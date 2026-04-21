"""Wiki-facing text constants."""

from __future__ import annotations

ACQUISITION_METHOD = {
    "限定寻访·春节": "限定寻访、限定寻访·春节、【",
    "限定寻访·庆典": "限定寻访、限定寻访·庆典、【",
    "限定寻访·夏季": "限定寻访、限定寻访·夏季、【",
    "活动奖励干员": "活动获取、【",
    "新增干员": "标准寻访",
    "采购凭证区-新增干员": "采购凭证区",
}

PROFESSION = {
    "CASTER": "术师",
    "MEDIC": "医疗",
    "PIONEER": "先锋",
    "SNIPER": "狙击",
    "SPECIAL": "特种",
    "SUPPORT": "辅助",
    "TANK": "重装",
    "WARRIOR": "近卫",
}

POSITION = {
    "RANGED": "远程位",
    "MELEE": "近战位",
}

SKILL_TYPE = {
    "INCREASE_WITH_TIME": "自动回复",
    "INCREASE_WHEN_ATTACK": "攻击回复",
    "INCREASE_WHEN_TAKEN_DAMAGE": "受击回复",
    8: "被动",
}

SKILL_TRIGGER_TYPE = {
    "PASSIVE": "被动",
    "MANUAL": "手动触发",
    "AUTO": "自动触发",
}

MAPPING_SKILL_TYPE = {
    0: "",
    1: "弹药",
    "AMMO": "弹药",
}

INFRASTRUCTURE_CONDITION = {
    "0": "初始携带",
    "1": "精英化1",
    "2": "精英化2",
    "初始携带": "初始携带",
    "精英化1": "精英化1",
    "精英化2": "精英化2",
}

__all__ = [
    "ACQUISITION_METHOD",
    "PROFESSION",
    "POSITION",
    "SKILL_TYPE",
    "SKILL_TRIGGER_TYPE",
    "MAPPING_SKILL_TYPE",
    "INFRASTRUCTURE_CONDITION",
]
