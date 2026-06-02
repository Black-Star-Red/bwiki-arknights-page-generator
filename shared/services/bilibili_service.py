"""Bilibili related service functions for character supplementary data."""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from bs4 import BeautifulSoup
import json
import requests

def slice_json_object_after_key(text: str, key: str = "initialData") -> dict:
    # 常见：\"initialData\":{  或  "initialData":{
    markers = [f'\\"{key}\\":{{', f'"{key}":{{']
    start_brace = -1
    for m in markers:
        pos = text.find(m)
        if pos != -1:
            start_brace = text.find("{", pos)
            break
    if start_brace == -1:
        # 兜底：只找 key，再找后面第一个 {
        pos = text.find(key)
        if pos == -1:
            raise ValueError(f"找不到 {key}")
        start_brace = text.find("{", pos)
    if start_brace == -1:
        raise ValueError(f"{key} 后没有 {{")
    depth = 0
    for i in range(start_brace, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                blob = text[start_brace : i + 1]
                return json.loads(blob)
    raise ValueError("括号不配对，可能截断了")
def get_dynamic_id(name: str) -> str:
    """从鹰角官网编译表查干员动态 cid；失败时返回空串，不抛异常。"""
    try:
        response = requests.get("https://ak.hypergryph.com/archive/dynamicCompile", timeout=15)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.content, "html.parser")
        scripts = [
            s.string
            for s in soup.find_all("script")
            if s.string and "__next_f.push" in s.string and "initialData" in s.string
        ]
        if not scripts:
            return ""
        text = scripts[0].replace("\\", "")
        text = text if isinstance(text, str) else (scripts[0].string or "")
        data = slice_json_object_after_key(text)
        for i in data.get("0", {}).get("list", []):
            if i.get("name") == name:
                return str(i.get("cid") or "")
        return ""
    except Exception:
        return ""


def _toolbox_package_root() -> Path:
    """`arknights_toolbox` 包目录（本文件位于 shared/services/）。"""
    return Path(__file__).resolve().parents[2]


def operator_photo_dir() -> Path:
    """B 站动态配图与 OCR 用图目录：包内 `photo/`。"""
    return _toolbox_package_root() / "photo"


def fetch_user_dynamics(
    mid: str,
    headers: dict[str, str],
    offset: str | None = None,
    *,
    log_warning: Callable[[str, Any], None] | None = None,
):
    """Fetch user dynamics from Bilibili API."""
    api_url = "https://api.bilibili.com/x/polymer/web-dynamic/desktop/v1/feed/space"
    params = {
        "host_mid": mid,
        "offset": "" if offset is None else offset,
    }
    last_message = ""

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
                    last_message = str(data.get("message") or "")
                    if data.get("code") == 0:
                        payload = data.get("data")
                        if isinstance(payload, dict):
                            items = payload.get("items")
                            if not isinstance(items, list) or len(items) == 0:
                                msg = (
                                    f"B 站动态 feed 为空 mid={mid} offset={offset or ''} "
                                    f"has_more={payload.get('has_more')} api_message={last_message}"
                                )
                                if log_warning:
                                    log_warning("%s", msg)
                                else:
                                    print(msg)
                            return payload
                    print(f"API错误: {data.get('message')}")
                except ValueError as e:
                    print(f"请求失败: JSON解析失败 {e}; 响应前200字符: {text[:200]}")
        except requests.RequestException as e:
            print(f"请求失败: {e}")

        sleep_s = (2**attempt) * 0.5 + random.random() * 0.2
        time.sleep(sleep_s)
    if log_warning:
        log_warning(
            "B 站动态请求失败 mid=%s offset=%s last_message=%s",
            mid,
            offset or "",
            last_message,
        )
    return None


def _iter_dynamic_modules(item: dict) -> list[dict]:
    """B 站 polymer 动态里 modules 可能是 list，也可能是 dict。"""
    raw = item.get("modules")
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _dynamic_pub_ts(item: dict) -> int | None:
    """从 polymer 动态条目解析发布时间（Unix 秒）。"""
    for mod in _iter_dynamic_modules(item):
        author = mod.get("module_author")
        if not isinstance(author, dict):
            continue
        ts = author.get("pub_ts")
        if ts is not None:
            try:
                return int(ts)
            except (TypeError, ValueError):
                continue
    basic = item.get("basic")
    if isinstance(basic, dict):
        for key in ("pub_ts", "pub_time"):
            ts = basic.get(key)
            if ts is not None:
                try:
                    return int(ts)
                except (TypeError, ValueError):
                    pass
    return None


