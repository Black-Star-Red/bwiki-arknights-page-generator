"""Skill field renderers for operator templates."""

from __future__ import annotations

from data.mapper_helpers import bind_operator, bind_skill_index, bind_skill_table_id
from shared.rendering.description_parser import process_description


def render_operator_skill_fields(
    mapper,
    trait_candidates,
    rich_styles,
    term_description_dict,
    _mapping_skill_type,
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
        bind_skill_index(mapper, i)
        skill_id = mapper.get_data_safe("character_table", "skill_id", default="") or ""
        skill_data = []
        if skill_id:
            bind_skill_table_id(mapper, skill_id)
            skill_data = mapper.get_data_safe("skill_table", "skill_levels", default=[]) or []
        if not isinstance(skill_data, list):
            skill_data = []
        head = skill_data[0] if skill_data else {}
        skill_name = head.get("name")
        skill_range = head.get("rangeId")
        sp_data = head.get("spData", {}) or {}
        skill_recover_type = sp_data.get("spType")
        skill_trigger_type = head.get("skillType")
        override_token_key = mapper.get_data_safe("character_table", "skill_override_token_key")

        lines.append(f"|技能{i}={skill_name if skill_name is not None else ''}")
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
            rendered_skill_desc = process_description(
                skill_description, trait_candidates, rich_styles, term_description_dict, blackboard, term_index_cache
            ).replace("\\n", "<br/>")
            lines.append(f"|技能{i}描述{j}={rendered_skill_desc}")
            lines.append(f"|技能{i}技力消耗{j}={skill_consume if skill_consume else ''}")
            lines.append(f"|技能{i}初始技力{j}={skill_init if skill_init is not None else ''}")
            lines.append(f"|技能{i}持续时间{j}={skill_consistent_time if skill_consistent_time is not None and skill_consistent_time >= 0 else ''}")
        lines.append(f"|技能{i}备注=")
        summon_name = ""
        if override_token_key:
            bind_operator(mapper, override_token_key)
            summon_name = mapper.get_data_safe("character_table", "operator_name") or ""
        summon_comment = (
            "<!-- 请额外创建页面，使用干员附带单位模板 -->"
            if i == 1
            else "<!-- 只有一个召唤物就不用填 -->"
        )
        if summon_name:
            lines.append(f"|召唤物{i}={summon_name}")
        else:
            lines.append(f"|召唤物{i}={summon_comment}")
        summon_entries.append((i, override_token_key, summon_name))
    return lines, summon_entries


__all__ = ["render_operator_skill_fields"]
