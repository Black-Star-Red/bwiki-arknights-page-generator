from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import traceback
from builtins import print as _builtin_print
from pathlib import Path
import requests
import json
import html
import time
import random
import uuid
from typing import Callable, Type
from datetime import datetime
from mwclient import Site
from mwclient import errors
# 数据映射器导入
from arknights_toolbox.data import DataMapper

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

acquisition_method={
    "限定寻访·春节":f"限定寻访、限定寻访·春节、【",
    "限定寻访·庆典":f"限定寻访、限定寻访·庆典、【",
    "限定寻访·夏季":f"限定寻访、限定寻访·夏季、【",
    "活动奖励干员":f"活动获取、【",
    "新增干员":f"标准寻访",
    "采购凭证区-新增干员":f"采购凭证区"
}
profession={
    "CASTER":"术师",
    "MEDIC":"医疗",
    "PIONEER":"先锋",
    "SNIPER":"狙击",
    "SPECIAL":"特种",
    "SUPPORT":"辅助",
    "TANK":"重装",
    "WARRIOR":"近卫",
}
position={
    "RANGED": "远程位",
    "MELEE": "近战位",
}
skillType = {
    "INCREASE_WITH_TIME":"自动回复",
    "INCREASE_WHEN_ATTACK":"攻击回复",
    "INCREASE_WHEN_TAKEN_DAMAGE":"受击回复",
    8:"被动"
}
skillTriggerType = {
    "PASSIVE":"被动",
    "MANUAL":"手动触发",
    "AUTO":"自动触发"
}
mapping_skill_type ={
    0:"",
    1:"弹药",
    "AMMO":"弹药",
}
VOICE_ORDER = {
    '037': 1,  # 标题
    '042': 2,  # 问候
    '043': 3,  # 生日
    '038': 4,  # 新年祝福
    '044': 5,  # 周年庆典
}
Infrastructure_condition={
    "0":"初始携带",
    "1":"精英化1",
    "2": "精英化2",
    "初始携带":"初始携带",
    "精英化1":"精英化1",
    "精英化2": "精英化2",
}
# voiceId -> 模板字段映射
VOICE_MAP = {
    '001': '任命助理',
    '002': '交谈1',
    '003': '交谈2',
    '004': '交谈3',
    '005': '晋升后交谈1',
    '006': '晋升后交谈2',
    '007': '信赖提升后交谈1',
    '008': '信赖提升后交谈2',
    '009': '信赖提升后交谈3',
    '010': '闲置',
    '011': '干员报到',
    '012': '观看作战记录',
    '013': '精英化晋升1',
    '014': '精英化晋升2',
    '017': '编入队伍',
    '018': '任命队长',
    '019': '行动出发',
    '020': '行动开始',
    '021': '选中干员1',
    '022': '选中干员2',
    '023': '部署1',
    '024': '部署2',
    '025': '作战中1',
    '026': '作战中2',
    '027': '作战中3',
    '028': '作战中4',
    '029': '完成高难行动',
    '030': '3星结束行动',
    '031': '非3星结束行动',
    '032': '行动失败',
    '033': '进驻设施',
    '034': '戳一下',
    '036': '信赖触摸',
    '037': '标题',
    '038': '新年祝福',
    '042': '问候',
    '043': '生日',
    '044': '周年庆典',
}

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
    api_url = f'https://api.bilibili.com/x/polymer/web-dynamic/desktop/v1/feed/space'

    params = {
        'host_mid': mid,  # 用户ID
        'offset': '' if offset is None else offset,  # 偏移量
    }

    for attempt in range(5):
        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=10)
            text = response.text or ""
            if response.status_code != 200:
                print(f"请求失败: status={response.status_code}")
            elif not text.strip():
                print("请求失败: empty response body")
            else:
                try:
                    data = response.json()
                    if data.get('code') == 0:
                        return data.get('data')
                    print(f"API错误: {data.get('message')}")
                except ValueError as e:
                    print(f"请求失败: JSON解析失败 {e}; 响应前200字符: {text[:200]}")
        except requests.RequestException as e:
            print(f"请求失败: {e}")

        # 指数退避 + 轻微随机抖动，降低被限流概率
        sleep_s = (2 ** attempt) * 0.5 + random.random() * 0.2
        time.sleep(sleep_s)
    return None

def get_character_supplementary_data(mid,headers):
    """通过b站api获取干员补充信息"""
    result={}
    diag = {"pages": 0, "items_total": 0, "skipped_exceptions": 0}
    url = f"https://api.bilibili.com/x/space/article"
    params = {
        'mid': '161775300',
        # 'pn': "",
        'ps': 12,  # 每页数量
        # 'sort': 'publish_time',
        # 'jsonp': 'jsonp'
    }
    request = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200 and (resp.text or "").strip():
                request = resp
                break
            print(f"获取卡池失败: status={resp.status_code}, body前120={resp.text[:120] if resp.text else ''}")
        except requests.RequestException as e:
            print(f"获取卡池失败: {e}")
        time.sleep((2 ** attempt) * 0.4 + random.random() * 0.2)

    pool_view = {}
    if request is not None:
        try:
            req_json = request.json()
            articles = req_json.get('data', {}).get('articles', [])
        except ValueError as e:
            print(f"获取卡池失败: JSON解析失败 {e}; 响应前200字符: {request.text[:200]}")
            articles = []
        for i in articles:
            if "限定寻访" in i['title']:
                data=[]
                data.append(i['title'][1:8])
                left = i['title'].find("【")
                right = i['title'].find("】")
                Ltime=i['summary'].find("活动时间：")
                Rtime=i['summary'].find("日")
                data.append(i['summary'][Ltime+5:Rtime+1])
                pool_view[i['title'][left + 1:right]] = data
    else:
        print("获取卡池失败")

    print(pool_view)
    dynamics = get_user_dynamics(mid,headers)

    SideStory=None
    release_time = None
    for i in range(20):
        if dynamics:
            diag["pages"] += 1
            items_page = dynamics.get('items') or []
            diag["items_total"] += len(items_page)
            # print(f"动态总数: {dynamics.get('total', 0)}")
            # print(f"当前页数: {dynamics.get('page', 2)}")
            for item in items_page:
                try:
                    data = item['modules'][1]['module_desc']['rich_text_nodes']
                    photoUrl = item['modules'][2]['module_dynamic']['dyn_draw']['items'][0]['src']
                    for index, i in enumerate(data):
                        str = i['orig_text']
                        if SideStory == None and re.match(r"SideStory「(.*)」",str):
                            SideStory = str[str.find("「")+1:str.find("」")]
                        if _ANNOUNCE_LINE_RE.match(str):
                            # print(item)
                            # print(str)
                            character = {}
                            GachaPool = str[str.find("【")+1:str.find("】")]
                            start = str.find("//")
                            end = str.find("\n", start)
                            name = str[start + 2:end]
                            # print(name)
                            # print(photoUrl)
                            photo_path = f"./photo/{name}.jpg"
                            if not Path(photo_path).exists():
                                photo = requests.get(photoUrl, timeout=10)
                                photo_dir = Path("photo")
                                photo_dir.mkdir(parents=True, exist_ok=True)
                                photo_path = photo_dir / f"{name}.jpg"
                                if photo.status_code == 200:
                                    photo_path.write_bytes(photo.content)
                            try:
                                character["专精"] = ocr_specialization(photo_path)
                            except Exception:
                                character["专精"] = ""
                                log_warning("专精OCR失败，已降级为空 name=%s", name)
                            print(character)
                            # print(GachaPool)
                            ImplementationData = pool_view.get(GachaPool)
                            if ImplementationData!=None:
                                if ImplementationData[1][0]=='0':
                                    ImplementationData[1]=ImplementationData[1][1:]
                                release_time = ImplementationData[1]
                                # print(ImplementationData)
                                if acquisition_method.get(ImplementationData[0])!=None :
                                    if len(data) > index + 1:
                                        splitIndex = data[index + 1]['orig_text'].rfind("/")
                                        character["动态id"]=data[index + 1]['orig_text'][splitIndex + 1:]
                                        character["获取途径"] = acquisition_method.get(ImplementationData[0]) + f"{GachaPool}】限定寻访"
                                    else:
                                        character["获取途径"] = acquisition_method.get("新增干员")
                            else:
                                if GachaPool=="活动奖励干员":
                                    character["获取途径"]=acquisition_method.get(GachaPool)+SideStory+"】活动获取"
                                else:
                                    if acquisition_method.get(GachaPool)!=None :
                                        character["获取途径"] = acquisition_method.get(GachaPool)
                                    else:
                                        character["获取途径"] = "标准寻访"
                            if release_time:
                                character["实装日期"]="[https://t.bilibili.com/" + item['id_str'] + "?spm_id_from=333.1387.0.0 "+release_time+"]"
                            else:
                                character["实装日期"] = "[https://t.bilibili.com/" + item['id_str'] + "?spm_id_from=333.1387.0.0 " + datetime.now().strftime("%Y年%m月%d日") + "]"
                            # print(str)
                            # character["专精"] = ocr_specialization(rf"./photo/{name}.jpg")
                            Introduction_temp = str[str.rfind("_") + 2:].rstrip("\n")
                            Introduction_temp = Introduction_temp.replace("\n", "<br/>\n")
                            # print(Introduction_temp)
                            # Introduction5 = re.sub(r'\n([^<]*)<br/>([^<]*)$', r'', Introduction_temp, flags=re.DOTALL)
                            character["宣传介绍"]=Introduction_temp
                            result[name]=character
                except Exception as e:
                    diag["skipped_exceptions"] += 1
                    continue
            offset = dynamics['offset']
            # print(offset)  # 下一偏移
            dynamics = get_user_dynamics(mid, offset)
    log_info("result:%s",result)
    if not result:

        script_log.warning(
            "supplementary_data_empty mid=%s pool_keys=%s pages=%s items_total=%s skipped_exceptions=%s",
            mid,
            len(pool_view),
            diag["pages"],
            diag["items_total"],
            diag["skipped_exceptions"],
        )
    return result