# 干员预告常早于活动 startTime 发布，B 站筛选时向前放宽
BILIBILI_PRE_START_SECONDS = 21 * 86400


def _effective_dynamic_start(dynamic_start_ts: int | None) -> int | None:
    if dynamic_start_ts is None:
        return None
    return dynamic_start_ts - BILIBILI_PRE_START_SECONDS


def _collect_rich_text_nodes_with_source(item: dict) -> list[tuple[dict, bool]]:
    """收集 rich_text_nodes；(node, from_forward) 标记是否来自 dyn_forward 内嵌动态。"""
    nodes: list[tuple[dict, bool]] = []

    def walk(dyn_item: dict, *, from_forward: bool) -> None:
        for mod in _iter_dynamic_modules(dyn_item):
            desc = mod.get("module_desc")
            if isinstance(desc, dict):
                for node in desc.get("rich_text_nodes") or []:
                    if isinstance(node, dict) and node.get("orig_text"):
                        nodes.append((node, from_forward))
            dyn = mod.get("module_dynamic")
            if not isinstance(dyn, dict):
                continue
            fwd = dyn.get("dyn_forward")
            if isinstance(fwd, dict):
                nested = fwd.get("item")
                if isinstance(nested, dict):
                    walk(nested, from_forward=True)

    walk(item, from_forward=False)
    return nodes


def _collect_rich_text_nodes(item: dict) -> list[dict]:
    """从 module_desc 收集 rich_text_nodes（含 dyn_forward 内嵌原动态）。"""
    return [node for node, _ in _collect_rich_text_nodes_with_source(item)]


# 活动公告长文中 SideStory 常在第二行，不能用 match 要求全文开头
_SIDE_STORY_IN_TEXT_RE = re.compile(r"SideStory「([^」]+)」")
# 排除维护公告里的「修复主题曲「二次呼吸」关卡」等描述性用语
_MAIN_THEME_ACTIVITY_RE = re.compile(r"(?<!修复)主题曲「([^」]+)」(?:篇章|限时|活动|即将|开启)")


def _extract_side_story_from_text(text: str) -> str | None:
    """从单段 orig_text 解析活动上下文（SideStory / 主题曲活动）。"""
    text = (text or "").strip()
    if not text:
        return None
    m = _SIDE_STORY_IN_TEXT_RE.search(text)
    if m:
        return m.group(0)
    m = _MAIN_THEME_ACTIVITY_RE.search(text)
    if m:
        return f"主题曲「{m.group(1)}」"
    return None


def _extract_side_story_from_nodes(nodes: list[dict]) -> str | None:
    """从单条动态的正文节点解析 SideStory / 主题曲（每条动态独立，不跨条复用）。"""
    for node in nodes:
        found = _extract_side_story_from_text(node.get("orig_text") or "")
        if found:
            return found
    return None


def _activity_reward_obtain_path(
    side_story: str | None,
    acquisition_method: dict[str, str],
) -> str:
    """活动奖励干员获取途径：仅当本动态含主题曲行时用主题曲获得。"""
    if side_story and side_story.startswith("主题曲"):
        return "主题曲获得 / "
    prefix = acquisition_method.get("活动奖励干员", "活动获取、【")
    if side_story:
        l = side_story.find("「")
        r = side_story.rfind("」")
        if l != -1 and r != -1 and r > l:
            return prefix + side_story[l + 1 : r] + "】活动获取"
    return "活动获取"


def _dynamic_is_collaboration(item: dict, collab_activity_re: re.Pattern[str] | None) -> bool:
    """动态含【明日方舟 × …】联动头（文首或长文公告首行）。"""
    if collab_activity_re is None:
        return False
    for node in _collect_rich_text_nodes(item):
        text = (node.get("orig_text") or "").strip()
        if not text:
            continue
        if collab_activity_re.match(text):
            return True
        first_line = text.split("\n", 1)[0].strip()
        if first_line and collab_activity_re.match(first_line):
            return True
    return False


