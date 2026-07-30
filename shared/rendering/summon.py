"""Summon template render helpers."""

from __future__ import annotations

from data.mapper_helpers import (
    bind_keyframe_index,
    bind_operator,
    bind_phase_index,
    bind_skill_index,
    bind_skill_table_id,
    bind_talent_group,
)
from shared.globals import POTENTIAL_SUFFIX
from shared.rendering.description_parser import process_description
from shared.utils import PHASE

def _collect_token_keys(raw_value) -> list[str]:
    keys: list[str] = []
    if isinstance(raw_value, str):
        if raw_value.strip():
            keys.append(raw_value.strip())
        return keys
    if isinstance(raw_value, list):
        for item in raw_value:
            keys.extend(_collect_token_keys(item))
        return keys
    if isinstance(raw_value, dict):
        for v in raw_value.values():
            keys.extend(_collect_token_keys(v))
        return keys
    return keys
def collect_operator_token_keys(owner_row: dict) -> list[str]:
    """去重、保序：技能 overrideTokenKey → 天赋 tokenKey → 顶层 tokenKey → displayTokenDict。"""
    if not isinstance(owner_row, dict):
        return []
    out: list[str] = []
    seen: set[str] = set()
    def add(raw) -> None:
        for key in _collect_token_keys(raw):
            if key not in seen:
                seen.add(key)
                out.append(key)
    for skill in owner_row.get("skills") or []:
        add((skill or {}).get("overrideTokenKey"))
    for group in owner_row.get("talents") or []:
        for cand in (group or {}).get("candidates") or []:
            add((cand or {}).get("tokenKey"))
    add(owner_row.get("tokenKey"))
    for key in (owner_row.get("displayTokenDict") or {}):
        add(key)
    return out
def resolve_token_display_name(mapper, token_key: str) -> str:
    key = (token_key or "").strip()
    if not key:
        return ""
    bind_operator(mapper, key)
    return (mapper.get_data_safe("character_table", "operator_name") or "").strip()


def _operator_phase_attr(mapper, phase_index: int, keyframe_index: int) -> dict:
    bind_phase_index(mapper, phase_index)
    bind_keyframe_index(mapper, keyframe_index)
    data = mapper.get_data_safe("character_table", "operator_phase_attr_data", default={}) or {}
    return data if isinstance(data, dict) else {}


