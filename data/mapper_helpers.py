"""DataMapper 逻辑字段绑定（配合 config field_mappings 使用）。"""

from __future__ import annotations


def bind_current_char(mapper, char_id: str) -> None:
    mapper.add_mapping("character_table", "currentCharId", char_id)


def bind_operator(mapper, operator_id: str) -> None:
    mapper.add_mapping("character_table", "operator_id", operator_id)


def bind_phase_index(mapper, phase_index: int) -> None:
    mapper.add_mapping("character_table", "phase_index", str(phase_index))


def bind_keyframe_index(mapper, keyframe_index: int) -> None:
    mapper.add_mapping("character_table", "keyframe_index", str(keyframe_index))


def bind_skill_index(mapper, skill_index: int) -> None:
    """skill_index 为 1-based（与 Wiki 技能编号一致），映射为 0-based 下标。"""
    mapper.add_mapping("character_table", "skill_index", str(skill_index - 1))


def bind_skill_list_index(mapper, list_index: int) -> None:
    """character_table.skills 数组下标（0-based）。"""
    mapper.add_mapping("character_table", "skill_index", str(list_index))


def bind_talent_group(mapper, group_index: int) -> None:
    mapper.add_mapping("character_table", "talent_group_index", str(group_index))


def bind_talent_candidate(mapper, candidate_index: int) -> None:
    mapper.add_mapping("character_table", "talent_candidate_index", str(candidate_index))


def bind_building_char(mapper, char_id: str, buff_char_index: int) -> None:
    mapper.add_mapping("building_data", "char_id", char_id)
    mapper.add_mapping("building_data", "buff_char_index", str(buff_char_index))


def bind_buff(mapper, buff_id: str) -> None:
    mapper.add_mapping("building_data", "buff_id", buff_id)


def bind_buff_data_slot(
    mapper,
    char_id: str,
    buff_char_index: int,
    buff_data_index: int,
) -> None:
    bind_building_char(mapper, char_id, buff_char_index)
    mapper.add_mapping("building_data", "buff_data_index", str(buff_data_index))


def bind_power(mapper, power_id: str) -> None:
    mapper.add_mapping("handbook_team_table", "power_id", str(power_id))


def bind_skill_table_id(mapper, skill_id: str) -> None:
    mapper.add_mapping("skill_table", "skill_id", skill_id)


def bind_item(mapper, item_id: str) -> None:
    mapper.add_mapping("item_table", "item_id", str(item_id))


def bind_handbook_char(mapper, char_id: str) -> None:
    mapper.add_mapping("handbook_info_table", "handbook_char_id", char_id)


def bind_charword(mapper, char_id: str, *, voice_key: str | None = None) -> None:
    mapper.add_mapping("charword_table", "char_id", char_id)
    if voice_key is not None:
        mapper.add_mapping("charword_table", "voice_key", voice_key)


__all__ = [
    "bind_buff",
    "bind_buff_data_slot",
    "bind_building_char",
    "bind_charword",
    "bind_current_char",
    "bind_handbook_char",
    "bind_item",
    "bind_keyframe_index",
    "bind_operator",
    "bind_phase_index",
    "bind_power",
    "bind_skill_index",
    "bind_skill_list_index",
    "bind_skill_table_id",
    "bind_talent_candidate",
    "bind_talent_group",
]