def _first_dyn_draw_src(item: dict) -> str | None:
    """从 module_dynamic.dyn_draw 取首张配图 URL（含转发内嵌动态）。"""
    for mod in _iter_dynamic_modules(item):
        dyn = mod.get("module_dynamic")
        if not isinstance(dyn, dict):
            continue
        draw = dyn.get("dyn_draw")
        if isinstance(draw, dict):
            for pic in draw.get("items") or []:
                if isinstance(pic, dict) and pic.get("src"):
                    return str(pic["src"])
        fwd = dyn.get("dyn_forward")
        if isinstance(fwd, dict):
            nested = fwd.get("item")
            if isinstance(nested, dict):
                found = _first_dyn_draw_src(nested)
                if found:
                    return found
    return None


# 联动总览公告中的卡池行，如「二、【幽境狩人】限时寻访开启」
_COLLAB_GACHA_POOL_RE = re.compile(r"【([^】]+)】限时寻访")
# 专栏：★★★★★★：凯尔希·思衡托 [限定] \ 可露希尔（占6★…）—— 无 [限定] 者为池内 UP 非常驻
_LIMITED_OPERATOR_IN_ARTICLE_RE = re.compile(r"([^\\★\n：:]+?)\s*\[限定\]")


def _extract_limited_operators_from_article_summary(summary: str) -> set[str]:
    """从限定寻访专栏摘要解析带 [限定] 标记的干员名。"""
    names: set[str] = set()
    for m in _LIMITED_OPERATOR_IN_ARTICLE_RE.finditer(summary or ""):
        name = (m.group(1) or "").strip()
        if name:
            names.add(name)
    return names


def _is_limited_operator_in_pool(name: str, limited_names: set[str]) -> bool:
    """干员是否在该卡池专栏的 [限定] 名单内（允许与预告名略有差异）。"""
    name = (name or "").strip()
    if not name or not limited_names:
        return False
    if name in limited_names:
        return True
    return any(
        name in lim or lim in name for lim in limited_names if lim
    )


def _extract_collab_gacha_pools_from_nodes(nodes: list[dict]) -> set[str]:
    pools: set[str] = set()
    for node in nodes:
        for m in _COLLAB_GACHA_POOL_RE.finditer(node.get("orig_text") or ""):
            pools.add(m.group(1))
    return pools


def _obtain_path_for_gacha_pool(
    gacha_pool: str,
    acquisition_method: dict[str, str],
    *,
    collab: bool = False,
    side_story: str | None = None,
) -> str:
    """按卡池名生成获取途径；未在 ACQUISITION_METHOD 中的命名池视为限定寻访。"""
    if collab and gacha_pool:
        return f"联动、联动寻访、【{gacha_pool}】寻访"
    if gacha_pool == "活动奖励干员":
        return _activity_reward_obtain_path(side_story, acquisition_method)
    mapped = acquisition_method.get(gacha_pool)
    if mapped is not None:
        return mapped
    if gacha_pool == "新增干员":
        return acquisition_method.get("新增干员", "标准寻访")
    if gacha_pool:
        return f"限定寻访、【{gacha_pool}】限定寻访"
    return acquisition_method.get("新增干员", "标准寻访")


def _dynamic_in_activity_window(
    pub_ts: int | None,
    *,
    dynamic_start_ts: int | None,
    dynamic_end_ts: int | None,
) -> str:
    """
    判断动态是否在活动时间内。
    返回: "in" | "after" | "before" | "unknown"
    """
    if dynamic_start_ts is None and dynamic_end_ts is None:
        return "in"
    if pub_ts is None:
        return "unknown"
    if dynamic_end_ts is not None and pub_ts > dynamic_end_ts:
        return "after"
    if dynamic_start_ts is not None and pub_ts < dynamic_start_ts:
        return "before"
    return "in"