def render_summon_template_lines(
    mapper,
    summon_key,
    summon_name,
    owner_name,
    owner_star,
    trait_candidates,
    rich_styles,
    term_description_dict,
    mapping_skill_type,
    skill_type_map,
    skill_trigger_type_map,
    term_index_cache=None,
):
    """干员附属单位模板"""
    lines: list[str] = []
    lines.append("{{干员附带单位")
    lines.append(f"|charId={summon_key}")
    lines.append("|皮肤名=")
    lines.append(f"|单位名称={summon_name}")
    lines.append(f"|所属干员={owner_name}")
    if summon_key:
        bind_operator(mapper, summon_key)
    lines.append(f"|英文名={mapper.get_data_safe('character_table', 'operator_appellation') if summon_key else ''}")
    feature = mapper.get_data_safe("character_table", "operator_description") if summon_key else ""
    lines.append(f"|特性={feature if feature else '无'}")
    lines.append(f"|部署位={mapper.get_data_safe('character_table', 'operator_position') if summon_key else ''}")
    for phase_idx in range(0, 3):
        keyframe_idx = 0 if phase_idx == 0 else 1
        phase_data = _operator_phase_attr(mapper, phase_idx, keyframe_idx) if summon_key else {}
        lift = phase_data.get("maxHp")
        atk = phase_data.get("atk")
        def_data = phase_data.get("def")
        magic = phase_data.get("magicResistance")
        if phase_idx == 0:
            lines.append(f"|初始生命={lift if lift is not None else ''}")
            lines.append(f"|初始攻击={atk if atk is not None else ''}")
            lines.append(f"|初始防御={def_data if def_data is not None else ''}")
            lines.append(f"|初始法抗={int(magic) if magic is not None else ''}")
            max_phase_data = _operator_phase_attr(mapper, 0, 1) if summon_key else {}
            lift = max_phase_data.get("maxHp")
            atk = max_phase_data.get("atk")
            def_data = max_phase_data.get("def")
            magic = max_phase_data.get("magicResistance")
            lines.append(f"|初始生命max={lift if lift is not None else ''}")
            lines.append(f"|初始攻击max={atk if atk is not None else ''}")
            lines.append(f"|初始防御max={def_data if def_data is not None else ''}")
            lines.append(f"|初始法抗max={int(magic) if magic is not None else ''}")
        else:
            lines.append(f"|精{phase_idx}生命max={lift if lift is not None else ''}")
            lines.append(f"|精{phase_idx}攻击max={atk if atk is not None else ''}")
            lines.append(f"|精{phase_idx}防御max={def_data if def_data is not None else ''}")
            lines.append(f"|精{phase_idx}法抗max={int(magic) if magic is not None else ''}")

    summon_cost = _operator_phase_attr(mapper, 0, 0) if summon_key else {}
    lines.append(f"|部署费用={summon_cost.get('cost', '') if summon_cost else ''}")
    if int(owner_star) >= 4:
        respawn_time = []
        phases_data = []
        for i in range(3):
            phase_data = _operator_phase_attr(mapper, i, 0) if summon_key else {}
            respawn_time.append(phase_data.get("respawnTime"))
            max_phase_data = _operator_phase_attr(mapper, i, 1) if summon_key else {}
            phases_data.append(max_phase_data.get("blockCnt", 0))
    elif int(owner_star) == 3:
        respawn_time = []
        phases_data = []
        for i in range(2):
            phase_data = _operator_phase_attr(mapper, i, 0) if summon_key else {}
            respawn_time.append(phase_data.get("respawnTime"))
            max_phase_data = _operator_phase_attr(mapper, i, 1) if summon_key else {}
            phases_data.append(max_phase_data.get("blockCnt", 0))
    elif int(owner_star) < 3:
        respawn_time = []
        phases_data = []
        phase_data = _operator_phase_attr(mapper, 0, 0) if summon_key else {}
        respawn_time.append(phase_data.get("respawnTime"))
        max_phase_data = _operator_phase_attr(mapper, 0, 1) if summon_key else {}
        phases_data.append(max_phase_data.get("blockCnt", 0))
    else:
        respawn_time, phases_data = [None] * 2
    first = phases_data[0] if phases_data else None
    block = phases_data[0] if phases_data and all(x == first for x in phases_data) else ("→".join(str(v) for v in phases_data) if phases_data else "")
    first = respawn_time[0] if respawn_time else None
    time_block = respawn_time[0] if respawn_time and all(x == first for x in respawn_time) else ("s→".join(str(v) for v in respawn_time) if respawn_time else "")
    lines.append(f"|阻挡数={block}")
    lines.append(f"|再部署={time_block}s")
    summon_phase_data = _operator_phase_attr(mapper, 0, 0) if summon_key else {}
    atk_speed = summon_phase_data.get("attackSpeed")
    atk_time = summon_phase_data.get("baseAttackTime")
    taunt_level = summon_phase_data.get("tauntLevel")
    if isinstance(atk_speed, float) and atk_speed.is_integer():
        atk_speed = int(atk_speed)
    lines.append(f"|攻击速度={atk_speed if atk_speed else ''}")
    lines.append(f"|攻击间隔={atk_time if atk_time else ''}s")
    lines.append(f"|嘲讽等级={taunt_level if taunt_level is not None else ''}")
    range_id_data = []
    for i in range(0, 3):
        bind_phase_index(mapper, i)
        range_id = mapper.get_data_safe("character_table", "operator_phase_range_id") if summon_key else None
        range_id_data.append(range_id)
    lines.append(f"|初始攻击范围={range_id_data[0] if range_id_data[0] else ''}")
    lines.append(f"|精1攻击范围={range_id_data[1] if range_id_data[1] else ''}")
    lines.append(f"|精2攻击范围={range_id_data[2] if range_id_data[2] else ''}")

    for i in range(1, 3):
        bind_talent_group(mapper, i - 1)
        talents_candidates = mapper.get_data_safe("character_table", "operator_talent_candidates") if summon_key else []
        
        pre_talent=None#上一个天赋提升描述

        for j in range(0, 6):
            talent, talent_condition, talent_description = [None] * 3
            if talents_candidates and len(talents_candidates) > j:
                talent = talents_candidates[j].get("name")
                unlock_condition = talents_candidates[j - 1].get("unlockCondition", {}) if j > 0 else talents_candidates[j].get("unlockCondition", {})
                phase = mapper._apply_value_map("character_table", "phase", unlock_condition.get("phase"))
                required_potential_rank = talents_candidates[j].get("requiredPotentialRank", 0)
                talent_condition = (
                    PHASE(phase) + POTENTIAL_SUFFIX[str(required_potential_rank)]
                    if (phase != "PHASE_0" or required_potential_rank != 0)
                    else "初始携带"
                )
                talent_description = process_description(
                    talents_candidates[j].get("description"),
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    None,
                    term_index_cache,
                )
            if talent and talent_description != pre_talent:
                lines.append(f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}={talent}")
                lines.append(
                f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'解锁' if j < 1 else ''}{'提升' if j >= 1 else ''}条件={talent_condition if talent_condition is not None and talent else ''}"
                )
                lines.append(f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}描述={talent_description if talent_description else ''}")
                pre_talent=talent_description
        # lines.append(f"|天赋{i}备注=")
        # lines.append(f"|天赋{i}攻击范围=")
    # 输出技能序号（跳过空槽后从 1 起排）；i 仍是 character 技能槽 1..3
    id_number = 1
    for i in range(1, 4):
        bind_skill_index(mapper, i)
        skill_id = mapper.get_data_safe("character_table", "operator_skill_id") if summon_key else None
        summon_skill_data = None
        if skill_id:
            bind_skill_table_id(mapper, skill_id)
            summon_skill_data = mapper.get_data_safe("skill_table", "skill_levels")
        if not isinstance(summon_skill_data, list):
            summon_skill_data = []
        # head=1 级：名字/范围/类型等元数据；1..10 级内容在下方循环读
        head = summon_skill_data[0] if summon_skill_data else {}
        summon_skill_name = head.get("name")
        # 无名字或无描述视为占位技能，不输出
        if not summon_skill_name or not (head.get("description") or "").strip():
            continue
        skill_icon = head.get("icon")
        is_null_skill_icon = skill_icon if summon_skill_name != skill_icon else summon_skill_name
        skill_range = head.get("rangeId")
        sp_data = head.get("spData", {}) or {}
        skill_recover_type = sp_data.get("spType")
        skill_trigger_type = head.get("skillType")
        skill_type = head.get("durationType")
        # 解锁条件挂在召唤物 skills[槽位] 上，不是 skill_table
        op_skills = mapper.get_data_safe("character_table", "operator_skills", default=[]) or []
        skill_row = op_skills[i - 1] if isinstance(op_skills, list) and len(op_skills) >= i else {}
        unlock = (skill_row or {}).get("unlockCond") or (skill_row or {}).get("unlockCondition") or {}
        unlock_phase = mapper._apply_value_map("character_table", "phase", unlock.get("phase"))
        unlock_label = PHASE(unlock_phase) if unlock_phase else ""
        lines.append(f"|技能{id_number}={summon_skill_name}")
        lines.append(f"|技能{id_number}产生={summon_skill_name}")
        lines.append(f"|技能{id_number}解锁条件={unlock_label}")
        # lines.append(f"|skillId{id_number}={skill_id if skill_id is not None else ''}")
        # lines.append(f"|skillIcon{id_number}={'' if is_null_skill_icon is None else skill_icon}")
        # lines.append(f"|技能{id_number}类型={mapping_skill_type[skill_type] if skill_type is not None and skill_type != 'NONE' else ''}")
        lines.append(f"|技能{id_number}攻击范围={skill_range if skill_range is not None else ''}")
        lines.append(f"|技能{id_number}回复类型={skill_type_map[skill_recover_type] if skill_type_map.get(skill_recover_type) else ''}")
        lines.append(
            f"|技能{id_number}触发类型={skill_trigger_type_map[skill_trigger_type] if skill_trigger_type_map.get(skill_trigger_type) else ''}"
        )
        # 连续等级内容相同则合并（只留描述1/技力1…）；out_j 为合并后的档位号
        prev_key = object()
        out_j = 0
        for j in range(1, 11):
            level_data = summon_skill_data[j - 1] if len(summon_skill_data) > j - 1 else {}
            sp_data = level_data.get("spData", {}) or {}
            skill_consume = sp_data.get("spCost")
            skill_init = sp_data.get("initSp")
            skill_consistent_time = level_data.get("duration")
            if skill_consistent_time is not None:
                rounded = round(skill_consistent_time)
                if abs(skill_consistent_time - rounded) < 1e-10:
                    skill_consistent_time = int(rounded)
            # duration<0（如 -1）表示无限/不适用，Wiki 留空
            duration_out = (
                skill_consistent_time
                if skill_consistent_time is not None and skill_consistent_time >= 0
                else ""
            )
            skill_description = level_data.get("description")
            blackboard = level_data.get("blackboard", [])
            rendered_skill_desc = process_description(
                skill_description, trait_candidates, rich_styles, term_description_dict, blackboard, term_index_cache
            ).replace("\\n", "<br/>")
            key = (rendered_skill_desc, skill_consume, skill_init, duration_out)
            if key == prev_key:
                continue
            prev_key = key
            out_j += 1
            lines.append(f"|技能{id_number}描述{out_j}={rendered_skill_desc}")
            lines.append(f"|技能{id_number}技力消耗{out_j}={skill_consume if skill_consume is not None else ''}")
            lines.append(f"|技能{id_number}初始技力{out_j}={skill_init if skill_init is not None else ''}")
            lines.append(f"|技能{id_number}持续时间{out_j}={duration_out}")
        lines.append(f"|技能{id_number}备注=")
        id_number += 1
    lines.append("}}")
    return lines


__all__ = ["render_summon_template_lines"]
