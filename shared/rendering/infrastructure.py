"""Infrastructure skill field renderers."""

from __future__ import annotations

from data.mapper_helpers import bind_buff, bind_building_char, bind_buff_data_slot
from shared.globals import INFRASTRUCTURE_ROOM, INFRASTRUCTURE_SKILL_SUFFIX
from shared.rendering.description_parser import process_description
from shared.utils import PHASE


def _normalize_infra_phase(mapper, raw_phase):
    """应用 building_data.value_maps.phase（如 yuanyan 的 0 → PHASE_0）。"""
    if raw_phase is None:
        return None
    return mapper._apply_value_map("building_data", "phase", raw_phase)


def _normalize_infra_level(raw_level):
    if raw_level is None:
        return None
    try:
        return int(raw_level)
    except (TypeError, ValueError):
        return raw_level


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
    for i in range(1, 3):
        bind_building_char(mapper, char_id, i - 1)
        buff_data_list = mapper.get_data_safe("building_data", "char_buff_data", default=[]) or []
        for j in range(1, 4):
            buff_data = buff_data_list[j - 1] if len(buff_data_list) >= j else {}
            # buffData 条目为游戏原始键 buffId（非 snake_case）
            infrastructure_skill_id = buff_data.get("buffId")
            infrastructure_skill_icon = None
            infrastructure_skill_name = None
            infrastructure_skill_room = None
            infrastructure_skill_description = None
            if infrastructure_skill_id:
                bind_buff(mapper, infrastructure_skill_id)
                infrastructure_skill_name = mapper.get_data_safe("building_data", "buff_name")
                infrastructure_skill_room = mapper.get_data_safe("building_data", "buff_room_type")
                infrastructure_skill_description = mapper.get_data_safe("building_data", "buff_description")
                infrastructure_skill_icon = mapper.get_data_safe("building_data", "skillIcon")

            bind_buff_data_slot(mapper, char_id, i - 1, j - 1)
            infrastructure_skill_level = _normalize_infra_level(
                mapper.get_data_safe("building_data", "buff_cond_level")
            )
            infrastructure_skill_phase = _normalize_infra_phase(
                mapper,
                mapper.get_data_safe("building_data", "buff_cond_phase"),
            )
            infrastructure_skill_condition = (
                f"{PHASE(infrastructure_skill_phase)}"
                + (f"、{infrastructure_skill_level}级" if (infrastructure_skill_level is not None and infrastructure_skill_level > 1) else "")
            ) if ((infrastructure_skill_level is not None and infrastructure_skill_level > 1) or infrastructure_skill_phase != "PHASE_0") else "初始携带"

            # Wiki 模板：id1–id6 = 技能槽1 三档(1–3) + 技能槽2 三档(4–6)
            infra_flat_index = (i - 1) * 3 + j
            lines.append(f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}={infrastructure_skill_name if infrastructure_skill_name is not None else ''}")
            lines.append(f"|基建技能id{infra_flat_index}={infrastructure_skill_id if infrastructure_skill_id is not None else ''}")
            lines.append(f"|基建技能图标{infra_flat_index}={infrastructure_skill_icon if infrastructure_skill_icon is not None else ''}")
            lines.append(
                f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j][:-1]}{'条件' if j > 1 else '解锁'}={infrastructure_skill_condition if infrastructure_skill_condition is not None and infrastructure_skill_name is not None else ''}"
            )
            infra_desc = process_description(
                infrastructure_skill_description,
                trait_candidates,
                rich_styles,
                term_description_dict,
                None,
                term_index_cache,
            )
            lines.append(f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}效果={infra_desc}")
            lines.append(
                f"|基建技能{i}{INFRASTRUCTURE_SKILL_SUFFIX[j]}设施={INFRASTRUCTURE_ROOM[infrastructure_skill_room] if infrastructure_skill_room is not None else ''}"
            )
    return lines


__all__ = ["render_operator_infrastructure_fields"]
