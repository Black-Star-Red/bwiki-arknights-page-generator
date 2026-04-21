"""Skill field renderers for operator templates."""

from __future__ import annotations

from arknights_toolbox.shared.rendering.description_parser import process_description


def render_operator_skill_fields(
    mapper,
    trait_candidates,
    rich_styles,
    term_description_dict,
    mapping_skill_type,
    term_index_cache=None,
):
    """
    渲染主干员技能字段。

    Returns:
        tuple[list[str], list[tuple[int, str, str]]]:
            - 字段行列表
            - 每个技能位的 (index, override_token_key, summon_name)
    """
    lines: list[str] = []
    summon_entries: list[tuple[int, str, str]] = []
    for i in range(1, 4):
        skill_id = mapper.get_data_safe("character_table", "{skills}" + f"[{i-1}].skillId")
        skill_data = mapper.get_data_safe("skill_table", f"{skill_id}.levels") if skill_id else None
        skill_name = skill_data[i - 1].get("name") if skill_data and len(skill_data) > i - 1 else None
        skill_icon = skill_data[i - 1].get("icon") if skill_data and len(skill_data) > i - 1 else None
        is_null_skill_icon = skill_icon if skill_name != skill_icon else skill_name
        skill_range = skill_data[i - 1].get("rangeId") if skill_data and len(skill_data) > i - 1 else None
        sp_data = skill_data[i - 1].get("spData", {}) if skill_data and len(skill_data) > i - 1 else {}
        skill_recover_type = sp_data.get("spType")
        skill_trigger_type = skill_data[i - 1].get("skillType") if skill_data and len(skill_data) > i - 1 else None
        skill_type = skill_data[i - 1].get("durationType") if skill_data and len(skill_data) > i - 1 else None
        override_token_key = mapper.get_data_safe("character_table", "{skills}" + f"[{i-1}].overrideTokenKey")

        lines.append(f"|技能{i}={skill_name if skill_name is not None else ''}")
        lines.append(f"|skillId{i}={skill_id if skill_id is not None else ''}")
        lines.append(f"|skillIcon{i}={'' if is_null_skill_icon is None else skill_icon}")
        lines.append(f"|技能{i}类型={mapping_skill_type[skill_type] if skill_type is not None and skill_type != 'NONE' else ''}")
        lines.append(f"|技能{i}攻击范围={skill_range if skill_range is not None else ''}")
        lines.append(f"|技能{i}回复类型={mapper._apply_value_map('skill_table', 'sp_type', skill_recover_type) or ''}")
        lines.append(f"|技能{i}触发类型={mapper._apply_value_map('skill_table', 'skill_trigger_type', skill_trigger_type) or ''}")
        for j in range(1, 11):
            level_data = skill_data[j - 1] if skill_data and len(skill_data) > j - 1 else {}
            sp_data = level_data.get("spData", {})
            skill_consume = sp_data.get("spCost")
            skill_init = sp_data.get("initSp")
            skill_consistent_time = level_data.get("duration")
            if skill_consistent_time is not None:
                rounded = round(skill_consistent_time)
                if abs(skill_consistent_time - rounded) < 1e-10:
                    skill_consistent_time = int(rounded)
            skill_description = level_data.get("description")
            blackboard = level_data.get("blackboard", [])
            lines.append(
                f"|技能{i}描述{j}={process_description(skill_description, trait_candidates, rich_styles, term_description_dict, blackboard, term_index_cache).replace(r'\\n', '<br/>')}"
            )
            lines.append(f"|技能{i}技力消耗{j}={skill_consume if skill_consume else ''}")
            lines.append(f"|技能{i}初始技力{j}={skill_init if skill_init is not None else ''}")
            lines.append(f"|技能{i}持续时间{j}={skill_consistent_time if skill_consistent_time is not None and skill_consistent_time >= 0 else ''}")
        lines.append(f"|技能{i}备注=")
        summon_name = mapper.get_data_safe("character_table", f"{override_token_key}.name") if override_token_key else ""
        lines.append(f"|召唤物{i}={summon_name}<!-- 请额外创建页面，使用干员附带单位模板 -->")
        summon_entries.append((i, override_token_key, summon_name))
    return lines, summon_entries


__all__ = ["render_operator_skill_fields"]
