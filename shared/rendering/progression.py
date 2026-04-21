"""Progression-related rendering helpers."""

from __future__ import annotations

from arknights_toolbox.shared.utils import PHASE


def Material(mapper, character_id, star, phase):
    """
    生成精英化材料模板片段。

    `character_id` 参数保留兼容，当前逻辑主要依赖 mapper 当前映射。
    """
    phases = mapper.get_data_safe("character_table", "phases")
    if not phases or len(phases) < 2:
        return ""
    evolve_costs = phases[phase].get("evolveCost") if phase < len(phases) else None
    if not isinstance(evolve_costs, list):
        evolve_costs = []
    if int(star) == 6:
        result = "{{data|龙门币|30000}}" if phase == 1 else "{{data|龙门币|180000}}"
        for cost in evolve_costs:
            item_id = cost.get("id")
            count = cost.get("count")
            item_name = mapper.get_data_safe("item_table", f"items.{item_id}.name", default=item_id if item_id is not None else "")
            result += f"{{{{data|{item_name}|{count}}}}}"
    elif int(star) == 5:
        result = "{{data|龙门币|20000}}" if phase == 1 else "{{data|龙门币|120000}}"
        for cost in evolve_costs:
            item_id = cost.get("id")
            count = cost.get("count")
            item_name = mapper.get_data_safe("item_table", f"items.{item_id}.name", default=item_id if item_id is not None else "")
            result += f"{{{{data|{item_name}|{count}}}}}"
    elif int(star) == 4:
        result = "{{data|龙门币|15000}}" if phase == 1 else "{{data|龙门币|60000}}"
        for cost in evolve_costs:
            item_id = cost.get("id")
            count = cost.get("count")
            item_name = mapper.get_data_safe("item_table", f"items.{item_id}.name", default=item_id if item_id is not None else "")
            result += f"{{{{data|{item_name}|{count}}}}}"
    elif int(star) == 3:
        result = "{{data|龙门币|10000}}"
    else:
        result = ""
    return result


