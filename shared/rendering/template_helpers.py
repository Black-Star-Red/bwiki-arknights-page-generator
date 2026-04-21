"""Template helper renderers extracted from legacy script."""

from __future__ import annotations


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
            nm = mapper.get_data_safe("item_table", f"items.{iid}.name", default=iid if iid is not None else "未知物品")
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


def resolve_drawer_with_fallback(mapper, char_id):
    """
    先从当前数据源获取画师；若为空则回退到其它数据源组尝试。
    """
    drawer = build_drawer_from_skins(mapper, char_id)
    if drawer.strip():
        return drawer
    other_keys = [k for k in mapper.config["data_sources"].keys() if k != mapper.current_data_sources]
    for alt in other_keys:
        with mapper.temporary_source_group(alt):
            drawer = build_drawer_from_skins(mapper, char_id)
            if drawer.strip():
                break
    return drawer


__all__ = ["render_skill_materials", "build_drawer_from_skins", "resolve_drawer_with_fallback"]
