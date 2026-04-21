from __future__ import annotations

import argparse
import logging
import re
import sys
import traceback
from builtins import print as _builtin_print
from pathlib import Path
import requests
import json
import time
import random
import uuid
from typing import Callable
from datetime import datetime
from mwclient import Site
from mwclient import errors
# 数据映射器导入
from arknights_toolbox.data import DataMapper
from arknights_toolbox.shared.services import (
    build_bilibili_headers,
    build_wiki_headers,
    fetch_character_supplementary_data,
    fetch_user_dynamics,
    publish_wiki_page_if_enabled,
    upload_operator_portrait_if_enabled,
    upload_site_file_with_retry,
    write_site_page,
)
from arknights_toolbox.shared.rendering import (
    process_description,
    render_operator_cv_fields,
    render_operator_dossier_fields,
    render_operator_infrastructure_fields,
    render_operator_potential_fields,
    render_operator_progression_fields,
    render_operator_skill_fields,
    render_operator_talent_fields,
    render_operator_trust_fields,
    render_operator_voice_template_lines,
    render_skill_materials,
    resolve_drawer_with_fallback,
    render_summon_template_lines,
)
from arknights_toolbox.shared.utils import (
    PHASE,
    normalize_voice_id,
    safe_get,
    sort_key,
)
from arknights_toolbox.shared.globals import (
    ACQUISITION_METHOD,
    DEFAULT_BILIBILI_MID,
    INFRASTRUCTURE_CONDITION,
    MAPPING_SKILL_TYPE,
    POSITION,
    PROFESSION,
    SKILL_TRIGGER_TYPE,
    SKILL_TYPE,
    VOICE_MAP,
    VOICE_ORDER,
)

script_log = logging.getLogger("arknights_tool.script")


def _detect_project_root() -> Path:
    """
        首先从运行时的当前工作目录检测项目根目录，如果失败则回退到模块路径。
    """
    starts = [Path.cwd(), Path(__file__).resolve()]
    for start in starts:
        for parent in [start, *start.parents]:
            if (parent / "log").is_dir():
                return parent
            # 兼容“从更高一级目录打开工程”的场景
            nested = parent / "arknights_toolbox"
            if (nested / "log").is_dir():
                return nested
    return Path(__file__).resolve().parents[2]


def default_log_path() -> str:
    """
        返回项目日志目录下的每日日志文件路径。
    """
    root = _detect_project_root()
    log_dir = root / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log")


def setup_script_logger(log_path: str | None, quiet: bool) -> None:
    """
        为脚本级日志附加控制台/文件处理程序。
    """
    logger = script_log
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_level = logging.INFO if quiet else logging.DEBUG
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if log_path:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)


def _strip_ark_gui_operator_markers(text: str) -> str:
    """去掉供 GUI 分标签用的行首标记；CLI 打印/写文件时更易读。"""
    return re.sub(r"^<<<ARK_GUI_OP\|[^>\n]+>>>\s*\n?", "", text or "", flags=re.MULTILINE)


def log_info(message, *args):
    script_log.info(message, *args)


def log_warning(message, *args):
    script_log.warning(message, *args)


def log_error(message, *args):
    script_log.error(message, *args)


def print(*args, **kwargs):
    """
        统一兼容旧 print 调用：默认转为 logger，显式 file 输出时保持原行为。
        这样 GUI/CLI 都可直接消费同一套日志流。
    """
    if kwargs.get("file") is not None:
        return _builtin_print(*args, **kwargs)
    sep = kwargs.get("sep", " ")
    message = sep.join(str(x) for x in args)
    level = kwargs.pop("level", None)
    if level is None:
        # 轻量规则：含“失败/错误”默认 warning；含“fatal/critical”按 error
        lower = message.lower()
        if "fatal" in lower or "critical" in lower:
            level = "error"
        elif "失败" in message or "错误" in message:
            level = "warning"
        else:
            level = "info"
    level = str(level).lower()
    if level == "error":
        log_error("%s", message)
    elif level in ("warn", "warning"):
        log_warning("%s", message)
    else:
        log_info("%s", message)

acquisition_method = ACQUISITION_METHOD
profession = PROFESSION
position = POSITION
skillType = SKILL_TYPE
skillTriggerType = SKILL_TRIGGER_TYPE
mapping_skill_type = MAPPING_SKILL_TYPE
Infrastructure_condition = INFRASTRUCTURE_CONDITION