def LevelUPEnhance(mapper, star, phase):
    """
    生成干员晋升时的属性/技能/天赋提升描述。
    """
    if int(star) < 3:
        return ""
    if int(star) == 3 and phase == 2:
        return ""

    content = "属性上限提升"
    cost0_path = "{phases}" + f"[{phase-1}].attributesKeyFrames[0].data.cost"
    cost1_path = "{phases}" + f"[{phase}].attributesKeyFrames[1].data.cost"
    cost0 = mapper.get_data_safe("character_table", cost0_path)
    cost1 = mapper.get_data_safe("character_table", cost1_path)
    if cost1 - cost0 > 0:
        content += f"<br/>增加部署费用{{{{color|ff6801|{cost1 - cost0}}}}}"

    if int(star) > 3:
        skills = mapper.get_data_safe("character_table", "{skills}", default=[]) or []
        if int(star) == 6 and len(skills) > phase:
            skill_id = skills[phase].get("skillId")
        elif len(skills) > phase:
            skill_id = skills[phase].get("skillId")
        else:
            skill_id = None
        if skill_id:
            levels = mapper.get_data_safe("skill_table", f"{skill_id}.levels", default=[]) or []
            skill_name = levels[0].get("name", "未知技能") if levels else "未知技能"
            content += f"<br/>获得新技能{{{{color|00b0ff|{skill_name}}}}}"

    talents = mapper.get_data_safe("character_table", "{talents}", default=[]) or []
    has_phase0_and_phase1 = False
    talents0_candidates = []

    def _norm_phase(v):
        return mapper._apply_value_map("character_table", "phase", v)

    if talents and len(talents) > 0:
        talents0_candidates = talents[0].get("candidates", [])
        has_phase0 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase-1}" for c in talents0_candidates)
        has_phase1 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}" for c in talents0_candidates)
        has_phase0_and_phase1 = has_phase0 and has_phase1
        if has_phase0_and_phase1 and talents0_candidates:
            talent_name = talents0_candidates[0].get("name", "未知天赋")
            content += f"<br/>天赋{{{{color|00b0ff|{talent_name}}}}}获得提升"

    has_phase0_and_phase1_2 = False
    if len(talents) > 1 and talents[1].get("candidates") and talents[1]["candidates"][0].get("name"):
        talents1_candidates = talents[1]["candidates"]
        has_phase0_2 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase-1}" for c in talents1_candidates)
        has_phase1_2 = any(_norm_phase(c.get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}" for c in talents1_candidates)
        has_phase0_and_phase1_2 = has_phase0_2 and has_phase1_2
        if has_phase0_and_phase1_2:
            talent_name2 = talents1_candidates[0].get("name", "未知天赋")
            content += f"<br/>天赋{{{{color|00b0ff|{talent_name2}}}}}获得提升"
        elif talents1_candidates and _norm_phase(talents1_candidates[0].get("unlockCondition", {}).get("phase")) == f"PHASE_{phase}":
            talent_name_new = talents1_candidates[0].get("name", "未知天赋")
            content += f"<br/>新获得天赋{{{{color|00b0ff|{talent_name_new}}}}}"

    if not has_phase0_and_phase1 and talents0_candidates:
        talent_name_first = talents0_candidates[0].get("name", "未知天赋")
        content += f"<br/>新获得天赋{{{{color|00b0ff|{talent_name_first}}}}}"

    phases = mapper.get_data_safe("character_table", "{phases}", default=[]) or []
    if len(phases) > phase:
        range_id_prev = phases[phase - 1].get("rangeId") if len(phases) > phase - 1 else None
        range_id_curr = phases[phase].get("rangeId")
        if range_id_prev != range_id_curr:
            content += "<br/>攻击范围扩大"

    trait = mapper.get_data_safe("character_table", "trait")
    if trait and trait.get("candidates"):
        for candidate in trait["candidates"]:
            unlock_condition = candidate.get("unlockCondition", {})
            phase_condition = unlock_condition.get("phase")
            if phase_condition and PHASE(phase_condition) == f"精英化{phase}":
                content += "<br/>{{color|00b0ff|特性}}更新"
                break

    if phase == 2:
        potential_item_id = mapper.get_data_safe("character_table", "{currentCharId}.potentialItemId", default="") or ""
        start = potential_item_id.rfind("_")
        if start != -1:
            mod_id = f"uniequip_001_{potential_item_id[start + 1:]}"
            equip_dict = mapper.get_data_safe("uniequip_table", "equipDict", {})
            if mod_id in equip_dict:
                content += "<br/>开启{{color|00b0ff|模组系统}}"

    return content


def render_operator_progression_fields(mapper, star):
    """
    渲染干员晋升与面板成长字段，返回可直接 append/extend 的模板行列表。
    """
    lines: list[str] = []
    phases0_data = mapper.get_data_safe("character_table", "{phases}[0].attributesKeyFrames[0].data")
    lines.append(f"|初始生命={phases0_data.get('maxHp', '') if phases0_data else ''}")
    lines.append(f"|初始攻击={phases0_data.get('atk', '') if phases0_data else ''}")
    lines.append(f"|初始防御={phases0_data.get('def', '') if phases0_data else ''}")
    lines.append(f"|初始法抗={int(phases0_data.get('magicResistance', 0)) if phases0_data else ''}")
    lines.append(f"|再部署={phases0_data.get('respawnTime', '') if phases0_data else ''}")
    lines.append(f"|部署费用={phases0_data.get('cost', '') if phases0_data else ''}")
    rdcCost = 0
    potential_ranks = mapper.get_data_safe("character_table", "potentialRanks")
    if potential_ranks:
        for i in range(len(potential_ranks)):
            if potential_ranks[i].get("description") == "部署费用-1":
                rdcCost += 1
    costPro = None
    zudang = None
    if int(star) >= 4:
        phase_data = mapper.get_data_safe("character_table", "{phases}[*].attributesKeyFrames[1].data")
        costPro = phase_data[2].get("cost", 0) - rdcCost if phase_data[2] else 0
        phases_data = []
        for i in range(3):
            if phase_data:
                phases_data.append(str(phase_data[i].get("blockCnt", 0)))
        zudang = "→".join(phases_data)
    elif int(star) == 3:
        phase_data = mapper.get_data_safe("character_table", "{phases}[*].attributesKeyFrames[1].data")
        costPro = phase_data[1].get("cost", 0) - rdcCost if phase_data[1] else 0
        phases_data = []
        for i in range(2):
            if phase_data:
                phases_data.append(str(phase_data.get("blockCnt", 0)))
        zudang = "→".join(phases_data)
    elif int(star) < 3:
        phases0_max_data = mapper.get_data_safe("character_table", "{phases}[0].attributesKeyFrames[1].data")
        costPro = phases0_max_data.get("cost", 0) - rdcCost if phases0_max_data else 0
        phases_data = []
        if phases0_max_data:
            phases_data.append(str(phases0_max_data.get("blockCnt", 0)))
        zudang = "→".join(phases_data)

    lines.append(f"|完美部署费用={costPro}<!-- 计算精二满潜费用 -->")
    lines.append(f"|阻挡数={zudang}")
    attack_speed = phases0_data.get("attackSpeed", 0) if phases0_data else 0
    if isinstance(attack_speed, float) and attack_speed.is_integer():
        attack_speed = int(attack_speed)
    lines.append(f"|攻击速度={attack_speed}<!-- 写攻击速度的值 -->")
    lines.append(f"|攻击间隔={phases0_data.get('baseAttackTime', '') if phases0_data else ''}<!-- 写攻击间隔的值 -->")
    lines.append("|bb备注=")
    lines.append(f"|初始攻击范围={mapper.get_data_safe('character_table', 'rangeId')[0]}")

    phases0_max_data = mapper.get_data_safe("character_table", "{phases}[0].attributesKeyFrames[1].data")
    lines.append(f"|初始生命max={phases0_max_data.get('maxHp', '') if phases0_max_data else ''}")
    lines.append(f"|初始攻击max={phases0_max_data.get('atk', '') if phases0_max_data else ''}")
    lines.append(f"|初始防御max={phases0_max_data.get('def', '') if phases0_max_data else ''}")
    lines.append(f"|初始法抗max={int(phases0_max_data.get('magicResistance', 0)) if phases0_max_data else ''}")
    lines.append(f"|精1等级需求={mapper.get_data_safe('character_table', '{phases}[0].maxLevel')}")
    lines.append(f"|精1提升={LevelUPEnhance(mapper, star, 1)}")
    lines.append(f"|精1材料={Material(mapper, '{phases}', star, 1)}")

    phases1_max_data = mapper.get_data_safe("character_table", "{phases}[1].attributesKeyFrames[1].data") if int(star) > 2 else None
    lines.append(f"|精1生命max={phases1_max_data.get('maxHp', '') if phases1_max_data else ''}")
    lines.append(f"|精1攻击max={phases1_max_data.get('atk', '') if phases1_max_data else ''}")
    lines.append(f"|精1防御max={phases1_max_data.get('def', '') if phases1_max_data else ''}")
    lines.append(f"|精1法抗max={int(phases1_max_data.get('magicResistance', 0)) if phases1_max_data else ''}")
    lines.append(f"|精1攻击范围={mapper.get_data_safe('character_table', 'rangeId')[1] if phases1_max_data else ''}")

    phases2_max_data = mapper.get_data_safe("character_table", "{phases}[2].attributesKeyFrames[1].data") if int(star) > 3 else None
    lines.append(f"|精2等级需求={mapper.get_data_safe('character_table', '{phases}[1].maxLevel') if phases2_max_data else ''}")
    lines.append(f"|精2提升={LevelUPEnhance(mapper, star, 2)}")
    lines.append(f"|精2材料={Material(mapper, '{phases}', star, 2)}")
    lines.append(f"|精2生命max={phases2_max_data.get('maxHp', '') if phases2_max_data else ''}")
    lines.append(f"|精2攻击max={phases2_max_data.get('atk', '') if phases2_max_data else ''}")
    lines.append(f"|精2防御max={phases2_max_data.get('def', '') if phases2_max_data else ''}")
    lines.append(f"|精2法抗max={int(phases2_max_data.get('magicResistance', 0)) if phases2_max_data else ''}")
    lines.append(f"|精2攻击范围={mapper.get_data_safe('character_table', '{phases}[2].rangeId') if phases2_max_data else ''}")
    return lines


__all__ = ["Material", "LevelUPEnhance", "render_operator_progression_fields"]
