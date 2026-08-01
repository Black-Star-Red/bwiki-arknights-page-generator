"""干员补充数据 → Wiki 角标等展示字段。"""

from __future__ import annotations

import re
from typing import Any

from shared.collab_supplementary import (
    enrich_collab_meta,
    is_collab_activity_reward_obtain,
    wiki_obtain_path as _wiki_obtain_path,
)

# 与 bilibili_service 联动分支写入的获取途径一致（兜底解析卡池名）
_COLLAB_OBTAIN_RE = re.compile(r"^联动、联动寻访、【([^】]+)】寻访")
_COLLAB_OBTAIN_LEGACY_RE = re.compile(r"^联动寻访、【([^】]+)】寻访")


def is_collaboration(value: dict[str, Any]) -> bool:
    """是否联动干员：联动=True，或获取途径为联动寻访文案。"""
    flag = value.get("联动")
    if flag is True:
        return True
    if isinstance(flag, str) and flag.strip().lower() in ("1", "true", "yes"):
        return True
    if collab_pool_name(value):
        return True
    if is_collab_activity_reward_obtain(str(value.get("获取途径") or "")):
        return True
    return False


def collab_pool_name(value: dict[str, Any]) -> str | None:
    """联动卡池名；优先 联动卡池，否则从获取途径解析。"""
    pool = (value.get("联动卡池") or "").strip()
    if pool:
        return pool
    obtain = str(value.get("获取途径") or "").strip()
    for pat in (_COLLAB_OBTAIN_RE, _COLLAB_OBTAIN_LEGACY_RE):
        m = pat.match(obtain)
        if m:
            return m.group(1).strip()
    return None


def _is_activity_reward_obtain(obtain: str) -> bool:
    text = obtain or ""
    return "活动获取" in text or "活动获得" in text


def _is_main_theme_obtain(obtain: str) -> bool:
    return "主题曲" in (obtain or "")


def collab_obtain_path(value: dict[str, Any]) -> str | None:
    """联动寻访类 |获取途径= 文案（活动/主题曲奖励类不覆盖）。"""
    obtain = str(value.get("获取途径") or "").strip()
    if _is_activity_reward_obtain(obtain) or _is_main_theme_obtain(obtain):
        return None
    pool = collab_pool_name(value)
    if pool:
        return f"联动、联动寻访、【{pool}】寻访"
    return None


def wiki_obtain_path(value: dict[str, Any]) -> str:
    """Wiki |获取途径= 与入库回填共用（实现在 shared.collab_supplementary）。"""
    return _wiki_obtain_path(value)


def build_corner_labels(
    value: dict[str, Any],
    *,
    alter_operator: str = "",
) -> list[str]:
    """
    根据 B 站补充 dict 生成 |角标= 列表项。

    联动：角标「联」；活动奖励干员再加「活」，主题曲活动再加「主」，异格再加「异」。
    非联动：限 / 活 / 主 / 异 等原有规则。
    """
    obtain = str(value.get("获取途径") or "")
    if is_collaboration(value):
        label: list[str] = ["联"]
        if _is_activity_reward_obtain(obtain):
            label.append("活")
        elif _is_main_theme_obtain(obtain):
            label.append("主")
        if alter_operator:
            label.append("异")
        return label

    label = []
    if _is_activity_reward_obtain(obtain):
        label.append("活")
    elif _is_main_theme_obtain(obtain):
        label.append("主")
    if alter_operator:
        label.append("异")
    if value.get("动态id"):
        label.insert(0, "限")
    return label


def is_limited_dynamic(value: dict[str, Any]) -> bool:
    """是否应输出 |解限=否（联动时不视为普限定标逻辑）。"""
    if is_collaboration(value):
        return False
    return bool(value.get("动态id"))


__all__ = [
    "build_corner_labels",
    "collab_obtain_path",
    "collab_pool_name",
    "enrich_collab_meta",
    "is_collaboration",
    "is_limited_dynamic",
    "wiki_obtain_path",
]