def fetch_character_supplementary_data(
    mid: str,
    headers: dict[str, str],
    *,
    announce_line_re: re.Pattern[str],
    acquisition_method: dict[str, str],
    collab_activity_re: re.Pattern[str] | None = None,
    ocr_specialization: Callable[[str], str],
    log_warning: Callable[[str, Any], None],
    log_info: Callable[[str, Any], None],
    character_num: int = 3,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
) -> dict[str, dict[str, str]]:
    """Fetch supplementary character data from Bilibili APIs."""
    result: dict[str, dict[str, str]] = {}
    diag: dict[str, int] = {
        "pages": 0,
        "items_total": 0,
        "skipped_exceptions": 0,
        "win_after": 0,
        "win_in": 0,
        "win_before": 0,
        "win_unknown": 0,
        "announce_hits": 0,
    }
    eff_start = _effective_dynamic_start(dynamic_start_ts)
    collab_gacha_pools: set[str] = set()
    url = "https://api.bilibili.com/x/space/article"
    params = {
        "mid": mid,
        "ps": 12,
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
        time.sleep((2**attempt) * 0.4 + random.random() * 0.2)

    pool_view: dict[str, list[str]] = {}
    pool_limited_ops: dict[str, set[str]] = {}
    if request is not None:
        try:
            req_json = request.json()
            articles = req_json.get("data", {}).get("articles", [])
        except ValueError as e:
            print(f"获取卡池失败: JSON解析失败 {e}; 响应前200字符: {request.text[:200]}")
            articles = []
        for article in articles:
            if "限定寻访" in article["title"]:
                data = [article["title"][1:8]]
                left = article["title"].find("【")
                right = article["title"].find("】")
                ltime = article["summary"].find("活动时间：")
                rtime = article["summary"].find("日")
                data.append(article["summary"][ltime + 5 : rtime + 1])
                pool_key = article["title"][left + 1 : right]
                pool_view[pool_key] = data
                pool_limited_ops[pool_key] = _extract_limited_operators_from_article_summary(
                    article.get("summary") or ""
                )
    else:
        print("获取卡池失败")

    print(pool_view)
    dynamics = fetch_user_dynamics(mid, headers, log_warning=log_warning)

    release_time = None
    time_filter = dynamic_start_ts is not None or dynamic_end_ts is not None
    if time_filter:
        log_info(
            "bilibili_dynamic_time_filter start=%s end=%s effective_start=%s (pre_%ss)",
            dynamic_start_ts,
            dynamic_end_ts,
            eff_start,
            BILIBILI_PRE_START_SECONDS,
        )
    while len(result.keys()) < character_num:
        if not dynamics or not isinstance(dynamics, dict):
            break
        diag["pages"] += 1
        items_page = dynamics.get("items") or []
        if not isinstance(items_page, list):
            break
        diag["items_total"] += len(items_page)
        reached_before_window = False
        for item in items_page:
            if time_filter:
                window = _dynamic_in_activity_window(
                    _dynamic_pub_ts(item),
                    dynamic_start_ts=eff_start,
                    dynamic_end_ts=dynamic_end_ts,
                )
                diag[f"win_{window}"] = diag.get(f"win_{window}", 0) + 1
                if window == "before":
                    reached_before_window = True
                    break
                if window == "after":
                    continue
            try:
                nodes_with_src = _collect_rich_text_nodes_with_source(item)
                nodes = [n for n, _ in nodes_with_src]
                photo_url = _first_dyn_draw_src(item)
                if not nodes or not photo_url:
                    continue
                is_collab = _dynamic_is_collaboration(item, collab_activity_re)
                if is_collab:
                    collab_gacha_pools |= _extract_collab_gacha_pools_from_nodes(nodes)
                side_story = _extract_side_story_from_nodes(nodes)
                for index, (node, from_forward) in enumerate(nodes_with_src):
                    text = node["orig_text"]
                    # 抽奖公示转发内嵌的旧干员预告（如「恭喜…中奖」+ 转发【承诺】//凯尔希）
                    if from_forward:
                        continue
                    if announce_line_re.match(text):
                        release_time = None
                        diag["announce_hits"] += 1
                        character: dict[str, Any] = {}
                        gacha_pool = text[text.find("【") + 1 : text.find("】")]
                        start = text.find("//")
                        end = text.find("\n", start)
                        name = text[start + 2 : end]
                        photo_path = operator_photo_dir() / f"{name}.jpg"
                        if not photo_path.exists():
                            photo = requests.get(photo_url, timeout=10)
                            photo_path.parent.mkdir(parents=True, exist_ok=True)
                            if photo.status_code == 200:
                                photo_path.write_bytes(photo.content)
                        try:
                            from .ocr_service import ocr_exec
                            character["专精"] = ocr_exec(str(photo_path))
                        except Exception:
                            character["专精"] = ""
                            log_warning("专精OCR失败，已降级为空 name=%s", name)
                        # character["专精"] = ""
                        print(character)
                        implementation_data = pool_view.get(gacha_pool)
                        in_collab_event = is_collab or bool(collab_gacha_pools)
                        named_collab_pool = bool(
                            gacha_pool
                            and gacha_pool not in ("新增干员", "活动奖励干员")
                            and (is_collab or gacha_pool in collab_gacha_pools)
                        )
                        collab_standard_pool = bool(
                            gacha_pool in ("新增干员", "活动奖励干员")
                            and in_collab_event
                        )
                        if named_collab_pool:
                            character["联动"] = True
                            character["联动卡池"] = gacha_pool
                            character["获取途径"] = _obtain_path_for_gacha_pool(
                                gacha_pool,
                                acquisition_method,
                                collab=True,
                            )
                            dynamic_id = get_dynamic_id(name)
                            if dynamic_id:
                                character["动态id"] = dynamic_id
                        elif collab_standard_pool:
                            character["联动"] = True
                            character["获取途径"] = _obtain_path_for_gacha_pool(
                                gacha_pool,
                                acquisition_method,
                                side_story=side_story,
                            )
                        elif implementation_data is not None:
                            if implementation_data[1] and implementation_data[1][0] == "0":
                                implementation_data[1] = implementation_data[1][1:]
                            release_time = implementation_data[1]
                            prefix = acquisition_method.get(implementation_data[0])
                            limited_in_pool = pool_limited_ops.get(gacha_pool, set())
                            if prefix is not None:
                                if not limited_in_pool or _is_limited_operator_in_pool(
                                    name, limited_in_pool
                                ):
                                    character["获取途径"] = (
                                        prefix + f"{gacha_pool}】限定寻访"
                                    )
                                    dynamic_id = get_dynamic_id(name)
                                    if dynamic_id:
                                        character["动态id"] = dynamic_id
                                else:
                                    # 卡池 UP 但专栏未标 [限定]，如承诺池中的可露希尔
                                    character["获取途径"] = acquisition_method.get(
                                        "新增干员", "标准寻访"
                                    )
                        else:
                            character["获取途径"] = _obtain_path_for_gacha_pool(
                                gacha_pool,
                                acquisition_method,
                                side_story=side_story,
                            )
                        if release_time:
                            character["实装日期"] = (
                                "[https://t.bilibili.com/"
                                + item["id_str"]
                                + "?spm_id_from=333.1387.0.0 "
                                + release_time
                                + "]"
                            )
                        else:
                            character["实装日期"] = (
                                "[https://t.bilibili.com/"
                                + item["id_str"]
                                + "?spm_id_from=333.1387.0.0 "
                                + datetime.now().strftime("%Y年%m月%d日")
                                + "]"
                            )
                        intro = text[text.rfind("_") + 2 :].rstrip("\n")
                        intro = intro.replace("\n", "<br/>\n")
                        character["宣传介绍"] = intro.replace("<br/>\n<br/>\n关注并转发本条动态，我们将抽取10位博士赠送【现金648元】一份。","")
                        result[name] = character
                        if len(result) >= character_num:
                            break
            except Exception:
                diag["skipped_exceptions"] += 1
                if len(result) >= character_num:
                    break
                continue
        if reached_before_window:
            break
        offset = dynamics.get("offset")
        if not offset:
            break
        dynamics = fetch_user_dynamics(mid, headers, offset, log_warning=log_warning)
    log_info("result:%s", result)
    if not result:
        log_warning(
            "supplementary_data_empty mid=%s pool_keys=%s pages=%s items_total=%s "
            "skipped_exceptions=%s win_after=%s win_in=%s win_before=%s win_unknown=%s "
            "announce_hits=%s — 若 items_total=0 请检查 config.cookies（含 SESSDATA）"
            "与 Referer；将回退数据库名单",
            mid,
            len(pool_view),
            diag["pages"],
            diag["items_total"],
            diag["skipped_exceptions"],
            diag.get("win_after", 0),
            diag.get("win_in", 0),
            diag.get("win_before", 0),
            diag.get("win_unknown", 0),
            diag.get("announce_hits", 0),
        )
    return result


__all__ = ["fetch_user_dynamics", "fetch_character_supplementary_data", "operator_photo_dir"]
