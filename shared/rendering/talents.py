"""Talent field renderers extracted from legacy template generation."""

from __future__ import annotations

from arknights_toolbox.shared.rendering.description_parser import process_description
from arknights_toolbox.shared.utils import PHASE
from arknights_toolbox.shared.globals import POTENTIAL_SUFFIX

def render_operator_talent_fields(
    mapper,
    trait_candidates,
    rich_styles,
    term_description_dict,
    term_index_cache=None,
):
    """
    渲染主干员天赋模板字段，返回可直接 append/extend 的模板行列表。
    """
    lines: list[str] = []
    talents_candidates = mapper.get_data_safe("character_table", "{talents}[*].candidates", default=[]) or []
    for i in range(1, 3):
        for j in range(0, 6):
            is_not_none = False
            talent = ""
            talent_condition = ""
            talent_description = ""
            if len(talents_candidates) >= i and talents_candidates[i - 1] and len(talents_candidates[i - 1]) > j:
                is_not_none = True
                mapper.add_mapping("character_table", "talent_group_index", str(i - 1))
                mapper.add_mapping("character_table", "talent_candidate_index", str(j))
                talent = mapper.get_data_safe("character_table", "talent_name", default="") or ""
                phase = mapper.get_data_safe("character_table", "talent_phase", default="PHASE_0")
                phase = mapper._apply_value_map("character_table", "phase", phase)
                required_potential = mapper.get_data_safe("character_table", "talent_required_potential", default=0)
                phase_text = str(PHASE(phase))
                talent_condition = (
                    phase_text + POTENTIAL_SUFFIX.get(str(required_potential), "")
                    if (phase != "PHASE_0" or required_potential != 0)
                    else "初始携带"
                )
                if talent == "":
                    talent_condition = ""
                talent_description = process_description(
                    mapper.get_data_safe("character_table", "talent_description", default=""),
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    None,
                    term_index_cache,
                )
            lines.append(f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}={talent if is_not_none else ''}")
            lines.append(
                f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'解锁' if j < 1 else ''}{'提升' if j >= 1 else ''}条件={talent_condition if is_not_none else ''}"
            )
            lines.append(
                f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}描述={talent_description if is_not_none else ''}"
            )
        lines.append(f"|天赋{i}备注=")
        lines.append(f"|天赋{i}攻击范围=")
    return lines


__all__ = ["render_operator_talent_fields"]