def ocr_specialization(photo_path: str, roi_tune=None):
    try:
        import cv2
        import pytesseract
        import numpy as np
        import re
    except ImportError:
        log_warning("OCR依赖缺失，专精识别降级为空 path=%s", photo_path)
        return ""

    # ROI 可调参数（支持通过 roi_tune 覆盖，便于后续 GUI 做滑杆调参）
    cfg = {
        "x1_ratio": 0.00,
        "x2_ratio": 0.45,
        "y1_ratio": 0.25,
        "y2_ratio": 0.75,
        "win_h_ratio": 0.08,
        "win_w_ratio": 0.85,
        "step_ratio": 0.35,
        "pad_x_ratio": 0.01,
        "pad_y_ratio": 0.01,
        "crop_left_bias": 100,
        "crop_top_bias": 10,
        "crop_right_bias": -10,
        "crop_bottom_bias": -20,
    }
    if isinstance(roi_tune, dict):
        cfg.update(roi_tune)

    img_path = photo_path
    try:
        with open(img_path, "rb") as f:
            data = f.read()
    except OSError as e:
        log_warning("OCR读取图片失败，专精识别降级为空 path=%s err=%s", photo_path, e)
        return ""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    log_info("ocr_decode path=%s is_none=%s shape=%s", photo_path, img is None, None if img is None else img.shape)
    if img is None:
        log_warning("OCR图片解码失败，专精识别降级为空 path=%s", photo_path)
        return ""

    H, W = img.shape[:2]
    lang = "chi_sim"
    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s)
    # 只在左侧面板区域粗扫（比例可调）
    x1 = int(W * cfg["x1_ratio"])
    x2 = int(W * cfg["x2_ratio"])
    y1 = int(H * cfg["y1_ratio"])
    y2 = int(H * cfg["y2_ratio"])
    # 防御性裁剪，避免 ROI 参数异常导致空切片
    x1 = max(0, min(x1, W - 1))
    x2 = max(x1 + 1, min(x2, W))
    y1 = max(0, min(y1, H - 1))
    y2 = max(y1 + 1, min(y2, H))
    panel = img[y1:y2, x1:x2]
    # OCR的白名单会让它更“敢只猜这些字”，但也可能降低识别率：我们先用白名单找得分最高
    whitelist = "专精+-0123456789"
    # config_scan = f"--oem 3 --psm 6 -c tessedit_char_whitelist={whitelist}"
    config_scan = "--oem 3 --psm 11"
    def preprocess_for_ocr(bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # 放大让“小字”更容易被识别
        gray = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        # 轻微去噪 + OTSU（二值化比 adaptive 更稳一些）
        gray = cv2.bilateralFilter(gray, 5, 50, 50)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if th.mean() < 127:
            th = 255 - th
        return th

    best = None
    best_score = -1

    # 滑窗参数（窗口越大越容易包含“专精”，越小越容易漏：先从中等开始）
    win_h = max(1, int(panel.shape[0] * cfg["win_h_ratio"]))
    win_w = max(1, int(panel.shape[1] * cfg["win_w_ratio"]))  # 宽度给够，避免切断一行
    step = max(1, int(win_h * cfg["step_ratio"]))

    for y in range(0, panel.shape[0] - win_h + 1, step):
        roi = panel[y:y + win_h, 0:win_w]
        th = preprocess_for_ocr(roi)

        text = pytesseract.image_to_string(th, lang=lang, config=config_scan)
        t_raw = text.replace(" ", "").replace("\n", "")
        t = norm(text)

        score = 0
        if "专精" in t:
            log_info("ocr_scan_hit text=%s", t)
            score += 10
        score += t.count("专")
        score += t.count("精")
        if t.startswith("专精"):
            score += 10
        if score > best_score:
            best_score = score
            best = (x1, y1 + y, x1 + win_w, y1 + y + win_h, t)

    if best is None or best_score <= 0:
        log_warning("OCR粗扫未命中 path=%s best_score=%s", photo_path, best_score)
        return ""

    bx1, by1, bx2, by2, coarse_text = best
    log_info("ocr_coarse best_score=%s box=%s text=%s", best_score, (bx1, by1, bx2, by2), coarse_text)

    # 精读：对这个窗口再裁得更“干净”一点（padding 可调）
    pad_x = int((bx2 - bx1) * cfg["pad_x_ratio"])
    pad_y = int((by2 - by1) * cfg["pad_y_ratio"])

    fx1 = max(0, bx1 - pad_x + int(cfg["crop_left_bias"]))
    fy1 = max(0, by1 - pad_y + int(cfg["crop_top_bias"]))
    fx2 = min(W, bx2 + pad_x + int(cfg["crop_right_bias"]))
    fy2 = min(H, by2 + pad_y + int(cfg["crop_bottom_bias"]))
    fx2 = max(fx1 + 1, fx2)
    fy2 = max(fy1 + 1, fy2)

    roi_final = img[fy1:fy2, fx1:fx2]
    th_final = preprocess_for_ocr(roi_final)
    # cv2.imshow("th_final", th_final)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # 精读阶段可以用 psm 7（单行）或 6
    # config_final = f"--oem 3 --psm 6 -c tessedit_char_whitelist={whitelist}"
    config_final = f"--oem 3 --psm 6"
    final_text = pytesseract.image_to_string(th_final, lang=lang, config=config_final).replace(" ", "").replace("\n", "")
    # 置信度输出：使用 image_to_data 的 conf 作为 OCR 质量参考
    conf_score = 0.0
    try:
        data = pytesseract.image_to_data(
            th_final, lang=lang, config=config_final, output_type=pytesseract.Output.DICT
        )
        conf_vals = []
        for c in data.get("conf", []):
            try:
                v = float(c)
                if v >= 0:
                    conf_vals.append(v)
            except (TypeError, ValueError):
                continue
        if conf_vals:
            conf_score = sum(conf_vals) / len(conf_vals)
    except Exception as e:
        log_warning("OCR置信度计算失败 path=%s err=%s", photo_path, e)
    conf_level = "high" if conf_score >= 80 else ("medium" if conf_score >= 60 else "low")
    log_info(
        "ocr_final path=%s box=%s text=%s conf=%.2f conf_level=%s",
        photo_path,
        (fx1, fy1, fx2, fy2),
        final_text,
        conf_score,
        conf_level,
    )
    if conf_level == "low":
        log_warning("OCR置信度偏低 path=%s conf=%.2f text=%s", photo_path, conf_score, final_text)

    def _normalize_keyword_text(s: str) -> str:
        return (
            re.sub(r"\s+", "", s or "")
            .replace("專", "专")
            .replace("精", "精")
            .replace("菁", "精")
            .replace("睛", "精")
        )

    def _has_keyword(s: str) -> bool:
        ns = _normalize_keyword_text(s)
        return ("专精" in ns) or (re.search(r"专.{0,3}精", ns) is not None)
    # 优先用 final_text；若 final 丢字则回退 coarse_text
    final_ok = _has_keyword(final_text)
    coarse_ok = _has_keyword(coarse_text)

    if final_ok:
        log_info("ocr_accept path=%s source=final raw=%s", photo_path, final_text)
        return final_text
    if coarse_ok:
        log_warning(
            "OCR回退到粗识别 path=%s final=%s coarse=%s",
            photo_path,
            final_text,
            coarse_text,
        )
        return coarse_text

    log_warning(
        "OCR结果未包含关键词 path=%s final=%s coarse=%s",
        photo_path,
        final_text,
        coarse_text,
    )
    return ""


# 官号干员预告常见形态：…【卡池】\n//干员名\n“台词”。
_ANNOUNCE_LINE_RE = re.compile(r"(.*)【(.*?)】\n//(.*)\n(?:\u201c|\")(.*?)(?:\u201d|\")")


def get_user_dynamics(mid, headers,offset=None):
    """获取用户动态 - 通过B站API"""
    return fetch_user_dynamics(mid, headers, offset)

def get_character_supplementary_data(mid,headers,character_num):
    """通过b站api获取干员补充信息"""
    return fetch_character_supplementary_data(
        mid,
        headers,
        announce_line_re=_ANNOUNCE_LINE_RE,
        acquisition_method=acquisition_method,
        ocr_specialization=ocr_specialization,
        log_warning=log_warning,
        log_info=log_info,
        character_num=character_num,
    )
def _wiki_yes_no(
    prompt: str,
    *,
    wiki_key: str,
    wiki_flags: dict | None,
    interactive: bool,
    wiki_confirm: Callable[[str, str], bool] | None = None,
) -> bool:
    """
    Wiki 步骤确认：
    - interactive=True：终端 input(Y/N)。
    - interactive=False：先要求 wiki_flags[wiki_key] 为真；若提供 wiki_confirm，再二次回调（如 GUI 弹窗）。
    """
    if interactive:
        try:
            return input(prompt) == "Y"
        except EOFError:
            return False
    if not (wiki_flags and wiki_flags.get(wiki_key)):
        return False
    if wiki_confirm is not None:
        return bool(wiki_confirm(prompt, wiki_key))
    return True


def _set_current_char_id(mapper, cid):
    """设置 character_table 的 currentCharId（供 {currentCharId} 路径替换）"""
    mapper.mappings.setdefault("character_table", {})
    mapper.mappings["character_table"]["currentCharId"] = cid


def _current_character_row(mapper):
    """通过公开接口取当前干员整行数据（避免直接读 data_cache）"""
    cid = mapper.mappings.get("character_table", {}).get("currentCharId")
    if not cid:
        return None
    table = mapper.get_data("character_table")
    if not isinstance(table, dict):
        return None
    return table.get(cid)


def create_site_page(site, page_name, page_content, wiki_use_test_page: bool = True):
    """写入 Wiki 页面。wiki_use_test_page 为真时写入当前用户沙盒页，避免误改正式词条。"""
    write_site_page(
        site,
        page_name,
        page_content,
        wiki_use_test_page=wiki_use_test_page,
        errors_module=errors,
    )


def generate_template(
    voice_json,
    mapper,
    wiki_flags=None,
    interactive: bool = True,
    wiki_use_test_page: bool = True,
    wiki_confirm: Callable[[str, str], bool] | None = None,
    character_num: int = 3,
):
    """
    生成干员模板

    Args:
        voice_json: JSON数据
        mapper: 数据映射器实例
        wiki_flags: 非交互时生效，键 wiki_operator_page / wiki_voice_page / wiki_portrait
        interactive: True 时对 Wiki 操作逐项 input；False 时由 wiki_flags，且可经 wiki_confirm 二次确认
        wiki_use_test_page: True 时写入用户沙盒「用户:用户名/测试页」；False 时按真实词条标题写入
        wiki_confirm: 非交互且勾选允许时调用 (prompt, wiki_key) -> 是否执行写入
    """
    headers = build_bilibili_headers(mapper.config.get("cookies", ""))
    mid = str(mapper.config.get("bilibili_mid", DEFAULT_BILIBILI_MID))
    site_headers = build_wiki_headers()
    # 数据一律经 mapper 按需读取，避免整表硬编码路径散落
    # 获取 charId：从 voice_json 任意条目读取
    supplementary_data=None
    if voice_json == {}:
        supplementary_data=get_character_supplementary_data(mid,headers,character_num)
        # raise ValueError("voice_json 为空，请先在脚本里手动设定语音 JSON。")
    else:
        print()
    print(supplementary_data)
    parts = []
    # 每位干员的模板预览（干员页 + 语音）；避免后续 parts.clear() 导致 GUI/CLI 得到空串
    gui_operator_outputs: list[tuple[str, str]] = []
    name_set = set(supplementary_data.keys()) if supplementary_data else set()
    name_view = {}
    for cid in mapper.get_data("character_table", "charIdS"):
        _set_current_char_id(mapper, cid)
        nm = mapper.get_data_safe("character_table", "name")
        if nm in name_set:
            name_view[nm] = cid


    pool = requests.Session()
    # 从浏览器复制你的 SESSDATA 值填入下方
    SESSDATA=""
    for i in mapper.config["cookies"].split(";"):
        if "SESSDATA" in i:
            SESSDATA = i.split("=")[1]
            break
    if SESSDATA=="":
        log_warning("SESSDATA is not set")
    cookies = {
        'SESSDATA': SESSDATA,
        'domain': ".biligame.com"
    }
    site = None
    def get_site():
        nonlocal site
        if site is not None:
            return site
        try:
            requests.utils.add_dict_to_cookiejar(pool.cookies, cookies)
            site = Site("wiki.biligame.com", path="/arknights/", scheme="https", pool=pool, custom_headers=site_headers)
            log_info("连接成功！站点名称：%s", site.site['sitename'])
            log_info("用户名: %s",site.username)
            return site
        except Exception as e:
            log_error(f"Wiki连接失败（懒连接）：%s",e)
            return None

    for name,value in supplementary_data.items():

        found_cid = None
        alter_operator=None
        for cid in mapper.get_data("character_table", "charIdS"):
            _set_current_char_id(mapper, cid)
            if mapper.get_data_safe("character_table", "name") == f"{name}":
                found_cid = cid
                break
        if found_cid is None:
            print(f"未在 character_table 中找到干员：{name}")
            continue
        _set_current_char_id(mapper, found_cid)
        try:
            Id = found_cid
            parts.append("{{干员")
            parts.append(f"|干员代号={name}")

            if value.get('动态id') is not None:
                parts.append(f"|角标=限")
                parts.append(f"|解限=否")
            if "活动获取" in value.get("获取途径"):
                parts.append(f"|角标=活")
            parts.append(f"|背景=")
            alter_operator = ""
            char_id_str = str(Id).split("_")
            for cid in mapper.get_data("character_table", "charIdS"):

                if str(cid).startswith("char") and cid != Id and char_id_str[-1][:-1] in cid:
                    alter_operator = cid
                    break
            if alter_operator != "":
                parts.append(f"|角标=异")
            parts.append(f"|实装日期={value["实装日期"]}")
            parts.append(f"|charId={Id}")
            parts.append(f"|异格干员={alter_operator}")
            parts.append(f"|英文名={mapper.get_data_safe('character_table', f'appellation')}")
            parts.append(f"|职业={profession.get(mapper.get_data_safe('character_table', f'profession'))}")
            star = mapper.get_data_safe('character_table', f'rarity')
            parts.append(f"|星级={star}")
            print(star)
            parts.append(f"|干员编号={mapper.get_data_safe('character_table', f'displayNumber')}<!-- 类似B101格式的编号 -->")
            item =[]
            main_power = mapper.get_data_safe('character_table', f'mainPower')
            if main_power:
                for i in main_power.values():
                    if i != None:
                        item.append(i)
            parts.append(f"|阵营={'、'.join(mapper.get_data_safe("handbook_team_table",f"{i}.powerName") for i in item)}<!-- 有多少写多少，顿号隔开 -->")
            parts.append(f"|副阵营=")
            label=[]
            label.append(position.get(mapper.get_data_safe('character_table', f'position')))
            tag_list = mapper.get_data_safe('character_table', f'tagList')
            if tag_list:
                for i in tag_list:
                    label.append(i)
            parts.append(f"|标签={"、".join(i for i in label)}<!-- 包括近战位/远程位，然后抄tag参数，顿号隔开 -->")
            parts.append(f"|获取途径={value["获取途径"]}")
            trait = mapper.get_data_safe('character_table', f'trait')
            if isinstance(trait, dict):
                trait_candidates = trait.get('candidates', [])
            else:
                trait_candidates = []
            rich_styles = mapper.get_data_safe("gamedata_const",'richTextStyles')
            term_descriptionDict = mapper.get_data_safe("gamedata_const",'termDescriptionDict')
            term_index_cache = {}
            feature = process_description(mapper.get_data_safe('character_table', f'description'),trait_candidates,rich_styles,term_descriptionDict)
            parts.append(f"|特性={feature}")
            parts.append(f"|特性攻击范围=")
            parts.append(f"|分支={subProf(mapper, mapper.get_data_safe('character_table', f'subProfessionId'))}")
            # phasesDatas=[]
            # for phasesData in character['phases']:
            #     Data_temp={}
            #     for phases2_Data in phasesData['attributesKeyFrames']:
            #         data_temp=phases2_Data['data']
            #         Data_temp['level']=phases2_Data['level']
            #         Data_temp['maxHp']=data_temp['maxHp']
            #         Data_temp['atk']=data_temp['atk']
            #         Data_temp['def']=data_temp['def'']
            #         Data_temp['magicResistance']=data_temp['magicResistance']
            #         Data_temp['respawnTime']=data_temp['respawnTime']
            #         Data_temp['respawnTime']=data_temp['respawnTime']
            #         Data_temp['respawnTime']=data_temp['respawnTime']
            #         Data_temp['respawnTime']=data_temp['level']
            #         Data_temp['respawnTime']=data_temp['level']

            parts.extend(render_operator_progression_fields(mapper, star))

            parts.append(f"|精二动态id="+ (value["动态id"] if value.get('动态id') is not None else ""))

            levelUpCost = mapper.get_data_safe('character_table', '{skills}[*].levelUpCostCond')
            for i in range(1,4):
                for j in range(7,10):
                    # print(levelUpCost)
                    number = len(levelUpCost)
                    is_not_none = True
                    if number<i:
                        is_not_none = False
                    parts.append(f"|{i}技能{j}→{j+1}材料={(render_skill_materials(mapper, levelUpCost[i-1], j-6)) if is_not_none else ""}")
            parts.extend(
                render_operator_talent_fields(
                    mapper,
                    trait_candidates,
                    rich_styles,
                    term_descriptionDict,
                    term_index_cache,
                )
            )
            parts.extend(render_operator_potential_fields(mapper))

            for i in range(1,7):
                parts.append(f"|技能{i}→{i+1}材料={render_skill_materials(mapper,mapper.get_data_safe('character_table',"allSkillLvlup") , i)}")

            parts.extend(render_operator_trust_fields(mapper))
            skill_lines, summon_entries = render_operator_skill_fields(
                mapper,
                trait_candidates,
                rich_styles,
                term_descriptionDict,
                mapping_skill_type,
                term_index_cache,
            )
            parts.extend(skill_lines)
            summon_array = set()
            for _, is_not_none_familiar, summon_name in summon_entries:
                if summon_name != "" and summon_name not in summon_array:
                    summon = render_summon_template_lines(
                        mapper,
                        is_not_none_familiar,
                        summon_name,
                        name,
                        star,
                        trait_candidates,
                        rich_styles,
                        term_descriptionDict,
                        position,
                        mapping_skill_type,
                        skillType,
                        skillTriggerType,
                        term_index_cache,
                    )
                    if _wiki_yes_no(
                        f"干员附带单位{summon_name}页面确定创建(Y/N):",
                        wiki_key="wiki_operator_page",
                        wiki_flags=wiki_flags,
                        interactive=interactive,
                        wiki_confirm=wiki_confirm,
                    ):
                        site_obj = get_site()
                        if site_obj is not None:
                            create_site_page(site_obj, f"{summon_name}", "\n".join(summon), wiki_use_test_page)
                        else:
                            print("Wiki未连接，跳过创建召唤物页面")
                    summon_array.add(summon_name)
            parts.extend(
                render_operator_infrastructure_fields(
                    mapper,
                    Id,
                    trait_candidates,
                    rich_styles,
                    term_descriptionDict,
                    Infrastructure_condition,
                    term_index_cache,
                )
            )

            drawer = resolve_drawer_with_fallback(mapper, Id)
            parts.append(f"|画师={drawer}")

            parts.append(f"|皮肤=")
            parts.append(f"|skin1动态id=")
            parts.append(f"|皮肤2=")
            parts.append(f"|skin2动态id=")
            parts.append(f"|皮肤3=")
            parts.append(f"|skin3动态id=")
            parts.append(f"|皮肤4=")
            parts.append(f"|skin4动态id=")
            parts.append(f"|皮肤5=")
            parts.append(f"|skin5动态id=")
            parts.append(f"|皮肤6=")
            parts.append(f"|skin6动态id=")
            parts.extend(
                render_operator_dossier_fields(
                    mapper,
                    Id,
                    value,
                    trait_candidates,
                    rich_styles,
                    term_descriptionDict,
                    safe_get_fn=safe_get,
                    process_description_fn=process_description,
                )
            )

            parts.extend(render_operator_cv_fields(mapper, Id))
            parts.append("}}")
            main_wikitext = "\n".join(parts)

            publish_wiki_page_if_enabled(
                enabled=_wiki_yes_no(
                    f"干员{name}页面确定创建(Y/N):",
                    wiki_key="wiki_operator_page",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                ),
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建干员页面",
            )

            parts.clear()
            parts.extend(render_operator_voice_template_lines(mapper, Id, name, VOICE_MAP))
            voice_wikitext = "\n".join(parts)
            safe_tab_name = name.replace("|", "｜")
            gui_operator_outputs.append(
                (
                    safe_tab_name,
                    "【干员页模板】\n"
                    + ("-" * 56)
                    + "\n"
                    + main_wikitext
                    + "\n\n【干员语音/套】\n"
                    + ("-" * 56)
                    + "\n"
                    + voice_wikitext,
                )
            )
            publish_wiki_page_if_enabled(
                enabled=_wiki_yes_no(
                    f"干员{name}语音页面确定创建(Y/N):",
                    wiki_key="wiki_voice_page",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                ),
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}/默认/中文-普通话",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建语音页面",
            )
            parts.clear()
            upload_operator_portrait_if_enabled(
                enabled=_wiki_yes_no(
                    f"干员{name}半身像确定上传(Y/N):",
                    wiki_key="wiki_portrait",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                ),
                requests_module=requests,
                get_site_fn=get_site,
                upload_fn=upload_site_file_with_retry,
                operator_id=Id,
                operator_name=name,
                headers=headers,
            )
        except Exception as e:
            traceback.print_exc()  # 直接打印异常堆栈到控制台
            # 或者获取堆栈字符串以便进一步处理
            error_msg = traceback.format_exc()
            print(error_msg)
            parts.append(name)
            parts.append(str(value))
            gui_operator_outputs.append(
                (str(name).replace("|", "｜"), f"（生成失败）\n\n{error_msg}")
            )
    if gui_operator_outputs:
        blocks: list[str] = []
        for tab_name, body in gui_operator_outputs:
            blocks.append(f"<<<ARK_GUI_OP|{tab_name}>>>\n{body}")
        return "\n\n".join(blocks)
    return "\n".join(parts)


