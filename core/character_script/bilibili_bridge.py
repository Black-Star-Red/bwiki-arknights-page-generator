"""B 站动态与干员补充数据（脚本侧薄封装）。"""

from __future__ import annotations

import re

from core.script_logging import log_info, log_warning
from shared.globals import ACQUISITION_METHOD
from shared.services import fetch_character_supplementary_data, fetch_user_dynamics
from shared.services.ocr_service import ocr_specialization

# 官号干员预告：【卡池】\n//干员名\n“台词”。仅匹配本条动态顶层正文，不扫 dyn_forward 内嵌段。
ANNOUNCE_LINE_RE = re.compile(
    r"^\s*(?:互动抽奖\s*)?【([^】]+)】\n//([^\n]+)\n(?:\u201c|\")(.*?)(?:\u201d|\")"
)

# 联动活动预告：【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启
COLLAB_ACTIVITY_RE = re.compile(r"^【明日方舟\s*[×xX][^】]+】")


def get_user_dynamics(mid, headers, offset=None):
    """获取用户动态 - 通过B站API"""
    return fetch_user_dynamics(mid, headers, offset)


def get_character_supplementary_data(
    mid,
    headers,
    character_num,
    *,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
):
    """通过b站api获取干员补充信息"""
    return fetch_character_supplementary_data(
        mid,
        headers,
        announce_line_re=ANNOUNCE_LINE_RE,
        collab_activity_re=COLLAB_ACTIVITY_RE,
        acquisition_method=ACQUISITION_METHOD,
        ocr_specialization=ocr_specialization,
        log_warning=log_warning,
        log_info=log_info,
        character_num=character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
    )
