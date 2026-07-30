"""Bilibili related service functions for character supplementary data."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from bs4 import BeautifulSoup
import json
import requests
from shared.collab_supplementary import pick_collab_gacha_pool
from shared.utils.format_date import format_zh_ymd
from shared.services.hypergryph_settings import resolve_hypergryph_settings
from core.script_logging import log_info

# 活动公告长文中 SideStory 常在第二行，不能用 match 要求全文开头
_SIDE_STORY_IN_TEXT_RE = re.compile(r"SideStory「([^」]+)」")
# 联动总公告首行：【明日方舟 × …】「泡影苍霆」限时活动…
_COLLAB_EVENT_TITLE_RE = re.compile(r"「([^」]+)」(?:限时活动|活动关卡|活动)")
# 排除维护公告里的「修复主题曲「二次呼吸」关卡」等描述性用语
_MAIN_THEME_ACTIVITY_RE = re.compile(r"(?<!修复)主题曲「([^」]+)」(?:篇章|限时|活动|即将|开启)")
# 鹰角公告正文：活动时间：08月01日 …
_ACTIVITY_OPEN_RE = re.compile(
    r"(?:活动时间|关卡开放时间|开放时间)[：:]\s*"
    r"(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})日"
)


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


@dataclass
class BilibiliScanContext:
    """B 站扫描上下文：GUI 活动名优先，否则用 feed 内缓存的 SideStory / 联动卡池名。"""

    gui_activity_name: str | None = None
    # GUI 活动为 TYPE_MAINSS（如「相变临界」）时，活动/主题曲奖励干员用主题曲获取途径
    gui_activity_is_main_theme: bool = False
    # GUI 选中活动的 startTime（Unix 秒），无专栏日期时用于实装日（国内日历）
    gui_activity_start_ts: int | None = None
    gui_activity_end_ts: int | None = None
    collab_gacha_pool_pub_ts: dict[str, int] = field(default_factory=dict)

    cached_activity_name: str | None = None
    cached_side_story: str | None = None
    cached_main_theme_activity_name: str | None = None
    cached_collab_gacha_pools: set[str] = field(default_factory=set)
    # 发现阶段记下的干员名 -> 动态 id_str，供后续按名抓取时对齐
    discovered_dynamic_ids: dict[str, str] = field(default_factory=dict)
    discover_feed_pages: int | None = None




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


def _extract_collab_event_title_from_text(text: str) -> str | None:
    """从联动总公告等正文提取「活动名」（无 SideStory 前缀时）。"""
    text = (text or "").strip()
    if not text:
        return None
    m = _COLLAB_EVENT_TITLE_RE.search(text)
    if m:
        name = (m.group(1) or "").strip()
        return name or None
    return None


def _extract_collab_event_title_from_nodes(nodes: list[dict]) -> str | None:
    for node in nodes:
        found = _extract_collab_event_title_from_text(node.get("orig_text") or "")
        if found:
            return found
    return None


def _is_side_story_context(label: str | None) -> bool:
    return (label or "").strip().startswith("SideStory")


def refresh_scan_activity_cache(
    scan_ctx: BilibiliScanContext | None,
    nodes: list[dict],
    *,
    is_collab_dynamic: bool = False,
    pub_ts: int | None = None,
) -> None:
    """扫描 feed 时累积 SideStory 原文、活动名、联动池名（供后续预告动态共用）。"""
    if scan_ctx is None:
        return
    side_story = _extract_side_story_from_nodes(nodes)
    if (side_story or "").strip().startswith("主题曲"):
        name = _side_story_activity_name(side_story)
        if name:
            scan_ctx.cached_main_theme_activity_name = name
    elif _is_side_story_context(side_story):
        scan_ctx.cached_side_story = side_story
        name = _side_story_activity_name(side_story)
        if name:
            scan_ctx.cached_activity_name = name
    elif not _is_side_story_context(scan_ctx.cached_side_story):
        name = _extract_collab_event_title_from_nodes(nodes)
        if name and not scan_ctx.cached_activity_name:
            scan_ctx.cached_activity_name = name
    if is_collab_dynamic:
        pools = _extract_collab_gacha_pools_from_nodes(nodes)
        if pools:
            scan_ctx.cached_collab_gacha_pools |= pools
            if pub_ts is not None:
                for pool in pools:
                    prev = scan_ctx.collab_gacha_pool_pub_ts.get(pool)
                    if prev is None or pub_ts < prev:
                        scan_ctx.collab_gacha_pool_pub_ts[pool] = pub_ts

def effective_side_story_for_hit(
    side_story: str | None,
    scan_ctx: BilibiliScanContext | None,
) -> str | None:
    """本条动态 SideStory 优先，否则用扫描上下文里缓存的 SideStory（不含主题曲）。"""
    if (side_story or "").strip():
        return side_story.strip()
    if scan_ctx and _is_side_story_context(scan_ctx.cached_side_story):
        return scan_ctx.cached_side_story.strip()
    return None


def _activity_obtain_bracket_label(
    side_story: str | None,
    activity_name: str | None,
) -> str | None:
    """获取途径【…】内活动短名；SideStory 原文仅用于匹配，展示仍为【泡影苍霆】。"""
    name = (activity_name or "").strip()
    if name:
        return name
    return _side_story_activity_name(side_story)


def _is_main_theme_context(
    side_story: str | None,
    scan_ctx: BilibiliScanContext | None = None,
) -> bool:
    """本条动态或扫描缓存是否为主题曲活动（非 SideStory）。"""
    ss = (side_story or "").strip()
    if ss.startswith("主题曲"):
        return True
    if scan_ctx:
        cached = (scan_ctx.cached_side_story or "").strip()
        if cached.startswith("主题曲"):
            return True
    return False


def should_use_main_theme_reward_obtain(
    gacha_pool: str,
    side_story: str | None,
    scan_ctx: BilibiliScanContext | None = None,
) -> bool:
    """主题曲奖励干员，或 GUI/动态上下文表明为主题曲篇章奖励。"""
    pool = (gacha_pool or "").strip()
    if pool == "主题曲奖励干员":
        return True
    if pool != "活动奖励干员":
        return False
    if _is_main_theme_context(side_story, scan_ctx):
        return True
    if scan_ctx is None:
        return False
    if scan_ctx.gui_activity_is_main_theme and (scan_ctx.gui_activity_name or "").strip():
        return True
    gui = (scan_ctx.gui_activity_name or "").strip()
    cached_mt = (scan_ctx.cached_main_theme_activity_name or "").strip()
    return bool(gui and cached_mt and gui == cached_mt)


def _main_theme_reward_obtain_path(activity_name: str | None) -> str:
    """主题曲奖励干员：【相变临界】主题曲获取、主题曲获取。"""
    name = (activity_name or "").strip()
    if name:
        return f"【{name}】主题曲获取、主题曲获取"
    return "主题曲获取"
def _normalize_reward_gacha_pool(gacha_pool: str) -> tuple[str, str | None]:
    """
    长名公告池 → (规范类型, 「」内主题名或 None)。
    已是规范短名则原样返回。
    """
    p = (gacha_pool or "").strip()
    if p in ("活动奖励干员", "主题曲奖励干员", "集成战略奖励干员"):
        return p, None
    # 集成战略「沉沦者的黑流树海」奖励干员
    if p.startswith("集成战略") and "奖励干员" in p:
        return "集成战略奖励干员", _side_story_activity_name(p)
    if p.endswith("奖励干员") and ("「" in p or "『" in p):
        # 其它带书名号的奖励干员长句，按活动奖励处理
        return "活动奖励干员", _side_story_activity_name(p)
    return p, None
def _is_reward_obtain_path(activity_name: str | None) -> str:
    """集成战略奖励：【黑流树海】集成战略活动获取、活动获取。"""
    name = (activity_name or "").strip()
    if name:
        return f"【{name}】集成战略活动获取、活动获取"
    return "集成战略活动获取、活动获取"
def apply_gui_activity_obtain_path(
    value: dict[str, Any],
    gui_activity_name: str | None,
    *,
    gui_activity_is_main_theme: bool = False,
) -> dict[str, Any]:
    """GUI 已选活动时，活动/主题曲奖励类获取途径强制用库表活动名。"""
    from shared.globals import ACQUISITION_METHOD

    gui = (gui_activity_name or "").strip()
    if not gui:
        return value
    obtain = str(value.get("获取途径") or "")
    out = dict(value)
    if (
        gui_activity_is_main_theme
        and ("活动获取" in obtain or "活动获得" in obtain)
        and "联动" not in obtain
    ):
        out["获取途径"] = _main_theme_reward_obtain_path(gui)
        return out
    if "主题曲获取" in obtain or "主题曲获得" in obtain:
        out["获取途径"] = _main_theme_reward_obtain_path(gui)
        return out
    if "活动获取" not in obtain and "活动获得" not in obtain:
        return value
    if "、活动获取、联动" in obtain:
        out["获取途径"] = f"【{gui}】活动获取、活动获取、联动"
    else:
        prefix = ACQUISITION_METHOD.get("活动奖励干员", "活动获取、【")
        out["获取途径"] = prefix + gui + "】活动获取"
    return out


def resolve_activity_reward_name(
    *,
    side_story: str | None,
    scan_ctx: BilibiliScanContext | None,
) -> str | None:
    """活动/主题曲奖励获取途径用活动名：GUI 选择 > 本动态 SideStory/主题曲 > 扫描缓存。"""
    if scan_ctx:
        gui = (scan_ctx.gui_activity_name or "").strip()
        if gui:
            return gui
    from_hit = _side_story_activity_name(side_story)
    if from_hit:
        return from_hit
    if scan_ctx:
        cached = (scan_ctx.cached_activity_name or "").strip()
        if cached:
            return cached
    return None


def resolve_collab_activity_name(
    *,
    side_story: str | None,
    scan_ctx: BilibiliScanContext | None,
) -> str | None:
    """联动活动奖励获取途径用活动名：GUI 选择 > 本动态 SideStory > 扫描缓存。"""
    if scan_ctx:
        gui = (scan_ctx.gui_activity_name or "").strip()
        if gui:
            return gui
    from_hit = _side_story_activity_name(side_story)
    if from_hit:
        return from_hit
    if scan_ctx:
        cached = (scan_ctx.cached_activity_name or "").strip()
        if cached:
            return cached
    return None


def _side_story_activity_name(side_story: str | None) -> str | None:
    """从 SideStory「泡影苍霆」/ 主题曲「…」 等文案取出活动名。"""
    if not side_story:
        return None
    l = side_story.find("「")
    r = side_story.rfind("」")
    if l != -1 and r != -1 and r > l:
        name = side_story[l + 1 : r].strip()
        return name or None
    return None


def _activity_reward_obtain_path(
    side_story: str | None,
    acquisition_method: dict[str, str],
    *,
    collab: bool = False,
    activity_name: str | None = None,
) -> str:
    """活动奖励干员获取途径；联动期为【活动名】活动获取、活动获取、联动。"""
    if side_story and side_story.startswith("主题曲"):
        return _main_theme_reward_obtain_path(
            _activity_obtain_bracket_label(side_story, activity_name)
        )
    label = _activity_obtain_bracket_label(side_story, activity_name)
    if collab:
        if label:
            return f"【{label}】活动获取、活动获取、联动"
        return "活动获取、活动获取、联动"
    prefix = acquisition_method.get("活动奖励干员", "活动获取、【")
    if label:
        return prefix + label + "】活动获取"
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
# 专栏摘要：活动期间【限定寻访·庆典】-【辟路之人】寻访开启
_ARTICLE_POOL_IN_SUMMARY_RE = re.compile(r"-【([^】]+)】寻访")
_LIMITED_BANNER_IN_TEXT_RE = re.compile(r"【(限定寻访[^】]+)】")


def _normalize_operator_name(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").replace("·", "").replace("•", ""))


def extract_article_pool_keys(title: str, summary: str) -> tuple[str | None, str | None]:
    """
    从专栏解析卡池名与寻访类型。

    卡池名优先取摘要里的 -【辟路之人】寻访；标题首个【】常为「限定寻访·庆典」。
    """
    pool_name: str | None = None
    m = _ARTICLE_POOL_IN_SUMMARY_RE.search(summary or "")
    if m:
        pool_name = (m.group(1) or "").strip() or None
    if not pool_name:
        for m in re.finditer(r"【([^】]+)】", title or ""):
            candidate = (m.group(1) or "").strip()
            if candidate and not candidate.startswith("限定寻访"):
                pool_name = candidate
                break
    banner_type: str | None = None
    for text in (summary, title):
        m2 = _LIMITED_BANNER_IN_TEXT_RE.search(text or "")
        if m2:
            banner_type = (m2.group(1) or "").strip() or None
            break
    return pool_name, banner_type


def _extract_limited_operators_from_article_summary(summary: str) -> set[str]:
    """从限定寻访专栏摘要解析带 [限定] 标记的干员名。"""
    names: set[str] = set()
    for m in _LIMITED_OPERATOR_IN_ARTICLE_RE.finditer(summary or ""):
        name = (m.group(1) or "").strip()
        if name:
            names.add(name)
    return names


def _is_limited_operator_in_pool(name: str, limited_names: set[str]) -> bool:
    """干员是否在该卡池专栏的 [限定] 名单内（允许预告名为专栏全名的前缀）。"""
    name = (name or "").strip()
    if not name or not limited_names:
        return False
    if name in limited_names:
        return True
    norm_name = _normalize_operator_name(name)
    for lim in limited_names:
        lim = (lim or "").strip()
        if not lim:
            continue
        if norm_name == _normalize_operator_name(lim):
            return True
        # 仅允许「预告名 ⊂ 专栏名」，避免专栏「凛冬」误判「怒潮凛冬」
        if len(name) >= 2 and name in lim:
            return True
    return False


def _extract_collab_gacha_pools_from_nodes(nodes: list[dict]) -> set[str]:
    pools: set[str] = set()
    for node in nodes:
        for m in _COLLAB_GACHA_POOL_RE.finditer(node.get("orig_text") or ""):
            pools.add(m.group(1))
    return pools


def _collab_gacha_pool_label(
    gacha_pool: str,
    collab_pool: str | None,
) -> str | None:
    """联动寻访文案中的卡池名：联动期内「新增干员」用公告池名，否则用本条池名。"""
    named = (collab_pool or "").strip()
    if named:
        return named
    if gacha_pool and gacha_pool not in (
        "新增干员",
        "活动奖励干员",
        "主题曲奖励干员",
    ):
        return gacha_pool.strip() or None
    return None

def _bulletin_plain_text(raw: str) -> str:
    """公告正文多为 HTML（如 <strong>活动时间：</strong>08月01日），去标签后再匹配。"""
    text = (raw or "").replace("\\n", "\n")
    if "<" in text and ">" in text:
        try:
            text = BeautifulSoup(text, "html.parser").get_text("\n")
        except Exception:
            text = re.sub(r"<[^>]+>", "", text)
    return text


def resolve_bulletin_activity_date_label(
    scan_ctx: BilibiliScanContext | None,
    *,
    activity_name: str | None = None,
) -> str | None:
    """从鹰角游戏内公告解析活动开日，供实装日期 date_label。

    用活动名（SideStory 名等）在标题/header/正文中匹配，再取附近「活动时间」。
    自行 load_config，避免层层传递 mapper/config。
    """
    if scan_ctx is None:
        return None
    needle = (
        (activity_name or "").strip()
        or (scan_ctx.cached_activity_name or "").strip()
        or (scan_ctx.gui_activity_name or "").strip()
    )
    cache_map = getattr(scan_ctx, "_bulletin_date_by_needle", None)
    if not isinstance(cache_map, dict):
        cache_map = {}
        scan_ctx._bulletin_date_by_needle = cache_map
    cache_key = needle or ""
    if cache_key in cache_map:
        return cache_map[cache_key] or None

    try:
        from data import load_config, resolve_config_path

        config = load_config(resolve_config_path("config.json"))
        settings = resolve_hypergryph_settings(config)
        list_url = settings["bulletin_list_url"]
        detail_url = settings["bulletin_detail_url"]
        target = settings["bulletin_target"]
    except Exception:
        cache_map[cache_key] = ""
        log_info("resolve_bulletin_activity_date_label: error resolving hypergryph settings")
        return None
    try:
        listing = requests.get(list_url, params={"target": target}, timeout=10).json()
        items = (listing.get("data") or {}).get("list") or []
    except Exception:
        cache_map[cache_key] = ""
        log_info("resolve_bulletin_activity_date_label: error getting bulletin list")
        return None

    def _norm_title(raw: str) -> str:
        return (raw or "").replace("\\n", "").replace("\n", "")

    # 标题含活动名优先；否则扫「活动限时/即将开启」类，再在正文里确认
    ordered: list[dict] = []
    seen_cid: set[str] = set()
    if needle:
        for it in items:
            title = _norm_title(it.get("title") or "")
            cid = str(it.get("cid") or "") or ""
            if not cid or cid in seen_cid:
                continue
            if needle in title:
                ordered.append(it)
                seen_cid.add(cid)
    for it in items:
        title = _norm_title(it.get("title") or "")
        cid = str(it.get("cid") or "") or ""
        if not cid or cid in seen_cid:
            continue
        if "活动限时开启" in title or "活动即将开启" in title:
            ordered.append(it)
            seen_cid.add(cid)

    label: str | None = None
    for it in ordered[:12]:
        cid = str(it.get("cid") or "") or ""
        if not cid:
            continue
        try:
            detail = requests.get(detail_url.format(cid=cid), timeout=10).json()
            data = detail.get("data") or {}
            title = _norm_title(data.get("title") or it.get("title") or "")
            header = _bulletin_plain_text(data.get("header") or "")
            content = _bulletin_plain_text(data.get("content") or "")
            display = (data.get("displayTime") or "").strip()
        except Exception:
            log_info(
                "resolve_bulletin_activity_date_label: error getting bulletin detail cid=%s",
                cid,
            )
            continue
        blob = f"{title}\n{header}\n{content}"
        if needle and needle not in blob:
            continue
        pos = content.find(needle) if needle else -1
        region = content[pos:] if pos >= 0 else content
        m = _ACTIVITY_OPEN_RE.search(region) or _ACTIVITY_OPEN_RE.search(content)
        if not m:
            continue
        year = int(m.group(1)) if m.group(1) else None
        month, day = int(m.group(2)), int(m.group(3))
        if year is None and display:
            try:
                year = int(display.split("-", 1)[0])
            except ValueError:
                year = None
        if year is None:
            year = datetime.now().year
        label = format_zh_ymd(year, month, day)
        log_info(
            "resolve_bulletin_activity_date_label: hit needle=%s cid=%s label=%s",
            needle or None,
            cid,
            label,
        )
        break

    cache_map[cache_key] = label or ""
    scan_ctx._bulletin_date_label = label or ""
    return label


def _obtain_path_for_gacha_pool(
    gacha_pool: str,
    acquisition_method: dict[str, str],
    *,
    collab: bool = False,
    side_story: str | None = None,
    activity_name: str | None = None,
    collab_pool: str | None = None,
) -> str:
    """按卡池名生成获取途径；未在 ACQUISITION_METHOD 中的命名池视为限定寻访。"""
    if gacha_pool and ("集成战略" in gacha_pool and "奖励干员" in gacha_pool):
        return _is_reward_obtain_path(activity_name)
    if gacha_pool == "主题曲奖励干员":
        return _main_theme_reward_obtain_path(activity_name)
    if gacha_pool == "活动奖励干员":
        if side_story and side_story.startswith("主题曲"):
            return _main_theme_reward_obtain_path(
                _activity_obtain_bracket_label(side_story, activity_name)
            )
        return _activity_reward_obtain_path(
            side_story,
            acquisition_method,
            collab=collab,
            activity_name=activity_name,
        )
    if collab:
        label = _collab_gacha_pool_label(gacha_pool, collab_pool)
        if label:
            return f"联动、联动寻访、【{label}】寻访"
    mapped = acquisition_method.get(gacha_pool)
    if mapped is not None:
        return mapped
    if gacha_pool == "新增干员":
        return acquisition_method.get("新增干员", "标准寻访")
    if gacha_pool:
        # 未匹配到专栏 [限定] 扫描结果时，不凭卡池名臆断为限定
        return acquisition_method.get("新增干员", "标准寻访")
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
    target_names: set[str] | list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """
    拉取 B 站干员补充数据。

    target_names 为 None：先发现 character_num 个干员名，再对每人完整抓取（含 OCR）。
    target_names 指定时：仅对名单内干员完整抓取。
    """
    from .bilibili_supplementary_fetch import (
        discover_operator_names_from_bilibili,
        fetch_character_supplementary_for_names,
    )

    if target_names is not None:
        return fetch_character_supplementary_for_names(
            mid,
            headers,
            target_names,
            announce_line_re=announce_line_re,
            acquisition_method=acquisition_method,
            collab_activity_re=collab_activity_re,
            log_warning=log_warning,
            log_info=log_info,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
        )

    names = discover_operator_names_from_bilibili(
        mid,
        headers,
        announce_line_re=announce_line_re,
        collab_activity_re=collab_activity_re,
        character_num=character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        log_warning=log_warning,
        log_info=log_info,
    )
    if not names:
        return {}
    return fetch_character_supplementary_for_names(
        mid,
        headers,
        names,
        announce_line_re=announce_line_re,
        acquisition_method=acquisition_method,
        collab_activity_re=collab_activity_re,
        log_warning=log_warning,
        log_info=log_info,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
    )


__all__ = [
    "fetch_user_dynamics",
    "fetch_character_supplementary_data",
    "operator_photo_dir",
]
