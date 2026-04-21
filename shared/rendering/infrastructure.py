"""Infrastructure skill field renderers."""

from __future__ import annotations

from arknights_toolbox.shared.globals import INFRASTRUCTURE_ROOM, INFRASTRUCTURE_SKILL_SUFFIX
from arknights_toolbox.shared.rendering.description_parser import process_description
from arknights_toolbox.shared.utils import PHASE


def render_operator_infrastructure_fields(
    mapper,
    char_id,
    trait_candidates,
    rich_styles,
    term_description_dict,
    infrastructure_condition_map,
    term_index_cache=None,
):
    """基建天赋模板"""
    lines: list[str] = []
    temp_number = 0
    for i in range(1, 3):
        buff_data_list = mapper.get_data_safe("building_data", f"chars.{char_id}.buffChar[{i - 1}].buffData", default=[]) or []
        for j in range(1, 4):
            buff_data = buff_data_list[j - 1] if len(buff_data_list) >= j else {}
            infrastructure_skill_id = buff_data.get("buffId")
            infrastructure_skill_name = mapper.get_data_safe("building_data", f"buffs.{infrastructure_skill_id}.buffName") if infrastructure_skill_id else None
            infrastructure_skill_icon = mapper.get_data_safe("building_data", f"buffs.{infrastructure_skill_id}.skillIcon") if infrastructure_skill_id else None
            cond = buff_data.get("cond") or {}
            infrastructure_skill_level = cond.get("level")
            infrastructure_skill_phase = cond.get("phase")
            infrastructure_skill_condition = (
                f"{PHASE(infrastructure_skill_phase)}"
                + (f"、等级{infrastructure_skill_level}" if (infrastructure_skill_level is not None and infrastructure_skill_level > 1) else "")
            ) if ((infrastructure_skill_level is not None and infrastructure_skill_level > 1) or infrastructure_skill_phase != "PHASE_0") else "初始携带"
            infrastructure_skill_room = mapper.get_data_safe("building_data", f"buffs.{infrastructure_skill_id}.roomType") if infrastructure_skill_id else None
            infrastructure_skill_description = mapper.get_data_safe("building_data", f"buffs.{infrastructure_skill_id}.description") if infrastructure_skill_id else None

            temp_number += 1
            lines.append(f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}={infrastructure_skill_name if infrastructure_skill_name is not None else ''}")
            lines.append(f"|基建技能id{temp_number}={infrastructure_skill_id if infrastructure_skill_id is not None else ''}")
            lines.append(f"|基建技能图标{temp_number}={infrastructure_skill_icon if infrastructure_skill_icon is not None else ''}")
            lines.append(
                f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j][:-1]}{'条件' if j > 1 else '解锁'}={infrastructure_condition_map[infrastructure_skill_condition] if infrastructure_skill_condition is not None and infrastructure_skill_name is not None else ''}"
            )
            lines.append(
                f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}设施={INFRASTRUCTURE_ROOM[infrastructure_skill_room] if infrastructure_skill_room is not None else ''}"
            )
            lines.append(
                f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}效果={process_description(infrastructure_skill_description, trait_candidates, rich_styles, term_description_dict, None, term_index_cache) if infrastructure_skill_description is not None else ''}"
            )
    return lines


__all__ = ["render_operator_infrastructure_fields"]
