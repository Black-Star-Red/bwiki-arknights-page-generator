"""Template helper renderers extracted from legacy script."""

from __future__ import annotations

import re

from data.mapper_helpers import bind_item

# char_193_frostl@boc#4 → @ 前为干员 charId
_SKIN_KEY_CHAR_RE = re.compile(r"^(.+?)@")
_MAX_OPERATOR_SKINS = 6


def render_skill_materials(mapper, all_skill_lvlup, level):
    """
    渲染技能升级材料。

    Args:
        mapper: 数据映射器实例
        all_skill_lvlup: 技能升级数据
        level: 技能等级（1-based）

    Returns:
        材料模板字符串
    """
    level -= 1
    costs = all_skill_lvlup[level].get("lvlUpCost") if level < len(all_skill_lvlup) else None
    costs = all_skill_lvlup[level].get("levelUpCost") if (costs is None and level < len(all_skill_lvlup)) else costs

    if isinstance(costs, list):
        parts_m = []
        for cost in costs:
            iid = cost.get("id")
            bind_item(mapper, iid)
            nm = mapper.get_data_safe("item_table", "item_name_by_id", default=iid if iid is not None else "未知物品")
            parts_m.append(f"{{{{data|{nm}|{cost.get('count', '')}}}}}")
        materials = "".join(parts_m)
    else:
        materials = ""
    return materials


def build_drawer_from_skins(mapper, char_id):
    """从 skin_table 中提取画师/原案并拼接为展示字符串。"""
    drawer = ""
    char_skins = mapper.get_data_safe("skin_table", "charSkins") or {}
    for _, skin_value in char_skins.items():
        if char_id == skin_value["charId"] and skin_value["displaySkin"]["skinGroupId"] == "ILLUST_0":
            for i in skin_value["displaySkin"]["drawerList"]:
                if "、" in i:
                    for j in list(filter(lambda s: s.strip() != "", i.split("、"))):
                        drawer += j + "、"
                else:
                    drawer += i + "、"
            if skin_value["displaySkin"]["designerList"] and len(skin_value["displaySkin"]["designerList"]) > 0:
                for i in skin_value["displaySkin"]["designerList"]:
                    if "、" in i:
                        for j in list(filter(lambda s: s.strip() != "", i.split("、"))):
                            drawer += j + "（原案）、"
                    else:
                        drawer += i + "（原案）、"
    if drawer.endswith("、"):
        drawer = drawer[:-1]
    return drawer


def resolve_drawer_with_fallback(
    mapper,
    char_id: str,
    *,
    db_drawer: str | None = None,
) -> str:
    """
    画师解析顺序：
    1. 当前数据源 skin_table
    2. 其它数据源组 skin_table
    3. 补充库 / OCR 写入的「画师」字段（db_drawer）
    """
    drawer = build_drawer_from_skins(mapper, char_id)
    if drawer.strip():
        return drawer
    other_keys = [
        k for k in mapper.config["data_sources"].keys() if k != mapper.current_data_sources
    ]
    for alt in other_keys:
        with mapper.temporary_source_group(alt):
            drawer = build_drawer_from_skins(mapper, char_id)
            if drawer.strip():
                return drawer
    return (db_drawer or "").strip()


def _skin_entry_char_id(skin_key: str, skin_value: dict) -> str:
    """skin_table 键或条目 charId 解析干员 id。"""
    cid = (skin_value.get("charId") or "").strip()
    if cid:
        return cid
    m = _SKIN_KEY_CHAR_RE.match((skin_key or "").strip())
    return m.group(1) if m else ""


def _skin_display_name(skin_value: dict) -> str:
    display = skin_value.get("displaySkin") or {}
    if not isinstance(display, dict):
        return ""
    return (display.get("skinName") or "").strip()


def collect_operator_skin_names(
    mapper,
    char_id: str,
    *,
    max_skins: int = _MAX_OPERATOR_SKINS,
) -> list[str]:
    """从 skin_table.charSkins 收集该干员皮肤名（按 skin 键排序，去重）。"""
    char_id = (char_id or "").strip()
    if not char_id:
        return []

    char_skins = mapper.get_data_safe("skin_table", "charSkins") or {}
    if not isinstance(char_skins, dict):
        return []

    names: list[str] = []
    seen: set[str] = set()
    for skin_key in sorted(char_skins.keys()):
        skin_value = char_skins.get(skin_key)
        if not isinstance(skin_value, dict):
            continue
        if _skin_entry_char_id(skin_key, skin_value) != char_id:
            continue
        skin_name = _skin_display_name(skin_value)
        if not skin_name or skin_name in seen:
            continue
        seen.add(skin_name)
        names.append(skin_name)
        if len(names) >= max_skins:
            break
    return names


def resolve_operator_skin_names_with_fallback(
    mapper,
    char_id: str,
    *,
    max_skins: int = _MAX_OPERATOR_SKINS,
) -> list[str]:
    """皮肤名：当前数据源 skin_table → 其它数据源组。"""
    names = collect_operator_skin_names(mapper, char_id, max_skins=max_skins)
    if names:
        return names
    other_keys = [
        k for k in mapper.config["data_sources"].keys() if k != mapper.current_data_sources
    ]
    for alt in other_keys:
        with mapper.temporary_source_group(alt):
            names = collect_operator_skin_names(mapper, char_id, max_skins=max_skins)
            if names:
                return names
    return []


def render_operator_skin_template_lines(mapper, char_id: str) -> list[str]:
    """生成 |皮肤= / |皮肤2= … 与空的 |skinN动态id= 占位。"""
    names = resolve_operator_skin_names_with_fallback(mapper, char_id)
    lines: list[str] = []
    for i in range(_MAX_OPERATOR_SKINS):
        name = names[i] if i < len(names) else ""
        if i == 0:
            lines.append(f"|皮肤={name}")
            lines.append("|skin1动态id=")
        else:
            lines.append(f"|皮肤{i + 1}={name}")
            lines.append(f"|skin{i + 1}动态id=")
    return lines


__all__ = [
    "render_skill_materials",
    "build_drawer_from_skins",
    "resolve_drawer_with_fallback",
    "collect_operator_skin_names",
    "resolve_operator_skin_names_with_fallback",
    "render_operator_skin_template_lines",
]
