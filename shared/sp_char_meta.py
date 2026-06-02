"""char_meta_table.spCharGroups：异格/联动皮 charId 与本体配对。"""

from __future__ import annotations

from typing import Any


def sp_char_groups_from_mapper(mapper) -> dict[str, list[str]] | None:
    """从 DataMapper 读取 spCharGroups；数据源未配置时返回 None。"""
    try:
        raw = mapper.get_data("char_meta_table", "spCharGroups")
    except (KeyError, TypeError, AttributeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, list[str]] = {}
    for key, members in raw.items():
        if not isinstance(members, list):
            continue
        ids = [str(m).strip() for m in members if str(m).strip()]
        if ids:
            out[str(key).strip()] = ids
    return out or None


def build_sp_char_index(
    groups: dict[str, list[str]],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """charId -> 组键（本体 id）；组键 -> 成员列表。"""
    char_to_group: dict[str, str] = {}
    for group_key, members in groups.items():
        for cid in members:
            char_to_group[cid] = group_key
    return char_to_group, groups


def _char_name(mapper, char_id: str) -> str:
    mapper.mappings.setdefault("character_table", {})
    mapper.mappings["character_table"]["currentCharId"] = char_id
    return (mapper.get_data_safe("character_table", "name") or "").strip()


def _char_in_table(mapper, char_id: str) -> bool:
    table = mapper.get_data("character_table")
    return isinstance(table, dict) and bool(char_id) and char_id in table


def resolve_char_id_by_sp_groups(mapper, display_name: str) -> str | None:
    """
    在 spCharGroups 各组内匹配显示名：精确名优先，否则组内最长「表名 ⊂ 显示名」。
    仅考虑 character_table 中存在的 charId。
    """
    display_name = (display_name or "").strip()
    if not display_name:
        return None
    groups = sp_char_groups_from_mapper(mapper)
    if not groups:
        return None

    best_cid: str | None = None
    best_len = -1
    for members in groups.values():
        for cid in members:
            if not _char_in_table(mapper, cid):
                continue
            nm = _char_name(mapper, cid)
            if not nm:
                continue
            if nm == display_name:
                return cid
            if nm in display_name and len(nm) > best_len:
                best_len = len(nm)
                best_cid = cid
    return best_cid


def find_sp_char_alter_partner(
    mapper, char_id: str
) -> tuple[str | None, str | None]:
    """
    为 Wiki |异格干员= 解析本体 charId 与显示名。

    当前 id 为组内异格/联动皮时返回 (组键本体, 本体名)；本体或单成员组返回 (None, None)。
    """
    char_id = (char_id or "").strip()
    if not char_id:
        return None, None
    groups = sp_char_groups_from_mapper(mapper)
    if not groups:
        return None, None

    char_to_group, _ = build_sp_char_index(groups)
    group_key = char_to_group.get(char_id)
    if not group_key:
        return None, None
    members = groups.get(group_key) or []
    if len(members) < 2 or char_id == group_key:
        return None, None

    base_id = group_key if _char_in_table(mapper, group_key) else None
    if base_id is None:
        for cid in members:
            if cid == char_id or not _char_in_table(mapper, cid):
                continue
            mapper.mappings.setdefault("character_table", {})
            mapper.mappings["character_table"]["currentCharId"] = cid
            if not mapper.get_data_safe("character_table", "isSpChar"):
                base_id = cid
                break
    if base_id is None:
        return None, None
    return base_id, _char_name(mapper, base_id)


__all__ = [
    "build_sp_char_index",
    "find_sp_char_alter_partner",
    "resolve_char_id_by_sp_groups",
    "sp_char_groups_from_mapper",
]