def create_handler(html_content: str) -> "Type[http.server.BaseHTTPRequestHandler]":
    try:
        import http.server
        import webbrowser
    except ImportError:
        raise ImportError
    """返回一个包含固定 html_content 的 Handler 类"""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        def log_message(self, format, *args):
            return
    return Handler

def view_in_browser(content: str):
    """在浏览器中显示模板内容"""
    try:
        import webbrowser
        import socketserver
        import threading
    except ImportError:
        raise ImportError
    escaped_content = html.escape(content)
    html_content = f"<pre>{escaped_content}</pre>"
    HandlerClass = create_handler(html_content)

    def start_server():
        with socketserver.TCPServer(("localhost", 0), HandlerClass) as httpd:
            port = httpd.server_address[1]
            webbrowser.open(f"http://localhost:{port}")
            httpd.serve_forever()

    threading.Thread(target=start_server, daemon=True).start()
    input("按 Enter 退出…")


def normalize_voice_id(vid):
    """从 'CN_001' / '001' / '1' 等提取数字并填充为 3 位字符串"""
    if vid is None:
        return None
    m = re.search(r'(\d+)', str(vid))
    if not m:
        return None
    return m.group(1).zfill(3)


def sort_key(item):
    _, norm_vid, _ = item
    # 如果在 VOICE_ORDER 里 → 给优先级 1，并用 VOICE_ORDER 排序
    # 否则 → 优先级 0，按 voiceId 正常排
    if norm_vid in VOICE_ORDER:
        return (1, VOICE_ORDER[norm_vid])
    return (0, int(norm_vid or 0))

def PHASE(phase_str):
    """将阶段代码（如 'PHASE_0'）转换为中文描述"""
    mapping = {
        "PHASE_0": "精英化0",
        "PHASE_1": "精英化1",
        "PHASE_2": "精英化2"
    }
    return mapping.get(phase_str, phase_str)
def Material(mapper, character_id, star, phase):
    # character_id 参数保留兼容；实际使用映射后的 phases
    phases = mapper.get_data_safe('character_table', 'phases')
    if not phases or len(phases) < 2:  # 缺少第二阶段数据
        return ''
    evolve_costs = phases[phase].get('evolveCost') if phase < len(phases) else None
    if not isinstance(evolve_costs, list):
        evolve_costs = []  # 确保为列表，便于统一处理
    # 根据星级拼接材料字符串
    if int(star) == 6:
        result = '{{data|龙门币|30000}}'if phase==1 else '{{data|龙门币|180000}}'
        for cost in evolve_costs:
            item_id = cost.get('id')
            count = cost.get('count')
            item_name = mapper.get_data_safe(
                'item_table', f'items.{item_id}.name', default=item_id if item_id is not None else '')
            result += f'{{{{data|{item_name}|{count}}}}}'
    elif int(star) == 5:
        result = '{{data|龙门币|20000}}' if phase==1 else '{{data|龙门币|120000}}'
        for cost in evolve_costs:
            item_id = cost.get('id')
            count = cost.get('count')
            item_name = mapper.get_data_safe(
                'item_table', f'items.{item_id}.name', default=item_id if item_id is not None else '')
            result += f'{{{{data|{item_name}|{count}}}}}'
    elif int(star) == 4:
        result = '{{data|龙门币|15000}}' if phase==1 else '{{data|龙门币|60000}}'
        for cost in evolve_costs:
            item_id = cost.get('id')
            count = cost.get('count')
            item_name = mapper.get_data_safe(
                'item_table', f'items.{item_id}.name', default=item_id if item_id is not None else '')
            result += f'{{{{data|{item_name}|{count}}}}}'
    elif int(star) == 3:
        result = '{{data|龙门币|10000}}'
    else:
        result = ''  # 其他星级未定义
    return result
def LevelUPEnhance(mapper, star, phase):
    """
    生成干员精二/晋升时的属性提升描述

    Args:
        mapper: 数据映射器实例（需已设置 character_table.currentCharId）
        star: 干员星级
        phase: 晋升阶段 (1=精1, 2=精2)

    Returns:
        提升描述字符串
    """
    # 稀有度不足3星时直接返回空字符串（或可根据需要调整）
    if int(star) < 3:
        return ''
    if int(star) == 3 and phase == 2:
        return ''

    content = "属性上限提升"

    # 1. 部署费用变化 - 使用安全访问
    cost0_path = "{phases}"+f"[{phase-1}].attributesKeyFrames[0].data.cost"
    cost1_path = "{phases}"+f"[{phase}].attributesKeyFrames[1].data.cost"

    cost0 = mapper.get_data_safe("character_table",cost0_path)
    cost1 = mapper.get_data_safe("character_table",cost1_path)

    if cost1 - cost0 > 0:
        content += f"<br/>增加部署费用{{{{color|ff6801|{cost1 - cost0}}}}}"

    # 2. 四星及以上获得新技能
    if int(star) > 3:
        if int(star) == 6:
            skill_id_path = "{skills}"+f"[{phase}].skillId"
        else:
            skill_id_path = "{skills}"+f"[{phase-1}].skillId"

        # 安全获取技能ID（经 character_table 映射）
        skills = mapper.get_data_safe('character_table', '{skills}', default=[]) or []
        if int(star) == 6 and len(skills) > phase:
            skill_id = skills[phase].get('skillId')
        elif len(skills) > phase:
            skill_id = skills[phase].get('skillId')
        else:
            skill_id = None

        if skill_id:
            levels = mapper.get_data_safe('skill_table', f'{skill_id}.levels', default=[]) or []
            skill_name = levels[0].get('name', '未知技能') if levels else '未知技能'
            content += f"<br/>获得新技能{{{{color|00b0ff|{skill_name}}}}}"

    # 3. 第一个天赋的阶段检查（是否同时有 PHASE_0 和 PHASE_1）
    talents = mapper.get_data_safe('character_table', '{talents}', default=[]) or []
    has_phase0_and_phase1 = False
    talents0_candidates = []
    def _norm_phase(v):
        return mapper._apply_value_map("character_table", "phase", v)

    if talents and len(talents) > 0:
        talents0_candidates = talents[0].get('candidates', [])
        has_phase0 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase-1}" for c in talents0_candidates)
        has_phase1 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}" for c in talents0_candidates)
        has_phase0_and_phase1 = has_phase0 and has_phase1
        if has_phase0_and_phase1 and talents0_candidates:
            talent_name = talents0_candidates[0].get("name", "未知天赋")
            content += f"<br/>天赋{{{{color|00b0ff|{talent_name}}}}}获得提升"

    # 4. 第二天赋处理（如果存在且第一个候选有名称）
    has_phase0_and_phase1_2 = False
    if len(talents) > 1 and talents[1].get("candidates") and talents[1]["candidates"][0].get("name"):
        talents1_candidates = talents[1]["candidates"]
        has_phase0_2 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase-1}" for c in talents1_candidates)
        has_phase1_2 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}" for c in talents1_candidates)
        has_phase0_and_phase1_2 = has_phase0_2 and has_phase1_2

        if has_phase0_and_phase1_2:
            talent_name2 = talents1_candidates[0].get("name", "未知天赋")
            content += f"<br/>天赋{{{{color|00b0ff|{talent_name2}}}}}获得提升"
        elif talents1_candidates and _norm_phase(talents1_candidates[0].get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}":
            talent_name_new = talents1_candidates[0].get('name', '未知天赋')
            content += f"<br/>新获得天赋{{{{color|00b0ff|{talent_name_new}}}}}"

    # 5. 如果第一个天赋不满足同时有 PHASE_0 和 PHASE_1，则视为新获得天赋
    if not has_phase0_and_phase1 and talents0_candidates:
        talent_name_first = talents0_candidates[0].get('name', '未知天赋')
        content += f"<br/>新获得天赋{{{{color|00b0ff|{talent_name_first}}}}}"

    # 6. 如果第二天赋存在且不满足同时有 PHASE_0 和 PHASE_1，再次添加新获得天赋（注意可能重复）
    # if len(character["talents"]) > 1 and not has_phase0_and_phase1_2:
    #     content += f"<br/>新获得天赋{{{{color|00b0ff|{character['talents'][1]['candidates'][0]['name']}}}}}"
    # 6. 攻击范围变化检查
    phases = mapper.get_data_safe('character_table', '{phases}', default=[]) or []
    if len(phases) > phase:
        range_id_prev = phases[phase-1].get("rangeId") if len(phases) > phase-1 else None
        range_id_curr = phases[phase].get("rangeId")
        if range_id_prev != range_id_curr:
            content += "<br/>攻击范围扩大"

    # 7. 特性变化检查
    trait = mapper.get_data_safe('character_table', 'trait')
    if trait and trait.get("candidates"):
        for candidate in trait["candidates"]:
            unlock_condition = candidate.get("unlockCondition", {})
            phase_condition = unlock_condition.get("phase")
            if phase_condition and PHASE(phase_condition) == f"精英化{phase}":
                content += "<br/>{{color|00b0ff|特性}}更新"
                break

    # 8. 模组系统检查（仅精2）
    if phase == 2:
        potential_item_id = mapper.get_data_safe('character_table', '{currentCharId}.potentialItemId', default='') or ''
        start = potential_item_id.rfind("_")
        if start != -1:
            mod_id = f"uniequip_001_{potential_item_id[start+1:]}"
            # 检查模组是否存在
            equip_dict = mapper.get_data_safe('uniequip_table', 'equipDict', {})
            if mod_id in equip_dict:
                content += "<br/>开启{{color|00b0ff|模组系统}}"

    return content


