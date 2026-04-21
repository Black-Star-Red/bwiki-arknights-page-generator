"""Runtime-wide constants that are still static mappings."""

from __future__ import annotations

POTENTIAL_SUFFIX = {
    "0": "",
    "1": "、潜能2",
    "2": "、潜能3",
    "3": "、潜能4",
    "4": "、潜能5",
    "5": "、潜能6",
}

INFRASTRUCTURE_ROOM = {
    "CONTROL": "控制中枢",
    "POWER": "发电站",
    "MANUFACTURE": "制造站",
    "TRADING": "贸易站",
    "WORKSHOP": "加工站",
    "TRAINING": "训练室",
    "DORMITORY": "宿舍",
    "HIRE": "办公室",
    "MEETING": "会客室",
}

# Keep legacy behavior as default while allowing config override.
DEFAULT_BILIBILI_MID = "161775300"

TRUST_ATTRIBUTE_LABELS = {
    "maxHp": "生命",
    "atk": "攻击",
    "def": "防御",
    "magicResistance": "法抗",
}

# 基建技能模板字段后缀（第 1/2/3 档）
INFRASTRUCTURE_SKILL_SUFFIX = {1: "", 2: "提升后", 3: "再次提升后"}

__all__ = [
    "POTENTIAL_SUFFIX",
    "INFRASTRUCTURE_ROOM",
    "DEFAULT_BILIBILI_MID",
    "TRUST_ATTRIBUTE_LABELS",
    "INFRASTRUCTURE_SKILL_SUFFIX",
]
