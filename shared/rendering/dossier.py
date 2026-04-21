"""Handbook dossier parsing/rendering helpers."""

from __future__ import annotations

import re


def render_operator_dossier_fields(
    mapper,
    char_id,
    value,
    trait_candidates,
    rich_styles,
    term_description_dict,
    *,
    safe_get_fn,
    process_description_fn,
):
    """干员档案模板"""
    lines: list[str] = []
    birthday, birthday2, month, day, sex, people, birthplace, height, height2, is_infection, design_sex, experience, experience_name, manufacturer, birthplace2, produce_time, weight, repair_report, infection_status, objective_eesume, physic_intensity, battlefield_flexible, physiology_tolerance, tactic_plan, battle_technic, source_stone_skill_adaptability, diagnosis_analysis, file_one, file_two, file_three, file_four, promotion_record, promotion_archive, maximum_speed, hill_climbing_ability, braking_efficiency, pass_rate, endurance, structural_stability = [None] * 39
    secret_record = []
    char_text = mapper.get_data_safe("handbook_info_table", f"handbookDict.{char_id}") or {}
    for story_idx, story_text in enumerate(char_text.get("storyTextAudio") or []):
        mapper.add_mapping("handbook_info_table", "handbook_char_id", char_id)
        mapper.add_mapping("handbook_info_table", "handbook_story_index", str(story_idx))
        if story_text["storyTitle"] == "基础档案":
            base_story = safe_get_fn(story_text, ["stories", 0, "storyText"])
            if "【代号】" in base_story or "【姓名】" in base_story:
                birthday_data = re.search(r"【([^】]*)】(\d+)月(\d+)日", base_story)
                birthday = (f"{birthday_data.group(2)}月{birthday_data.group(3)}日") if birthday_data and birthday_data.group(1) == "生日" else ""
                birthday2 = (f"{birthday_data.group(2)}月{birthday_data.group(3)}日") if birthday_data and birthday_data.group(1) == "出厂日" else ""
                month = f"{birthday_data.group(2)}" if birthday_data else ""
                day = f"{birthday_data.group(3)}" if birthday_data else ""
                if not birthday_data:
                    birthday_data = re.search(r"【生日】(.+)\n", base_story)
                    birthday = f"{birthday_data.group(1)}" if birthday_data else ""
                sex_data = re.search(r"【性别】(.+)\n", base_story)
                sex = sex_data[1] if sex_data else ""
                people_data = re.search(r"【种族】(.+)\n", base_story)
                people = people_data[1] if people_data else ""
                birthplace_data = re.search(r"【出身地】(.+)\n", base_story)
                birthplace = birthplace_data[1] if birthplace_data else ""
                birthplace_data = re.search(r"【产地】(.+)\n", base_story) if birthplace_data is None else None
                birthplace2 = birthplace_data[1] if birthplace_data else ""
                height_data = re.search(r"【身高】(.+)\n", base_story)
                height = height_data[1] if height_data else ""
                height_data = re.search(r"【高度】(.+)\n", base_story) if height_data is None else None
                height2 = height_data[1] if height_data else ""
                infection_status_data = re.search(r"【矿石病感染情况】\n(.+)", base_story)
                infection_status = infection_status_data[1] if infection_status_data else ""
                is_infection = "是" if "确认为感染者" in infection_status else "否"
                experience_data = re.search(r"【(.*?)经验】(.+)\n", base_story)
                experience = experience_data[2] if experience_data else ""
                experience_name = (experience_data[1] + "经验") if experience_data else ""
                design_sex_data = re.search(r"【设定性别】(.+)\n", base_story)
                design_sex = design_sex_data[1] if design_sex_data else ""
                weight_data = re.search(r"【重量】(.+)\n", base_story)
                weight = weight_data[1] if weight_data else ""
                repair_report_data = re.search(r"【维护检测报告】\n(.+)", base_story)
                repair_report_data = re.search(r"【维护检测情况】\n(.+)", base_story) if repair_report_data is None else repair_report_data
                repair_report = repair_report_data[1] if repair_report_data else ""
                manufacturer_data = re.search(r"【制造商】(.+)\n", base_story)
                manufacturer = manufacturer_data[1] if manufacturer_data else ""
                produce_time_data = re.search(r"【出厂时间】(.+)\n", base_story)
                produce_time = produce_time_data[1] if produce_time_data else ""
        if story_text["storyTitle"] == "客观履历":
            objective_eesume = process_description_fn(safe_get_fn(story_text, ["stories", 0, "storyText"]), trait_candidates, rich_styles)
        if story_text["storyTitle"] == "综合体检测试":
            test_story = safe_get_fn(story_text, ["stories", 0, "storyText"])
            physic_intensity_data = re.search(r"【物理强度】(.+)\n", test_story)
            physic_intensity = physic_intensity_data[1] if physic_intensity_data else ""
            battlefield_flexible_data = re.search(r"【战场机动】(.+)\n", test_story)
            battlefield_flexible = battlefield_flexible_data[1] if battlefield_flexible_data else ""
            physiology_tolerance_data = re.search(r"【生理耐受】(.+)\n", test_story)
            physiology_tolerance = physiology_tolerance_data[1] if physiology_tolerance_data else ""
            tactic_plan_data = re.search(r"【战术规划】(.+)\n", test_story)
            tactic_plan = tactic_plan_data[1] if tactic_plan_data else ""
            battle_technic_data = re.search(r"【战斗技巧】(.+)\n", test_story)
            battle_technic = battle_technic_data[1] if battle_technic_data else ""
            source_stone_skill_adaptability_data = re.search(r"【源石技艺适应性】(.+)", test_story)
            source_stone_skill_adaptability = source_stone_skill_adaptability_data[1] if source_stone_skill_adaptability_data else ""
        if story_text["storyTitle"] == "临床诊断分析":
            unlock_type = mapper.get_data_safe("handbook_info_table", "handbook_story_unlock_type", default=None)
            story_txt = mapper.get_data_safe("handbook_info_table", "handbook_story_text", default="") or ""
            unlock_param = mapper.get_data_safe("handbook_info_table", "handbook_story_unlock_param", default="") or ""
            if unlock_type == "DIRECT":
                diagnosis_analysis = story_txt.replace("\n", "<br/>")
            elif unlock_type == "FAVOR":
                diagnosis_analysis = story_txt.replace("\n", "<br/>")
            elif unlock_type == "AWAKE":
                parts_param = (unlock_param or "").split(";")
                p0 = parts_param[0] if len(parts_param) > 0 else ""
                p1 = parts_param[1] if len(parts_param) > 1 else ""
                diagnosis_analysis = f"{p0}等级{p1}<br/>{story_txt.replace(chr(10), '<br/>')}"
            else:
                diagnosis_analysis = ""
        if story_text["storyTitle"] == "档案资料一":
            file_one = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        elif story_text["storyTitle"] == "档案资料二":
            file_two = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        elif story_text["storyTitle"] == "档案资料三":
            file_three = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        elif story_text["storyTitle"] == "档案资料四":
            file_four = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        elif story_text["storyTitle"] == "晋升记录":
            promotion_record = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        elif "升变档案" in story_text["storyTitle"]:
            promotion_archive = safe_get_fn(story_text, ["stories", 0, "storyText"]).replace("\n", "<br/>")
        if story_text["storyTitle"] == "综合性能检测结果":
            performance_story = safe_get_fn(story_text, ["stories", 0, "storyText"])
            maximum_speed_data = re.search(r"/【最高速度】(.+)\n/", performance_story)
            maximum_speed = maximum_speed_data[1] if maximum_speed_data else ""
            hill_climbing_ability_data = re.search(r"/【爬坡能力】(.+)\n/", performance_story)
            hill_climbing_ability = hill_climbing_ability_data[1] if hill_climbing_ability_data else ""
            braking_efficiency_data = re.search(r"/【制动效能】(.+)\n/", performance_story)
            braking_efficiency = braking_efficiency_data[1] if braking_efficiency_data else ""
            pass_rate_data = re.search(r"/【通过性】(.+)\n/", performance_story)
            pass_rate = pass_rate_data[1] if pass_rate_data else ""
            endurance_data = re.search(r"/【续航】(.+)\n/", performance_story)
            endurance = endurance_data[1] if endurance_data else ""
            structural_stability_data = re.search(r"/【结构稳定性】(.+)/", performance_story)
            structural_stability = structural_stability_data[1] if structural_stability_data else ""
        for i in range(1, 4):
            record = [
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "storySetName"]),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam1"]),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "unlockParam2"]),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "unlockParam", 1, "unlockParam1"]),
                safe_get_fn(char_text, ["handbookAvgList", i - 1, "unlockParam", 0, "storyIntro"]),
            ]
            secret_record.append(record)

    lines.append(f"|生日={birthday}")
    lines.append(f"|出厂日={birthday2}")
    lines.append(f"|月={month}")
    lines.append(f"|日={day}")
    lines.append(f"|性别={sex}")
    lines.append("|真实姓名=")
    lines.append("|职能=")
    lines.append(f"|种族={people}")
    lines.append(f"|出身={birthplace}")
    lines.append(f"|身高={height}")
    lines.append(f"|高度={height2}")
    lines.append(f"|是否感染={is_infection}")
    lines.append(f"|设定性别={design_sex}")
    lines.append(f"|专精={value['专精']}")
    lines.append(f"|经验={experience}<!--类似十年这样的文本-->")
    lines.append(f"|经验名称={experience_name}<!--不填写即显示战斗经验-->")
    lines.append(f"|制造商={manufacturer}")
    lines.append(f"|产地={birthplace2}")
    lines.append(f"|出厂时间={produce_time}")
    lines.append(f"|重量={weight}")
    lines.append(f"|维护检测报告={repair_report}")
    lines.append(f"|矿石病毒感染情况={infection_status}")
    lines.append(f"|客观履历={objective_eesume}")
    lines.append(f"|物理强度={physic_intensity}")
    lines.append(f"|战场机动={battlefield_flexible}")
    lines.append(f"|生理耐受={physiology_tolerance}")
    lines.append(f"|战术规划={tactic_plan}")
    lines.append(f"|战斗技巧={battle_technic}")
    lines.append(f"|源石技艺适应性={source_stone_skill_adaptability}")
    lines.append(f"|临床诊断分析={diagnosis_analysis}")
    lines.append(f"|档案资料一={file_one}")
    lines.append(f"|档案资料二={file_two}")
    lines.append(f"|档案资料三={file_three}")
    lines.append(f"|档案资料四={file_four}")
    lines.append(f"|晋升记录={promotion_record}")
    lines.append(f"|升变档案={promotion_archive if promotion_archive else ''}")
    lines.append(f"|档案资料五={value['宣传介绍']}")
    lines.append("|档案资料五标题=宣传介绍")
    lines.append(f"|最高速度={maximum_speed if maximum_speed else ''}")
    lines.append(f"|爬坡能力={hill_climbing_ability if hill_climbing_ability else ''}")
    lines.append(f"|制动效能={braking_efficiency if braking_efficiency else ''}")
    lines.append(f"|通过性={pass_rate if pass_rate else ''}")
    lines.append(f"|续航={endurance if endurance else ''}")
    lines.append(f"|结构稳定性={structural_stability if structural_stability else ''}")
    lines.append("|体检描述=")
    for i in range(1, 4):
        lines.append(f"|干员密录{i}={secret_record[i][0] if secret_record[i][0] else ''}")
        lines.append(
            f"|干员密录{i}解锁条件="
            + (
                f"[[文件: icon_e{secret_record[i][1]}_need.png|20px|link=|class=invert-color]]提升至精英阶段{secret_record[i][2]}等级{secret_record[i][3]}<br/>[[文件:icon_信赖.png|20px|link=|class=invert-color]]提升信赖至{secret_record[i][4]}"
                if secret_record[i][1]
                else ""
            )
        )
        lines.append(f"|干员密录{i}描述={secret_record[i][5] if secret_record[i][5] else ''}")
        lines.append(f"|干员密录{i}述描视频=")
    lines.append("|悖论模拟标题=")
    return lines


__all__ = ["render_operator_dossier_fields"]