def load_json_file(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    with p.open('r', encoding='utf-8') as f:
        return json.load(f)
# def optimize_code(char_table, gamedata_const):
#     result = []
#     seen = set()
#     rich_styles = gamedata_const.get('richTextStyles', {})
#     for character in char_table.values():
#         desc = character.get('description')
#         if not desc:
#             continue
#         trait = character.get('trait', {})
#
#         if isinstance(trait, dict):
#             trait_candidates = trait.get('candidates', [])
#         else:
#             trait_candidates = []
#         processed = process_description(desc, trait_candidates, rich_styles)
#         if processed not in seen:
#             seen.add(processed)
#             result.append(processed)
#             print(processed)  # 保留原有打印行为
#     return result
def process_description(desc, trait_candidates, rich_styles,term_descriptionDict = None,blackboard = None):
    result_chars = []          # 最终字符列表
    stack = []                 # 栈元素：(tag_type, id, start_index)
    i = 0
    if desc is None:
        return ""
    length = len(desc)
    map_data={}
    if blackboard:
        for data in blackboard:
            if isinstance(data, dict):
                map_data[data["key"]]=data["value"]
            else:
                log_error("process_description blackboard data is not dict:%s",data)
                continue
    while i < length:
        ch = desc[i]
        # 检测开始标签：<@ 或 <$
        if ch == '<' and i + 1 < length and desc[i + 1] in ('@', '$'):
            end_idx = desc.find('>', i + 2)
            if end_idx != -1:
                tag_id = desc[i + 2:end_idx]
                tag_type = '<@' if desc[i + 1] == '@' else '<$'
                stack.append((tag_type, tag_id, len(result_chars)))
                i = end_idx + 1
                continue

        # 检测结束标签 </>
        elif ch == '<' and i + 2 < length and desc[i:i + 3] == '</>':
            if not stack:
                result_chars.append(ch)
                i += 1
                continue

            tag_type, tag_id, start_idx = stack.pop()
            parent_tag_type = stack[-1][0] if stack else None
            parent_is_shiyi = (parent_tag_type == '<$')
            inner = ''.join(result_chars[start_idx:])
            del result_chars[start_idx:]

            if tag_type == '<@':
                # 处理 <@...> 标签

                style = rich_styles.get(tag_id)
                if not style:
                    # 样式不存在，降级为释义标签
                    result_chars.append(f'{{{{释义|{inner}}}}}')
                    i += 3
                    continue

                color_match = re.match(r'<color=#([^>]*)>', style)
                if not color_match:
                    result_chars.append(f'{{{{释义|{inner}}}}}')
                    i += 3
                    continue
                color = color_match.group(1)

                # 解析 inner 中的特殊格式：前缀{key} 或 前缀{key:百分比}
                left_brace = inner.find('{')
                if left_brace == -1:
                    processed = inner
                else:
                    prefix = inner[:left_brace]
                    right_brace = inner.find('}', left_brace)
                    if right_brace == -1:
                        processed = inner
                    else:
                        key_part = inner[left_brace + 1:right_brace]
                        colon = key_part.find(':')
                        if colon == -1:
                            key = key_part
                            is_percent = False
                        else:
                            key = key_part[:colon]
                            is_percent = True
                        # 从 trait_candidates 中查找 key 对应的值
                        values = []
                        for cand in trait_candidates:
                            for board in cand.get('blackboard', []):
                                if board.get('key') == key:
                                    val = board.get('value')
                                    if val is not None:
                                        values.append(val)
                                    break  # 每个 candidate 只取第一个匹配
                        if not values:
                            value_str = key
                        elif is_percent:
                            value_str = str(int(values[-1] * 100)) + '%'
                        else:
                            value_str = '/'.join(str(int(v)) for v in values)

                        processed = prefix + value_str
                if parent_is_shiyi:
                    # 关键：把释义放进 color 里
                    result_chars.append(f'{{{{color|{color}|{{{{释义|{processed}}}}}}}}}')
                else:
                    # 原逻辑
                    result_chars.append(f'{{{{color|{color}|{processed}}}}}')

            else:  # tag_type == '<$'
                if inner.startswith('{{color|') and '{{释义|' in inner:
                    result_chars.append(inner)  # 不再二次包释义
                else:
                    result_chars.append(f'{{{{释义|{inner}}}}}')

            i += 3
            continue

        elif ch == '{':
            end = desc.find('}', i + 1)
            if end != -1:
                data = desc[i+1:end]
                i = end  # 移动索引
                if data.endswith(':0%'):
                    data = map_data[data[:-3]] * 100
                    rounded = round(data)  # 四舍五入到最近整数
                    if abs(data - rounded) < 1e-10:  # 如果误差小于极小阈值
                        data = int(rounded)  # 转换为整数
                    result_chars.append(f"{data}%")
                else:
                    data = map_data[data]
                    if data.is_integer():  # 仅对 float 有效，且要求精确整数
                        data = int(data)
                    result_chars.append(f"{data}")
            else:
                result_chars.append(ch)
            i+=1
        else:
            result_chars.append(ch)
            i += 1
    return "".join(result_chars);

def subProf(mapper, subProfessionId):
    if subProfessionId is None or subProfessionId == '':
        return ''
    mapper.add_mapping('uniequip_table', 'subProfessionId', subProfessionId)
    return mapper.get_data_safe('uniequip_table', 'sub_profession_name', default='')


def run_character_pipeline(
    *,
    config_path: str,
    data_source_group: str | None,
    wiki_flags: dict | None,
    voice_json=None,
    log_path=None,
    no_log_file: bool = False,
    quiet: bool = False,
    interactive: bool = True,
    wiki_use_test_page: bool = True,
    wiki_confirm: Callable[[str, str], bool] | None = None,
    character_num: int = 3,
) -> str:
    """
    供 GUI 与 CLI 共用的执行入口：配置日志 → DataMapper → generate_template。
    interactive=False 时：先按 wiki_flags 过滤；若传入 wiki_confirm，则在每次写入前再询问。
    """
    if voice_json is None:
        voice_json = {}
    if no_log_file:
        eff_log = None
    else:
        eff_log = log_path or default_log_path()
    debug = not quiet
    setup_script_logger(eff_log, quiet)
    run_id = uuid.uuid4().hex[:8]
    started_at = time.time()
    script_log.info("run_start run_id=%s log_file=%s debug=%s", run_id, eff_log, debug)

    try:
        mapper = DataMapper(
            config_path,
            debug=debug,
            log_path=eff_log,
            data_source_group=data_source_group,
        )
        mapper.set_run_context(run_id)
        script_log.info("数据映射器初始化成功 source=%s", getattr(mapper, "current_data_sources", None))
    except Exception:
        script_log.exception("数据映射器初始化失败")
        raise

    try:
        script_log.info("stage_start run_id=%s stage=generate_template", run_id)
        tpl = generate_template(
            voice_json,
            mapper,
            wiki_flags=wiki_flags,
            interactive=interactive,
            wiki_use_test_page=wiki_use_test_page,
            wiki_confirm=wiki_confirm,
            character_num=character_num,
        )
        script_log.info("stage_end run_id=%s stage=generate_template output_len=%d", run_id, len(tpl or ""))
        return tpl or ""
    except Exception:
        script_log.exception("stage_error run_id=%s stage=generate_template", run_id)
        raise
    finally:
        if mapper is not None:
            mapper.flush_missing_path_summary()
        elapsed_ms = int((time.time() - started_at) * 1000)
        script_log.info("run_end run_id=%s elapsed_ms=%d", run_id, elapsed_ms)


def main():
    parser = argparse.ArgumentParser(description="干员模板脚本（CLI；与 Gui/ark_gui_mock.py 共用 run_character_pipeline）")
    parser.add_argument(
        "--config",
        "-c",
        default="config.json",
        help="配置路径；相对路径默认优先从 arknights_toolbox/config 解析",
    )
    parser.add_argument(
        "--data-source",
        default=None,
        help="config.data_sources 顶层键，如 Kengxxiao/ArknightsGameData；省略时交互终端下标选择，非 tty 取第一项",
    )
    parser.add_argument("--out", "-o", default=None, help="输出文件路径（若不指定则打印到 stdout）")
    parser.add_argument(
        "--log-file",
        default=None,
        help="日志文件路径（默认: log/YYYY-MM-DD.log，追加写入）",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="不写日志文件，仅控制台输出",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="控制台不显示 DEBUG 级别（文件仍为 DEBUG，便于排错）",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="不对 Wiki 逐项询问；由 --wiki-* 开关决定（适合自动化 / GUI 对齐）",
    )
    parser.add_argument(
        "--wiki-operator-page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="非交互模式下是否创建干员页 / 召唤物页（默认：开）",
    )
    parser.add_argument(
        "--wiki-voice-page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="非交互模式下是否创建语音页（默认：开）",
    )
    parser.add_argument(
        "--wiki-portrait",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="非交互模式下是否上传半身像（默认：关）",
    )
    parser.add_argument(
        "--wiki-test-page",
        dest="wiki_use_test_page",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Wiki 文本写入目标：开启时写入当前用户沙盒「用户:用户名/测试页」；"
            "关闭请用 --no-wiki-test-page，按真实词条标题写入（默认开启）"
        ),
    )
    args = parser.parse_args()

    wiki_flags = {
        "wiki_operator_page": args.wiki_operator_page,
        "wiki_voice_page": args.wiki_voice_page,
        "wiki_portrait": args.wiki_portrait,
    }

    # ========== 在此手动粘贴/设定你的 voice_json（CLI 暂用空，走 B 站补充逻辑）==========
    voice_json: dict = {}
    # =====================================================================================

    try:
        tpl = run_character_pipeline(
            config_path=args.config,
            data_source_group=args.data_source,
            wiki_flags=wiki_flags,
            voice_json=voice_json,
            log_path=args.log_file,
            no_log_file=args.no_log_file,
            quiet=args.quiet,
            interactive=not args.no_interactive,
            wiki_use_test_page=args.wiki_use_test_page,
        )
    except Exception:
        sys.exit(1)

    out_text = _strip_ark_gui_operator_markers(tpl)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
