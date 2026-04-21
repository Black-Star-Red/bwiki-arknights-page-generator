"""Summon template render helpers."""

from __future__ import annotations

from arknights_toolbox.shared.globals import POTENTIAL_SUFFIX
from arknights_toolbox.shared.rendering.description_parser import process_description
from arknights_toolbox.shared.utils import PHASE


def render_summon_template_lines(
    mapper,
    summon_key,
    summon_name,
    owner_name,
    owner_star,
    trait_candidates,
    rich_styles,
    term_description_dict,
    position_map,
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
    lines.append(f"|英文名={mapper.get_data_safe('character_table', f'{summon_key}.appellation') if summon_key else ''}")
    feature = mapper.get_data_safe("character_table", f"{summon_key}.description") if summon_key else ""
    lines.append(f"|特性={feature if feature else '无'}")
    lines.append(f"|部署位={position_map.get(mapper.get_data_safe('character_table', f'{summon_key}.position'), '') if summon_key else ''}")
    for phase_idx in range(0, 3):
        keyframe_idx = 0 if phase_idx == 0 else 1
        phase_data = mapper.get_data_safe(
            "character_table", f"{summon_key}.phases" + f"[{phase_idx}].attributesKeyFrames[{keyframe_idx}].data"
        ) if summon_key else {}
        lift = phase_data.get("maxHp")
        atk = phase_data.get("atk")
        def_data = phase_data.get("def")
        magic = phase_data.get("magicResistance")
        if phase_idx == 0:
            lines.append(f"|初始生命={lift if lift is not None else ''}")
            lines.append(f"|初始攻击={atk if atk is not None else ''}")
            lines.append(f"|初始防御={def_data if def_data is not None else ''}")
            lines.append(f"|初始法抗={int(magic) if magic is not None else ''}")
            max_phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[0].attributesKeyFrames[1].data") if summon_key else {}
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

    summon_cost = mapper.get_data_safe("character_table", f"{summon_key}.phases[0].attributesKeyFrames[0].data") if summon_key else {}
    lines.append(f"|部署费用={summon_cost.get('cost', '') if summon_cost else ''}")
    if int(owner_star) >= 4:
        respawn_time = []
        phases_data = []
        for i in range(3):
            phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[{i}].attributesKeyFrames[0].data") if summon_key else {}
            respawn_time.append(phase_data.get("respawnTime"))
            max_phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[{i}].attributesKeyFrames[1].data") if summon_key else {}
            phases_data.append(max_phase_data.get("blockCnt", 0))
    elif int(owner_star) == 3:
        respawn_time = []
        phases_data = []
        for i in range(2):
            phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[{i}].attributesKeyFrames[0].data") if summon_key else {}
            respawn_time.append(phase_data.get("respawnTime"))
            max_phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[{i}].attributesKeyFrames[1].data") if summon_key else {}
            phases_data.append(max_phase_data.get("blockCnt", 0))
    elif int(owner_star) < 3:
        respawn_time = []
        phases_data = []
        phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[0].attributesKeyFrames[0].data") if summon_key else {}
        respawn_time.append(phase_data.get("respawnTime"))
        max_phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[0].attributesKeyFrames[1].data") if summon_key else {}
        phases_data.append(max_phase_data.get("blockCnt", 0))
    else:
        respawn_time, phases_data = [None] * 2
    first = phases_data[0] if phases_data else None
    block = phases_data[0] if phases_data and all(x == first for x in phases_data) else ("→".join(str(v) for v in phases_data) if phases_data else "")
    first = respawn_time[0] if respawn_time else None
    time_block = respawn_time[0] if respawn_time and all(x == first for x in respawn_time) else ("s→".join(str(v) for v in respawn_time) if respawn_time else "")
    lines.append(f"|阻挡数={block}")
    lines.append(f"|再部署={time_block}S")
    summon_phase_data = mapper.get_data_safe("character_table", f"{summon_key}.phases[0].attributesKeyFrames[0].data") if summon_key else {}
    atk_speed = summon_phase_data.get("attackSpeed")
    atk_time = summon_phase_data.get("baseAttackTime")
    taunt_level = summon_phase_data.get("tauntLevel")
    lines.append(f"|攻击速度={atk_speed if atk_speed else ''}")
    lines.append(f"|攻击间隔={atk_time if atk_time else ''}s")
    lines.append(f"|嘲讽等级={taunt_level if taunt_level is not None else ''}")
    range_id_data = []
    for i in range(0, 3):
        range_id = mapper.get_data_safe("character_table", f"{summon_key}.phases[{i}].rangeId") if summon_key else None
        range_id_data.append(range_id)
    lines.append(f"|初始攻击范围={range_id_data[0] if range_id_data[0] else ''}")
    lines.append(f"|精1攻击范围={range_id_data[1] if range_id_data[1] else ''}")
    lines.append(f"|精2攻击范围={range_id_data[2] if range_id_data[2] else ''}")

    for i in range(1, 3):
        talents_candidates = mapper.get_data_safe("character_table", f"{summon_key}.talents[{i-1}].candidates") if summon_key else []
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
            lines.append(f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}={talent if talent else ''}")
            lines.append(
                f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'解锁' if j < 1 else ''}{'提升' if j >= 1 else ''}条件={talent_condition if talent_condition is not None and talent else ''}"
            )
            lines.append(f"|天赋{i}{f'第{j}次' if j > 1 else ''}{'提升后' if j >= 1 else ''}描述={talent_description if talent_description else ''}")
        lines.append(f"|天赋{i}备注=")
        lines.append(f"|天赋{i}攻击范围=")

    for i in range(1, 4):
        skill_id = mapper.get_data_safe("character_table", f"{summon_key}.skills[{i-1}].skillId") if summon_key else None
        summon_skill_data = mapper.get_data_safe("skill_table", f"{skill_id}.levels") if skill_id else None
        summon_skill_name = summon_skill_data[i - 1].get("name") if summon_skill_data and len(summon_skill_data) > i - 1 else None
        skill_icon = summon_skill_data[i - 1].get("icon") if summon_skill_data and len(summon_skill_data) > i - 1 else None
        is_null_skill_icon = skill_icon if summon_skill_name != skill_icon else summon_skill_name
        skill_range = summon_skill_data[i - 1].get("rangeId") if summon_skill_data and len(summon_skill_data) > i - 1 else None
        sp_data = summon_skill_data[i - 1].get("spData", {}) if summon_skill_data and len(summon_skill_data) > i - 1 else {}
        skill_recover_type = sp_data.get("spType")
        skill_trigger_type = summon_skill_data[i - 1].get("skillType") if summon_skill_data and len(summon_skill_data) > i - 1 else None
        skill_type = summon_skill_data[i - 1].get("durationType") if summon_skill_data and len(summon_skill_data) > i - 1 else None
        lines.append(f"|技能{i}产生={summon_skill_name}")
        lines.append(f"|技能{i}={summon_skill_name if summon_skill_name is not None else ''}")
        lines.append(f"|skillId{i}={skill_id if skill_id is not None else ''}")
        lines.append(f"|skillIcon{i}={'' if is_null_skill_icon is None else skill_icon}")
        lines.append(f"|技能{i}类型={mapping_skill_type[skill_type] if skill_type is not None and skill_type != 'NONE' else ''}")
        lines.append(f"|技能{i}攻击范围={skill_range if skill_range is not None else ''}")
        lines.append(f"|技能{i}回复类型={skill_type_map[skill_recover_type] if skill_type_map.get(skill_recover_type) else ''}")
        lines.append(
            f"|技能{i}触发类型={skill_trigger_type_map[skill_trigger_type] if skill_trigger_type_map.get(skill_trigger_type) else ''}"
        )
        for j in range(1, 11):
            level_data = summon_skill_data[j - 1] if summon_skill_data and len(summon_skill_data) > j - 1 else {}
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
            lines.append(f"|技能{i}技力消耗{j}={skill_consume if skill_consume is not None else ''}")
            lines.append(f"|技能{i}初始技力{j}={skill_init if skill_init is not None else ''}")
            lines.append(f"|技能{i}持续时间{j}={skill_consistent_time if skill_consistent_time is not None else ''}")
        lines.append(f"|技能{i}备注=")
    lines.append("}}")
    return lines


__all__ = ["render_summon_template_lines"]
