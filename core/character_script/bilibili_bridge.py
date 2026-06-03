"""B 站动态与干员补充数据（脚本侧薄封装）。"""

from __future__ import annotations

import re

from core.script_logging import log_info, log_warning
from shared.globals import ACQUISITION_METHOD
from shared.services import fetch_user_dynamics
from shared.services.bilibili_service import BilibiliScanContext
from shared.services.bilibili_supplementary_fetch import (
    discover_operator_names_from_bilibili,
    fetch_character_supplementary_for_names,
)
# 官号干员预告：【卡池】\n//干员名\n“台词”。仅匹配本条动态顶层正文，不扫 dyn_forward 内嵌段。
ANNOUNCE_LINE_RE = re.compile(
    r"^\s*(?:互动抽奖\s*)?【([^】]+)】\n//([^\n]+)\n(?:\u201c|\")(.*?)(?:\u201d|\")"
)

# 联动活动预告：【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启
COLLAB_ACTIVITY_RE = re.compile(r"^【明日方舟\s*[×xX][^】]+】")

_BILI_SCAN_KW = dict(
    announce_line_re=ANNOUNCE_LINE_RE,
    collab_activity_re=COLLAB_ACTIVITY_RE,
    log_warning=log_warning,
    log_info=log_info,
)

_BILI_FETCH_KW = dict(
    **_BILI_SCAN_KW,
    acquisition_method=ACQUISITION_METHOD,
)


def get_user_dynamics(mid, headers, offset=None):
    """获取用户动态 - 通过B站API"""
    return fetch_user_dynamics(mid, headers, offset)


def discover_operator_names(
    mid,
    headers,
    character_num: int | None,
    *,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
    scan_ctx: BilibiliScanContext | None = None,
):
    """仅扫描 B 站动态，返回干员名列表（不 OCR）。"""
    return discover_operator_names_from_bilibili(
        mid,
        headers,
        character_num=character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        scan_ctx=scan_ctx,
        **_BILI_SCAN_KW,
    )


def fetch_supplementary_for_names(
    mid,
    headers,
    names: set[str] | list[str],
    *,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
    scan_ctx: BilibiliScanContext | None = None,
):
    """对指定干员名完整抓取 B 站补充（含 OCR）。"""
    return fetch_character_supplementary_for_names(
        mid,
        headers,
        names,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        scan_ctx=scan_ctx,
        **_BILI_FETCH_KW,
    )


def get_character_supplementary_data(
    mid,
    headers,
    character_num,
    *,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
    target_names: set[str] | list[str] | None = None,
):
    """通过 B 站 API 获取干员补充信息（兼容旧调用）。"""
    if target_names is not None:
        return fetch_supplementary_for_names(
            mid,
            headers,
            target_names,
            dynamic_start_ts=dynamic_start_ts,
            dynamic_end_ts=dynamic_end_ts,
        )
    names = discover_operator_names(
        mid,
        headers,
        character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
    )
    if not names:
        return {}
    return fetch_supplementary_for_names(
        mid,
        headers,
        names,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
    )