def render_skill_materials(mapper, all_skill_lvlup, level):
    """
    渲染技能升级材料

    Args:
        mapper: 数据映射器实例
        all_skill_lvlup: 技能升级数据
        level: 技能等级

    Returns:
        材料字符串
    """
    level -= 1
    costs = all_skill_lvlup[level].get('lvlUpCost') if level < len(all_skill_lvlup) else None
    costs = all_skill_lvlup[level].get('levelUpCost') if (costs is None and level < len(all_skill_lvlup)) else costs

    if isinstance(costs, list):
        parts_m = []
        for cost in costs:
            iid = cost.get('id')
            nm = mapper.get_data_safe(
                'item_table', f'items.{iid}.name', default=iid if iid is not None else '未知物品')
            parts_m.append(f'{{{{data|{nm}|{cost.get("count", "")}}}}}')
        materials = ''.join(parts_m)
    else:
        materials = ''
    return materials
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


def safe_get(data, keys, default=None):
    """
    安全地从嵌套字典/列表中取值。
    支持字典键和列表索引混合，若中途缺失或索引越界则返回 default。
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        elif isinstance(current, list) and isinstance(key, int):
            if 0 <= key < len(current):
                current = current[key]
            else:
                return default
        else:
            return default
    return current


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
    if wiki_use_test_page:
        page = site.pages[f"用户:{site.username}/测试页"]
    else:
        page = site.pages[page_name]
    # 获取页面并编辑
    try:
        result = page.edit(text=page_content, summary=f"{page_name}")
        # result = page.edit(text=page_content)
        print(result)  # 如果成功会返回 True
    except errors.APIError as e:
        if e.code == 'abusefilter-warning':
            print("触发了防滥用过滤器警告，正在尝试二次提交...")
            # 再次提交相同内容（相当于点击“确认”）
            if wiki_use_test_page:
                result = page.edit(text=page_content, summary=f"{page_name}")
            else:
                result = page.edit(text=page_content)
            print(result)  # 如果成功会返回 True
        else:
            raise e


def process_description(desc, trait_candidates, rich_styles,termDescriptionDict,blackboard = None):
    result_chars = []          # 最终字符列表
    stack = []                 # 栈元素：(tag_type, id, start_index)
    i = 0
    if desc is None:
        return ""
    length = len(desc)
    map_data={}
    if blackboard:
        for data in blackboard:
            map_data[data["key"]]=data["value"]
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

                result_chars.append(f'{{{{color|{color}|{processed}}}}}')

            else:  # tag_type == '<$'
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

    return ''.join(result_chars)

def build_drawer_from_skins(mapper, char_id):
    drawer = ""
    char_skins = mapper.get_data_safe('skin_table', 'charSkins') or {}
    for skin_key, skin_value in char_skins.items():
        if char_id == skin_value["charId"] and skin_value["displaySkin"]["skinGroupId"] == "ILLUST_0":
            for i in skin_value["displaySkin"]["drawerList"]:
                if '、' in i:
                    for j in list(filter(lambda s: s.strip() != "", i.split("、"))):
                        drawer += j + "、"
                else:
                    drawer += i + "、"
            if skin_value["displaySkin"]["designerList"] and len(skin_value["displaySkin"]["designerList"]) > 0:
                for i in skin_value["displaySkin"]["designerList"]:
                    if '、' in i:
                        for j in list(filter(lambda s: s.strip() != "", i.split("、"))):
                            drawer += j + "（原案）、"
                    else:
                        drawer += i + "（原案）、"
    if drawer.endswith('、'):
        drawer = drawer[:-1]
    return drawer
def generate_template(
    voice_json,
    mapper,
    wiki_flags=None,
    interactive: bool = True,
    wiki_use_test_page: bool = True,
    wiki_confirm: Callable[[str, str], bool] | None = None,

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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cookie': f"{mapper.config["cookies"]}"
    }
    mid = "161775300"
    site_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer':"https://wiki.biligame.com/arknights/",
    }
    # 数据一律经 mapper 按需读取，避免整表硬编码路径散落
    # 获取 charId：从 voice_json 任意条目读取
    supplementary_data=None
    if voice_json == {}:
        supplementary_data=get_character_supplementary_data(mid,headers)
        # raise ValueError("voice_json 为空，请先在脚本里手动设定语音 JSON。")
    else:
        print()
    print(supplementary_data)
    parts = []
    # 每位干员的模板预览（干员页 + 语音）；避免后续 parts.clear() 导致 GUI/CLI 得到空串
    gui_operator_outputs: list[tuple[str, str]] = []
    summon =[]
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

            phases0_data = mapper.get_data_safe('character_table', '{phases}[0].attributesKeyFrames[0].data')
            parts.append(f"|初始生命={phases0_data.get('maxHp', '') if phases0_data else ''}")
            parts.append(f"|初始攻击={phases0_data.get('atk', '') if phases0_data else ''}")
            parts.append(f"|初始防御={phases0_data.get('def', '') if phases0_data else ''}")
            parts.append(f"|初始法抗={int(phases0_data.get('magicResistance', 0)) if phases0_data else ''}")
            parts.append(f"|再部署={phases0_data.get('respawnTime', '') if phases0_data else ''}")
            parts.append(f"|部署费用={phases0_data.get('cost', '') if phases0_data else ''}")
            rdcCost=0
            potential_ranks = mapper.get_data_safe('character_table', f'potentialRanks')
            if potential_ranks:
                for i in range(len(potential_ranks)):
                    if potential_ranks[i].get('description') == "部署费用-1":
                        rdcCost+=1
            costPro=None
            zudang=None
            if int(star)>= 4:
                phase_data = mapper.get_data_safe('character_table', '{phases}[*].attributesKeyFrames[1].data')
                costPro = phase_data[2].get('cost', 0) - rdcCost if phase_data[2] else 0
                phases_data = []
                for i in range(3):
                    if phase_data:
                        phases_data.append(str(phase_data[i].get('blockCnt', 0)))
                zudang = "→".join(phases_data)
            elif int(star) == 3:
                phase_data = mapper.get_data_safe('character_table', '{phases}[*].attributesKeyFrames[1].data')
                costPro = phase_data[1].get('cost', 0) - rdcCost if phase_data[1] else 0
                phases_data = []
                for i in range(2):
                    if phase_data:
                        phases_data.append(str(phase_data.get('blockCnt', 0)))
                zudang = "→".join(phases_data)
            elif int(star) < 3:
                phases0_max_data = mapper.get_data_safe('character_table', '{phases}[0].attributesKeyFrames[1].data')
                costPro = phases0_max_data.get('cost', 0) - rdcCost if phases0_max_data else 0
                phases_data = []
                if phases0_max_data:
                    phases_data.append(str(phases0_max_data.get('blockCnt', 0)))
                zudang = "→".join(phases_data)

            parts.append(f"|完美部署费用={costPro}<!-- 计算精二满潜费用 -->")
            parts.append(f"|阻挡数={zudang}")
            attack_speed = phases0_data.get('attackSpeed', 0) if phases0_data else 0
            if isinstance(attack_speed, float) and attack_speed.is_integer():
                attack_speed = int(attack_speed)
            parts.append(f"|攻击速度={attack_speed}<!-- 写攻击速度的值 -->")
            parts.append(f"|攻击间隔={phases0_data.get('baseAttackTime', '') if phases0_data else ''}<!-- 写攻击间隔的值 -->")
            parts.append(f"|bb备注=")
            parts.append(f"|初始攻击范围={mapper.get_data_safe('character_table', 'rangeId')[0]}")

            phases0_max_data = mapper.get_data_safe('character_table','{phases}[0].attributesKeyFrames[1].data')
            parts.append(f"|初始生命max={phases0_max_data.get('maxHp', '') if phases0_max_data else ''}")
            parts.append(f"|初始攻击max={phases0_max_data.get('atk', '') if phases0_max_data else ''}")
            parts.append(f"|初始防御max={phases0_max_data.get('def', '') if phases0_max_data else ''}")
            parts.append(f"|初始法抗max={int(phases0_max_data.get('magicResistance', 0)) if phases0_max_data else ''}")
            parts.append(f"|精1等级需求={mapper.get_data_safe('character_table','{phases}[0].maxLevel')}")

            parts.append(f"|精1提升={LevelUPEnhance(mapper, star, 1)}")

            parts.append(f"|精1材料={Material(mapper, "{phases}", star, 1)}")

            phases1_max_data = mapper.get_data_safe('character_table', '{phases}[1].attributesKeyFrames[1].data') if int(star)>2 else None

            parts.append(f"|精1生命max={phases1_max_data.get('maxHp', '') if phases1_max_data else ''}")
            parts.append(f"|精1攻击max={phases1_max_data.get('atk', '') if phases1_max_data else ''}")
            parts.append(f"|精1防御max={phases1_max_data.get('def', '') if phases1_max_data else ''}")
            parts.append(f"|精1法抗max={int(phases1_max_data.get('magicResistance', 0)) if phases1_max_data else ''}")
            parts.append(f"|精1攻击范围={mapper.get_data_safe('character_table', 'rangeId')[1] if phases1_max_data else ''}")


            phases2_max_data = mapper.get_data_safe('character_table', '{phases}[2].attributesKeyFrames[1].data') if int(star)>3 else None
            parts.append(f"|精2等级需求={mapper.get_data_safe('character_table', '{phases}[1].maxLevel') if phases2_max_data else ''}")
            parts.append(f"|精2提升={LevelUPEnhance(mapper, star, 2)}")
            parts.append(f"|精2材料={Material(mapper, "{phases}", star, 2)}")

            parts.append(f"|精2生命max={phases2_max_data.get('maxHp', '') if phases2_max_data else ''}")
            parts.append(f"|精2攻击max={phases2_max_data.get('atk', '') if phases2_max_data else ''}")
            parts.append(f"|精2防御max={phases2_max_data.get('def', '') if phases2_max_data else ''}")
            parts.append(f"|精2法抗max={int(phases2_max_data.get('magicResistance', 0)) if phases2_max_data else ''}")
            parts.append(f"|精2攻击范围={mapper.get_data_safe('character_table', '{phases}[2].rangeId') if phases2_max_data else ''}")

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
            potential = {
                "0":"",
                "1": "、潜能2",
                "2": "、潜能3",
                "3": "、潜能4",
                "4": "、潜能5",
                "5": "、潜能6",
            }
            talents_candidates = mapper.get_data_safe(
                'character_table', '{talents}[*].candidates', default=[]
            ) or []
            print(talents_candidates)
            for i in range(1, 3):
                for j in range(0, 6):
                    is_not_none = False
                    talent = ""
                    talent_condition = ""
                    talent_description = ""
                    if (
                        len(talents_candidates) >= i
                        and talents_candidates[i - 1]
                        and len(talents_candidates[i - 1]) > j
                    ):
                        is_not_none = True
                        mapper.add_mapping("character_table", "talent_group_index", str(i-1))
                        mapper.add_mapping("character_table", "talent_candidate_index", str(j))
                        talent = mapper.get_data_safe("character_table", "talent_name", default="") or ""
                        phase = mapper.get_data_safe("character_table", "talent_phase", default="PHASE_0")
                        phase = mapper._apply_value_map("character_table", "phase", phase)
                        required_potential = mapper.get_data_safe(
                            "character_table", "talent_required_potential", default=0
                        )
                        phase_text = str(PHASE(phase))
                        talent_condition = (
                            phase_text + potential.get(str(required_potential), "")
                            if (phase != "PHASE_0" or required_potential != 0)
                            else "初始携带"
                        )
                        if talent =="":
                            talent_condition=""
                        talent_description = process_description(
                            mapper.get_data_safe("character_table", "talent_description", default=""),
                            trait_candidates,
                            rich_styles,
                            term_descriptionDict
                        )
                    parts.append(f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"提升后" if j>=1 else ""}={talent if is_not_none else ""}")
                    parts.append(f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"解锁" if j<1 else ""}{"提升" if j>=1 else ""}条件={talent_condition if is_not_none else ""}")
                    parts.append(f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"提升后" if j>=1 else ""}描述={talent_description if is_not_none else ""}")
                parts.append(f"|天赋{i}备注=")
                parts.append(f"|天赋{i}攻击范围=")
            for i in range(2,7):
                potential_ranks = mapper.get_data_safe('character_table','potentialRanks')
                description = ""
                if potential_ranks and len(potential_ranks) > i-2:
                    description = potential_ranks[i-2].get("description", "")
                parts.append(f"|潜能{i}={description}")

            for i in range(1,7):
                parts.append(f"|技能{i}→{i+1}材料={render_skill_materials(mapper,mapper.get_data_safe('character_table',"allSkillLvlup") , i)}")

            trust = {
                "maxHp":"生命",
                "atk": "攻击",
                "def": "防御",
                "magicResistance": "法抗",
            }
            for attribute_key,attribute_value in trust.items():
                favor_data = mapper.get_data_safe('character_table', '{favorKeyFrames}[1].data')
                data = favor_data.get(attribute_key, 0) if favor_data else 0
                parts.append(f"|信赖{attribute_value}={"+"+str(data) if data>0 else ""}")
            summon_array=set()
            for i in range(1, 4):
                skill_id = mapper.get_data_safe('character_table', "{skills}"+f"[{i-1}].skillId")
                skill_data = mapper.get_data_safe('skill_table', f'{skill_id}.levels') if skill_id else None
                skill_name = skill_data[i-1].get('name') if skill_data and len(skill_data) > i-1 else None
                skill_icon = skill_data[i-1].get('icon') if skill_data and len(skill_data) > i-1 else None
                is_null_skill_icon = skill_icon if skill_name != skill_icon else skill_name
                skill_range = skill_data[i-1].get('rangeId') if skill_data and len(skill_data) > i-1 else None
                sp_data = skill_data[i-1].get('spData', {}) if skill_data and len(skill_data) > i-1 else {}
                skill_recover_type = sp_data.get('spType')
                skill_trigger_type = skill_data[i-1].get('skillType') if skill_data and len(skill_data) > i-1 else None
                skill_type = skill_data[i-1].get('durationType') if skill_data and len(skill_data) > i-1 else None
                is_not_none_familiar = mapper.get_data_safe('character_table',"{skills}"+f"[{i-1}].overrideTokenKey")

                parts.append(f"|技能{i}={skill_name if skill_name != None else ""}")
                parts.append(f"|skillId{i}={skill_id if skill_id != None else ""}")
                parts.append(f"|skillIcon{i}={"" if is_null_skill_icon ==None else skill_icon}")
                parts.append(f"|技能{i}类型={mapping_skill_type[skill_type] if skill_type!=None and skill_type !="NONE" else ""}")
                parts.append(f"|技能{i}攻击范围={skill_range if skill_range!=None else ""}")
                parts.append(f"|技能{i}回复类型={mapper._apply_value_map('skill_table', 'sp_type', skill_recover_type) or ''}")
                parts.append(f"|技能{i}触发类型={mapper._apply_value_map('skill_table', 'skill_trigger_type', skill_trigger_type) or ''}")
                for j in range(1, 11):
                    level_data = skill_data[j-1] if skill_data and len(skill_data) > j-1 else {}
                    sp_data = level_data.get('spData', {})
                    skill_comsume = sp_data.get('spCost')
                    skill_init = sp_data.get('initSp')
                    skill_consistent_time = level_data.get('duration')
                    if skill_consistent_time is not None:
                        rounded = round(skill_consistent_time)  # 四舍五入到最近整数
                        if abs(skill_consistent_time - rounded) < 1e-10:  # 如果误差小于极小阈值
                            skill_consistent_time = int(rounded)  # 转换为整数
                    skill_description = level_data.get('description')
                    blackboard = level_data.get('blackboard', [])
                    parts.append(f"|技能{i}描述{j}={process_description(skill_description,trait_candidates, rich_styles, term_descriptionDict,blackboard).replace(r"\n","<br/>")}")
                    parts.append(f"|技能{i}技力消耗{j}={skill_comsume if skill_comsume else ""}")
                    parts.append(f"|技能{i}初始技力{j}={skill_init if skill_init!=None else ""}")
                    parts.append(f"|技能{i}持续时间{j}={skill_consistent_time if skill_consistent_time!=None and skill_consistent_time>=0 else ""}")
                parts.append(f"|技能{i}备注=")
                summon_name = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.name") if is_not_none_familiar else ""
                parts.append(f"|召唤物{i}={summon_name}<!-- 请额外创建页面，使用干员附带单位模板 -->")
                if summon_name != "" and summon_name not in summon_array:
                    summon.append("{{干员附带单位")
                    summon.append(f"|charId={is_not_none_familiar}")
                    summon.append(f"|皮肤名=")
                    summon.append(f"|单位名称={summon_name}")
                    summon.append(f"|所属干员={name}")
                    summon.append(f"|英文名={mapper.get_data_safe('character_table', f"{is_not_none_familiar}.appellation") if is_not_none_familiar else ''}")
                    feature = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.description") if is_not_none_familiar else ""
                    summon.append(f"|特性={ feature if feature else "无" }")
                    summon.append(f"|部署位={position.get(mapper.get_data_safe('character_table', f"{is_not_none_familiar}.position"), '') if is_not_none_familiar else ''}")
                    for phase_idx in range(0,3):
                        if phase_idx==0:
                            keyframe_idx=0
                        else:
                            keyframe_idx=1
                        phase_data = mapper.get_data_safe('character_table',f"{is_not_none_familiar}.phases"+f"[{phase_idx}].attributesKeyFrames[{keyframe_idx}].data") if is_not_none_familiar else {}
                        lift = phase_data.get('maxHp')
                        atk = phase_data.get('atk')
                        def_data = phase_data.get('def')
                        magic = phase_data.get('magicResistance')
                        if phase_idx==0:
                            summon.append(f"|初始生命={lift if lift is not None else ""}")
                            summon.append(f"|初始攻击={atk  if atk is not None else ""}")
                            summon.append(f"|初始防御={def_data if def_data is not None else ""}")
                            summon.append(f"|初始法抗={int(magic) if magic is not None else ""}")

                            max_phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[0].attributesKeyFrames[1].data") if is_not_none_familiar else {}
                            lift = max_phase_data.get('maxHp')
                            atk = max_phase_data.get('atk')
                            def_data = max_phase_data.get('def')
                            magic = max_phase_data.get('magicResistance')
                            summon.append(f"|初始生命max={lift if lift is not None else ""}")
                            summon.append(f"|初始攻击max={atk  if atk is not None else ""}")
                            summon.append(f"|初始防御max={def_data if def_data is not None else ""}")
                            summon.append(f"|初始法抗max={int(magic) if magic is not None else ""}")
                        else:
                            summon.append(f"|精{phase_idx}生命max={lift if lift is not None else ""}")
                            summon.append(f"|精{phase_idx}攻击max={atk  if atk is not None else ""}")
                            summon.append(f"|精{phase_idx}防御max={def_data if def_data is not None else ""}")
                            summon.append(f"|精{phase_idx}法抗max={int(magic) if magic is not None else ""}")

                    summon_cost = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[0].attributesKeyFrames[0].data") if is_not_none_familiar else {}
                    summon.append(f"|部署费用={summon_cost.get('cost', '') if summon_cost else ''}")
                    block = None
                    if int(star) >= 4:
                        respawnTime = []
                        phases_data = []
                        for i in range(3):
                            phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[{i}].attributesKeyFrames[0].data") if is_not_none_familiar else {}
                            respawnTime.append(phase_data.get('respawnTime'))
                            max_phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[{i}].attributesKeyFrames[1].data") if is_not_none_familiar else {}
                            phases_data.append(max_phase_data.get('blockCnt', 0))
                    elif int(star) == 3:
                        respawnTime = []
                        phases_data = []
                        for i in range(2):
                            phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[{i}].attributesKeyFrames[0].data") if is_not_none_familiar else {}
                            respawnTime.append(phase_data.get('respawnTime'))
                            max_phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[{i}].attributesKeyFrames[1].data") if is_not_none_familiar else {}
                            phases_data.append(max_phase_data.get('blockCnt', 0))
                    elif int(star) < 3:
                        respawnTime = []
                        phases_data = []
                        phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[0].attributesKeyFrames[0].data") if is_not_none_familiar else {}
                        respawnTime.append(phase_data.get('respawnTime'))
                        max_phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[0].attributesKeyFrames[1].data") if is_not_none_familiar else {}
                        phases_data.append(max_phase_data.get('blockCnt', 0))
                    else:
                        respawnTime,phases_data = [None]*2
                    first = phases_data[0] if phases_data else None
                    if phases_data and all(x == first for x in phases_data):
                        block = phases_data[0]
                    else:
                        block = "→".join(str(value) for value in phases_data) if phases_data else ""
                    first = respawnTime[0] if respawnTime else None
                    if respawnTime and all(x == first for x in respawnTime):
                        time_block = respawnTime[0]
                    else:
                        time_block = "s→".join(str(value) for value in respawnTime) if respawnTime else ""
                    summon.append(f"|阻挡数={block}")
                    summon.append(f"|再部署={time_block}S")
                    summon_phase_data = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[0].attributesKeyFrames[0].data") if is_not_none_familiar else {}
                    atk_speed = summon_phase_data.get('attackSpeed')
                    atk_time = summon_phase_data.get('baseAttackTime')
                    tauntLevel = summon_phase_data.get('tauntLevel')
                    summon.append(f"|攻击速度={atk_speed if atk_speed else ""}")
                    summon.append(f"|攻击间隔={atk_time if atk_time else ""}s")
                    summon.append(f"|嘲讽等级={tauntLevel if tauntLevel is not None else ""}")
                    rangeId_data = []
                    for i in range(0,3):
                        range_id = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.phases[{i}].rangeId") if is_not_none_familiar else None
                        rangeId_data.append(range_id)
                    summon.append(f"|初始攻击范围={rangeId_data[0] if rangeId_data[0] else ""}")
                    summon.append(f"|精1攻击范围={rangeId_data[1] if rangeId_data[1] else ""}")
                    summon.append(f"|精2攻击范围={rangeId_data[2] if rangeId_data[2] else ""}")
                    print("REACH_TALENT_BLOCK", Id, flush=True)
                    for i in range(1, 3):
                        try:
                            print("REACH_TALENT_ITER", i, repr(is_not_none_familiar), flush=True)
                            talents_candidates = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.talents[{i-1}].candidates") if is_not_none_familiar else []
                            print("TALENTS_CANDIDATES", i, type(talents_candidates), len(talents_candidates) if talents_candidates else 0, flush=True)
                            for j in range(0, 6):
                                talent,talent_condition,talent_description = [None]*3
                                if talents_candidates and len(talents_candidates) > j:
                                    talent = talents_candidates[j].get("name")
                                    unlock_condition = (
                                        talents_candidates[j - 1].get("unlockCondition", {})
                                        if j > 0
                                        else talents_candidates[j].get("unlockCondition", {})
                                    )
                                    phase = unlock_condition.get("phase")
                                    phase = mapper._apply_value_map("character_table", "phase", phase)
                                    requiredPotentialRank = talents_candidates[j].get("requiredPotentialRank", 0)
                                    talent_condition = PHASE(phase) + \
                                                       potential[str(requiredPotentialRank)] if (phase != "PHASE_0" or requiredPotentialRank != 0) else "初始携带"
                                    talent_description = process_description(
                                        talents_candidates[j].get("description"),
                                        trait_candidates, rich_styles,term_descriptionDict)
                                summon.append(
                                    f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"提升后" if j>=1 else ""}={talent if talent  else ""}")
                                summon.append(
                                    f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"解锁" if j<1 else ""}{"提升" if j>=1 else ""}条件={talent_condition if talent_condition is not None and talent else ""}")
                                summon.append(
                                    f"|天赋{i}{f"第{j}次" if j > 1 else ""}{"提升后" if j>=1 else ""}描述={talent_description if talent_description else ""}")
                            summon.append(f"|天赋{i}备注=")
                            summon.append(f"|天赋{i}攻击范围=")
                        except Exception as e:
                            print(f"TALENT_BLOCK_ERROR i={i} id={Id}: {e}", flush=True)
                            traceback.print_exc()
                            raise
                    for i in range(1, 4):
                        skill_id = mapper.get_data_safe('character_table', f"{is_not_none_familiar}.skills[{i-1}].skillId") if is_not_none_familiar else None
                        summon_skill_data = mapper.get_data_safe('skill_table', f'{skill_id}.levels') if skill_id else None
                        summon_skill_name = summon_skill_data[i-1].get('name') if summon_skill_data and len(summon_skill_data) > i-1 else None
                        skill_icon = summon_skill_data[i-1].get('icon') if summon_skill_data and len(summon_skill_data) > i-1 else None
                        is_null_skill_icon = skill_icon if summon_skill_name != skill_icon else summon_skill_name
                        skill_range = summon_skill_data[i-1].get('rangeId') if summon_skill_data and len(summon_skill_data) > i-1 else None
                        sp_data = summon_skill_data[i-1].get('spData', {}) if summon_skill_data and len(summon_skill_data) > i-1 else {}
                        skill_recover_type = sp_data.get('spType')
                        skill_trigger_type = summon_skill_data[i-1].get('skillType') if summon_skill_data and len(summon_skill_data) > i-1 else None
                        skill_type = summon_skill_data[i-1].get('durationType') if summon_skill_data and len(summon_skill_data) > i-1 else None
                        summon.append(f"|技能{i}产生={summon_skill_name}")
                        summon.append(f"|技能{i}={summon_skill_name if summon_skill_name != None else ""}")
                        summon.append(f"|skillId{i}={skill_id if skill_id != None else ""}")
                        summon.append(f"|skillIcon{i}={"" if is_null_skill_icon == None else skill_icon}")
                        summon.append(
                            f"|技能{i}类型={mapping_skill_type[skill_type] if skill_type != None and skill_type != "NONE" else ""}")
                        summon.append(f"|技能{i}攻击范围={skill_range if skill_range != None else ""}")
                        summon.append(
                            f"|技能{i}回复类型={skillType[skill_recover_type] if skillType.get(skill_recover_type) else ""}")
                        summon.append(
                            f"|技能{i}触发类型={skillTriggerType[skill_trigger_type] if skillTriggerType.get(skill_trigger_type) else ""}")
                        for j in range(1, 11):
                            level_data = summon_skill_data[j-1] if summon_skill_data and len(summon_skill_data) > j-1 else {}
                            sp_data = level_data.get('spData', {})
                            skill_comsume = sp_data.get('spCost')
                            skill_init = sp_data.get('initSp')
                            skill_consistent_time = level_data.get('duration')
                            if skill_consistent_time is not None:
                                rounded = round(skill_consistent_time)  # 四舍五入到最近整数
                                if abs(skill_consistent_time - rounded) < 1e-10:  # 如果误差小于极小阈值
                                    skill_consistent_time = int(rounded)  # 转换为整数
                            skill_description = level_data.get('description')
                            blackboard = level_data.get('blackboard', [])
                            summon.append(
                                f"|技能{i}描述{j}={process_description(skill_description, trait_candidates, rich_styles,term_descriptionDict, blackboard).replace(r"\n", "<br/>")}")
                            summon.append(f"|技能{i}技力消耗{j}={skill_comsume if skill_comsume != None else ""}")
                            summon.append(f"|技能{i}初始技力{j}={skill_init if skill_init != None else ""}")
                            summon.append(
                                f"|技能{i}持续时间{j}={skill_consistent_time if skill_consistent_time != None and skill_consistent_time != None else ""}")
                        summon.append(f"|技能{i}备注=")
                    summon.append("}}")
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
                    summon.clear()
                    summon_array.add(summon_name)
            suffix ={
                1:"",
                2:"提升后",
                3:"再次提升后"
            }
            infrastructure_room={
                "CONTROL":"控制中枢",
                "POWER":"发电站",
                "MANUFACTURE":"制造站",
                "TRADING":"贸易站",
                "WORKSHOP":"加工站",
                "TRAINING":"训练室",
                "DORMITORY":"宿舍",
                "HIRE":"办公室",
                "MEETING":"会客室"
            }
            temp_number = 0 #计算基建技能id，基建技能图标
            for i in range(1,3):
                buff_data_list = mapper.get_data_safe(
                    'building_data',
                    f'chars.{Id}.buffChar[{i - 1}].buffData',
                    default=[]
                ) or []
                for j in range(1, 4):
                    buff_data = buff_data_list[j - 1] if len(buff_data_list) >= j else {}
                    infrastructure_skill_Id = buff_data.get('buffId')
                    infrastructure_skill_name = mapper.get_data_safe(
                        'building_data', f'buffs.{infrastructure_skill_Id}.buffName') if infrastructure_skill_Id else None
                    infrastructure_skill_icon = mapper.get_data_safe(
                        'building_data', f'buffs.{infrastructure_skill_Id}.skillIcon') if infrastructure_skill_Id else None
                    cond = buff_data.get('cond') or {}
                    infrastructure_skill_level = cond.get('level')
                    infrastructure_skill_phase = cond.get('phase')
                    infrastructure_skill_condiction2 = (f"{PHASE(infrastructure_skill_phase)}" +
                                                        (f"、等级{infrastructure_skill_level}" if (infrastructure_skill_level!=None and infrastructure_skill_level > 1) else "")) if ((infrastructure_skill_level!=None and infrastructure_skill_level > 1) or infrastructure_skill_phase != "PHASE_0") else "初始携带"
                    infrastructure_skill_room = mapper.get_data_safe(
                        'building_data', f'buffs.{infrastructure_skill_Id}.roomType') if infrastructure_skill_Id else None
                    infrastructure_skill_description = mapper.get_data_safe(
                        'building_data', f'buffs.{infrastructure_skill_Id}.description') if infrastructure_skill_Id else None

                    temp_number += 1
                    parts.append(f"|基建技能{i}{suffix[j]}={infrastructure_skill_name if infrastructure_skill_name!=None else ""}")
                    parts.append(f"|基建技能id{temp_number}={infrastructure_skill_Id if infrastructure_skill_Id!=None else ""}")
                    parts.append(f"|基建技能图标{temp_number}={infrastructure_skill_icon if infrastructure_skill_icon!=None else ""}")
                    parts.append(f"|基建技能{i}{suffix[j][:-1]}{"条件" if j>1 else "解锁"}={Infrastructure_condition[infrastructure_skill_condiction2] if infrastructure_skill_condiction2 != None and infrastructure_skill_name != None else ""}")
                    parts.append(f"|基建技能{i}{suffix[j]}设施={infrastructure_room[infrastructure_skill_room] if infrastructure_skill_room!=None else ""}")
                    parts.append(f"|基建技能{i}{suffix[j]}效果={process_description(infrastructure_skill_description,trait_candidates,rich_styles,term_descriptionDict) if infrastructure_skill_description!=None else ""}")

            drawer = build_drawer_from_skins(mapper, Id)
            if not drawer.strip():
                other_keys = [k for k in mapper.config["data_sources"].keys() if k != mapper.current_data_sources]
                for alt in other_keys:
                    with mapper.temporary_source_group(alt):
                        drawer = build_drawer_from_skins(mapper, Id)
                        if drawer.strip():
                            break
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
            birthday, birthday2, month, day, sex, people, birthplace, height, height2, is_infection, design_sex, experience, experience_name, manufacturer, birthplace2, produce_time, weight, repair_report, infection_status, objective_eesume, physic_intensity, battlefield_flexible, physiology_tolerance, tactic_plan, battle_technic, source_stone_skill_adaptability, diagnosis_analysis, file_one, file_two, file_three, file_four, promotion_record,promotion_archive,maximum_speed,hill_climbing_ability,braking_efficiency,pass_rate,endurance,structural_stability= [None]*39
            secret_record = []
            char_Text = mapper.get_data_safe('handbook_info_table', f'handbookDict.{Id}') or {}
            for story_idx, storyText in enumerate(char_Text.get("storyTextAudio") or []):
                mapper.add_mapping('handbook_info_table', 'handbook_char_id', Id)
                mapper.add_mapping('handbook_info_table', 'handbook_story_index', str(story_idx))
                if storyText["storyTitle"] == "基础档案":
                    if "【代号】" in safe_get(storyText,["stories",0,"storyText"]) or "【姓名】" in safe_get(storyText,["stories",0,"storyText"]):
                        birthday_data = re.search(r"【([^】]*)】(\d+)月(\d+)日",safe_get(storyText,["stories",0,"storyText"]))#生日
                        birthday = (f"{birthday_data.group(2)}月{birthday_data.group(3)}日") if birthday_data and birthday_data.group(1)=="生日" else ""
                        birthday2 = (
                            f"{birthday_data.group(2)}月{birthday_data.group(3)}日") if birthday_data and birthday_data.group(
                            1) == "出厂日" else ""

                        month = f"{birthday_data.group(2)}" if birthday_data else ""
                        day = f"{birthday_data.group(3)}" if birthday_data else ""
                        if not birthday_data:
                            birthday_data =re.search(r"【生日】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                            birthday = (
                                f"{birthday_data.group(1)}") if birthday_data else ""
                        sex_data = re.search(r"【性别】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        sex = sex_data[1] if sex_data else ""
                        people_data = re.search(r"【种族】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        people = people_data[1] if people_data else ""
                        birthplace_data = re.search(r"【出身地】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        birthplace = birthplace_data[1] if birthplace_data else ""
                        birthplace_data = re.search(r"【产地】(.+)\n", safe_get(storyText, ["stories", 0,"storyText"])) if birthplace_data == None else None
                        birthplace2 = birthplace_data[1] if birthplace_data else ""
                        height_data = re.search(r"【身高】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        height = height_data[1] if height_data else ""
                        height_data = re.search(r"【高度】(.+)\n", safe_get(storyText, ["stories", 0,"storyText"])) if height_data == None else None
                        height2 = height_data[1] if height_data else ""
                        infection_status_data = re.search(r"【矿石病感染情况】\n(.+)",safe_get(storyText,["stories",0,"storyText"]))
                        infection_status = infection_status_data[1] if infection_status_data else ""
                        if "确认为感染者" in infection_status:
                            is_infection="是"
                        else:
                            is_infection="否"
                        experience_data= re.search(r"【(.*?)经验】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        experience = experience_data[2] if experience_data else ""
                        experience_name = (experience_data[1]+"经验") if experience_data else ""
                        design_sex_data = re.search(r"【设定性别】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        design_sex = design_sex_data[1] if design_sex_data else ""
                        weight_data= re.search(r"【重量】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        weight = weight_data[1] if weight_data else ""
                        repair_report_data=re.search(r"【维护检测报告】\n(.+)",safe_get(storyText,["stories",0,"storyText"]))
                        repair_report_data=re.search(r"【维护检测情况】\n(.+)",safe_get(storyText,["stories",0,"storyText"])) if repair_report_data==None else repair_report_data
                        repair_report = repair_report_data[1] if repair_report_data else ""
                        manufacturer_data = re.search(r"【制造商】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        manufacturer = manufacturer_data[1] if manufacturer_data else ""
                        produce_time_data = re.search(r"【出厂时间】(.+)\n",safe_get(storyText,["stories",0,"storyText"]))
                        produce_time = produce_time_data[1] if produce_time_data else ""
                if storyText["storyTitle"] == "客观履历":
                    objective_eesume = process_description(safe_get(storyText,["stories",0,"storyText"]),trait_candidates, rich_styles)
                if storyText["storyTitle"] == "综合体检测试":
                    physic_intensity_data = re.search(r"【物理强度】(.+)\n", safe_get(storyText,
                                                                                    ["stories", 0,
                                                                                     "storyText"]))
                    physic_intensity = physic_intensity_data[1] if physic_intensity_data else ""
                    battlefield_flexible_data = re.search(r"【战场机动】(.+)\n", safe_get(storyText,
                                                                                        [ "stories", 0,
                                                                                         "storyText"]))
                    battlefield_flexible = battlefield_flexible_data[1] if battlefield_flexible_data else ""
                    physiology_tolerance_data = re.search(r"【生理耐受】(.+)\n", safe_get(storyText,
                                                                                        [ "stories", 0,
                                                                                         "storyText"]))
                    physiology_tolerance = physiology_tolerance_data[1] if physiology_tolerance_data else ""
                    tactic_plan_data = re.search(r"【战术规划】(.+)\n",
                                                 safe_get(storyText, [ "stories", 0, "storyText"]))
                    tactic_plan = tactic_plan_data[1] if tactic_plan_data else ""
                    battle_technic_data = re.search(r"【战斗技巧】(.+)\n",
                                                    safe_get(storyText, [ "stories", 0, "storyText"]))
                    battle_technic = battle_technic_data[1] if battle_technic_data else ""
                    source_stone_skill_adaptability_data = re.search(r"【源石技艺适应性】(.+)", safe_get(storyText,
                                                                                                       [
                                                                                                        "stories", 0,
                                                                                                        "storyText"]))
                    source_stone_skill_adaptability = source_stone_skill_adaptability_data[
                        1] if source_stone_skill_adaptability_data else ""
                if storyText["storyTitle"] == "临床诊断分析":
                    unLockType = mapper.get_data_safe(
                        'handbook_info_table', 'handbook_story_unlock_type', default=None)
                    story_txt = mapper.get_data_safe(
                        'handbook_info_table', 'handbook_story_text', default='') or ''
                    un_lock_param = mapper.get_data_safe(
                        'handbook_info_table', 'handbook_story_unlock_param', default='') or ''
                    if unLockType == "DIRECT":
                        diagnosis_analysis = story_txt.replace("\n", "<br/>")
                    elif unLockType == "FAVOR":
                        diagnosis_analysis = story_txt.replace("\n", "<br/>")
                    elif unLockType == "AWAKE":
                        parts_param = (un_lock_param or "").split(";")
                        p0 = parts_param[0] if len(parts_param) > 0 else ""
                        p1 = parts_param[1] if len(parts_param) > 1 else ""
                        diagnosis_analysis = (
                            f"{p0}等级{p1}<br/>{story_txt.replace(chr(10), '<br/>')}")
                    else:
                        diagnosis_analysis = ""

                if storyText["storyTitle"] == "档案资料一":
                    file_one=safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                elif storyText["storyTitle"] == "档案资料二":
                    file_two = safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                elif storyText["storyTitle"] == "档案资料三":
                    file_three = safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                elif storyText["storyTitle"] == "档案资料四":
                    file_four = safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                elif storyText["storyTitle"] == "晋升记录":
                    promotion_record = safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                elif "升变档案" in storyText["storyTitle"]:
                    promotion_archive = safe_get(storyText, [ "stories", 0, "storyText"]).replace("\n","<br/>")
                if storyText["storyTitle"] == "综合性能检测结果":
                    maximum_speed_data= re.search(r"/【最高速度】(.+)\n/",safe_get(storyText,["stories",0,"storyText"]))
                    maximum_speed= maximum_speed_data[1] if maximum_speed_data else ""
                    hill_climbing_ability_data = re.search(r"/【爬坡能力】(.+)\n/",safe_get(storyText,["stories",0,"storyText"]))
                    hill_climbing_ability= hill_climbing_ability_data[1] if hill_climbing_ability_data else ""
                    braking_efficiency_data = re.search(r"/【制动效能】(.+)\n/",safe_get(storyText,["stories",0,"storyText"]))
                    braking_efficiency= braking_efficiency_data[1] if braking_efficiency_data else ""
                    pass_rate_data = re.search(r"/【通过性】(.+)\n/",safe_get(storyText,["stories",0,"storyText"]))
                    pass_rate= pass_rate_data[1] if pass_rate_data else ""
                    endurance_data = re.search(r"/【续航】(.+)\n/",safe_get(storyText,["stories",0,"storyText"]))
                    endurance= endurance_data[1] if endurance_data else ""
                    structural_stability_data = re.search(r"/【结构稳定性】(.+)/",safe_get(storyText,["stories",0,"storyText"]))
                    structural_stability= structural_stability_data[1] if structural_stability_data else ""
                for i in range(1,4):
                    record= [safe_get(char_Text, ["handbookAvgList", i - 1, "storySetName"]),
                             safe_get(char_Text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]),
                             safe_get(char_Text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]),
                             safe_get(char_Text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam2"]),
                             safe_get(char_Text, ["handbookAvgList", i - 1, "unlockParam", 1, "unlockParam1"]),
                             safe_get(char_Text, ["handbookAvgList", i - 1, "unlockParam", 0, "storyIntro"])]
                    secret_record.append(record)
            parts.append(f"|生日={birthday}")
            parts.append(f"|出厂日={birthday2}")
            parts.append(f"|月={month}")
            parts.append(f"|日={day}")
            parts.append(f"|性别={sex}")
            parts.append(f"|真实姓名=")
            parts.append(f"|职能=")
            parts.append(f"|种族={people}")
            parts.append(f"|出身={birthplace}")
            parts.append(f"|身高={height}")
            parts.append(f"|高度={height2}")
            parts.append(f"|是否感染={is_infection}")
            parts.append(f"|设定性别={design_sex}")
            parts.append(f"|专精={value["专精"]}")
            parts.append(f"|经验={experience}<!--类似十年这样的文本-->")
            parts.append(f"|经验名称={experience_name}<!--不填写即显示战斗经验-->")
            parts.append(f"|制造商={manufacturer}")
            parts.append(f"|产地={birthplace2}")
            parts.append(f"|出厂时间={produce_time}")
            parts.append(f"|重量={weight}")
            parts.append(f"|维护检测报告={repair_report}")
            parts.append(f"|矿石病毒感染情况={infection_status}")
            parts.append(f"|客观履历={objective_eesume}")
            parts.append(f"|物理强度={physic_intensity}")
            parts.append(f"|战场机动={battlefield_flexible}")
            parts.append(f"|生理耐受={physiology_tolerance}")
            parts.append(f"|战术规划={tactic_plan}")
            parts.append(f"|战斗技巧={battle_technic}")
            parts.append(f"|源石技艺适应性={source_stone_skill_adaptability}")

            parts.append(f"|临床诊断分析={diagnosis_analysis}")
            parts.append(f"|档案资料一={file_one}")
            parts.append(
                f"|档案资料二={file_two}")
            parts.append(
                f"|档案资料三={file_three}")
            parts.append(
                f"|档案资料四={file_four}")
            parts.append(
                f"|晋升记录={promotion_record}")
            parts.append(f"|升变档案={promotion_archive if promotion_archive else ""}")
            parts.append(f"|档案资料五={value["宣传介绍"]}")
            parts.append(f"|档案资料五标题=宣传介绍")
            parts.append(f"|最高速度={maximum_speed if maximum_speed else ""}")
            parts.append(f"|爬坡能力={hill_climbing_ability if hill_climbing_ability else ""}")
            parts.append(f"|制动效能={braking_efficiency if braking_efficiency else ""}")
            parts.append(f"|通过性={pass_rate if pass_rate else ""}")
            parts.append(f"|续航={endurance if endurance else ""}")
            parts.append(f"|结构稳定性={structural_stability if structural_stability else ""}")
            parts.append(f"|体检描述=")
            for i in range(1,4):
                parts.append(f"|干员密录{i}={secret_record[i][0] if secret_record[i][0] else ""}")
                parts.append(f"|干员密录{i}解锁条件="+((f"[[文件: icon_e{secret_record[i][1]}_need.png|20px|link=|class=invert-color]]提升至精英阶段{secret_record[i][2]}等级{secret_record[i][3]}<br/>[[文件:icon_信赖.png|20px|link=|class=invert-color]]提升信赖至{secret_record[i][4]}") if secret_record[i][1] else ""))
                parts.append(f"|干员密录{i}描述={secret_record[i][5] if secret_record[i][5] else ""}")
                parts.append(f"|干员密录{i}述描视频=")

            parts.append(f"|悖论模拟标题=")

            map_language={}
            for language, language_name in (mapper.get_data_safe('charword_table', 'voiceLangTypeDict') or {}).items():
                if language == "JP":
                    map_language["JP"]=""
                    continue
                type_name = language_name["name"][0] if language_name["name"] !="中文-方言" else "方"
                map_language[language]=type_name
            for language, cv in (mapper.get_data_safe('charword_table', f'voiceLangDict.{Id}.dict') or {}).items():
                parts.append(f"|CV{map_language[language]}={"，".join([cvName for cvName in cv["cvName"]])}")
            parts.append("}}")
            main_wikitext = "\n".join(parts)

            if _wiki_yes_no(
                f"干员{name}页面确定创建(Y/N):",
                wiki_key="wiki_operator_page",
                wiki_flags=wiki_flags,
                interactive=interactive,
                wiki_confirm=wiki_confirm,
            ):
                site_obj = get_site()
                if site_obj is not None:
                    create_site_page(site_obj, f"{name}", "\n".join(parts), wiki_use_test_page)
                else:
                    print("Wiki未连接，跳过创建干员页面")

            parts.clear()
            parts.append("{{干员语音/套")
            parts.append(f"|所属干员={name}")
            parts.append(f"|所属皮肤=默认")
            parts.append(f"|语言=中文-普通话")
            for number,description in VOICE_MAP.items():
                voice_text = mapper.get_data_safe(
                    'charword_table', f'charWords.{Id}_CN_{number}.voiceText', default='') or ''
                if "Dr.{@nickname}" in voice_text:
                    voice_text = voice_text.replace("Dr.{@nickname}", "博士")
                parts.append(f"|{description}={voice_text}")
            parts.append("}}")
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
            if _wiki_yes_no(
                f"干员{name}语音页面确定创建(Y/N):",
                wiki_key="wiki_voice_page",
                wiki_flags=wiki_flags,
                interactive=interactive,
                wiki_confirm=wiki_confirm,
            ):
                site_obj = get_site()
                if site_obj is not None:
                    create_site_page(site_obj, f"{name}/默认/中文-普通话", "\n".join(parts), wiki_use_test_page)
                else:
                    print("Wiki未连接，跳过创建语音页面")
            parts.clear()
            portrait_resp = requests.get(
                f"https://web.hycdn.cn/arknights/game/assets/char/portrait/{Id}.png",
                headers=headers,
            )
            if portrait_resp.status_code == 200:
                file_obj = io.BytesIO(portrait_resp.content)
                site_obj = get_site()
                if site_obj is not None:
                    if _wiki_yes_no(
                        f"干员{name}半身像确定上传(Y/N):",
                        wiki_key="wiki_portrait",
                        wiki_flags=wiki_flags,
                        interactive=interactive,
                        wiki_confirm=wiki_confirm,
                    ):
                        upload_result = site_obj.upload(file_obj, filename=f"{name}06.png")
                        if upload_result["result"] == "Warning":
                            print(upload_result)
                            print("再次尝试")
                            upload_result = site_obj.upload(file_obj, filename=f"{name}06.png")
                        print("上传结果:", upload_result)
                else:
                    print("site创建失败")
            else:
                print(f"干员{name}半身像,获取失败")
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
