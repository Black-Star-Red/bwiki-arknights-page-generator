"""干员页 + 语音模板生成主流程。"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Callable

import requests
from mwclient import Site

from core.script_logging import (
    log_error,
    log_info,
    log_warning,
    script_print as print,
)
from shared.globals import (
    DEFAULT_BILIBILI_MID,
    INFRASTRUCTURE_CONDITION,
    MAPPING_SKILL_TYPE as mapping_skill_type,
    SKILL_TRIGGER_TYPE as skill_trigger_type,
    SKILL_TYPE as skill_type,
    VOICE_MAP,
)
from shared.rendering import (
    process_description,
    render_operator_cv_fields,
    render_operator_dossier_fields,
    render_operator_infrastructure_fields,
    render_operator_potential_fields,
    render_operator_progression_fields,
    render_operator_skill_fields,
    render_operator_talent_fields,
    render_operator_trust_fields,
    render_operator_voice_template_lines,
    render_skill_materials,
    resolve_drawer_with_fallback,
    render_operator_skin_template_lines,
    render_summon_template_lines,
)
from shared.services import (
    build_bilibili_headers,
    build_hycdn_portrait_headers,
    build_wiki_headers,
    publish_wiki_page_if_enabled,
    upload_operator_portrait_if_enabled,
    upload_site_file_with_retry,
)
from shared.utils import safe_get

from data.mapper_helpers import bind_current_char, bind_power

from data.db import OperatorSupplementaryRepository
from data.db.engine import resolve_database_settings

from .mapper_ops import (
    _char_id_in_table,
    collect_cid_name_pairs,
    resolve_alter_for_operator,
    resolve_operator_char_id_for_name,
    set_current_char_id,
    sub_profession_name,
)
from .supplementary_labels import build_corner_labels, is_limited_dynamic, wiki_obtain_path
from .resolve_supplementary import resolve_supplementary_data
from .operator_template_no_local import (
    _empty_voice_template_lines,
    build_operator_parts_without_local_json,
)
from .wiki_ops import create_site_page, wiki_yes_no


def _team_power_names(mapper, power_ids: list) -> list[str]:
    names: list[str] = []
    for power_id in power_ids:
        bind_power(mapper, power_id)
        nm = mapper.get_data_safe("handbook_team_table", "power_name")
        if nm:
            names.append(str(nm))
    return names


def generate_template(
    voice_json,
    mapper,
    operator_filter: str | None = None,
    wiki_flags=None,
    interactive: bool = True,
    wiki_use_test_page: bool = True,
    wiki_confirm: Callable[[str, str], bool] | None = None,
    character_num: int = 3,
    dynamic_start_ts: int | None = None,
    dynamic_end_ts: int | None = None,
    activity_name: str | None = None,
    activity_is_main_theme: bool = False,
    force_bilibili_fetch: bool = False,
):
    """
    生成干员模板

    Args:
        voice_json: JSON数据
        mapper: 数据映射器实例
        wiki_flags: 非交互时生效，键 wiki_operator_page / wiki_voice_page / wiki_portrait
        interactive: True 时对 Wiki 操作逐项 input；False 时由 wiki_flags，且可经 wiki_confirm 二次确认
        wiki_use_test_page: True 时写入用户沙盒「用户:用户名/测试页」；False 时按真实词条标题写入
        wiki_confirm: 非交互且勾选允许时调用 (prompt, wiki_key) -> 是否执行写入
    """
    mid = str(mapper.config.get("bilibili_mid", DEFAULT_BILIBILI_MID))
    cookies = mapper.config.get("cookies", "") or ""
    headers = build_bilibili_headers(cookies, mid=mid)
    if not cookies.strip():
        log_warning("config.cookies 为空，B 站动态 API 可能返回空列表并回退数据库")
    site_headers = build_wiki_headers()
    selected = (operator_filter or "").strip()
    supplementary_data = resolve_supplementary_data(
        mapper,
        operator_filter=operator_filter,
        voice_json=voice_json,
        mid=mid,
        headers=headers,
        character_num=character_num,
        dynamic_start_ts=dynamic_start_ts,
        dynamic_end_ts=dynamic_end_ts,
        activity_name=activity_name,
        activity_is_main_theme=activity_is_main_theme,
        force_bilibili_fetch=force_bilibili_fetch,
    )
    if selected and not supplementary_data:
        return ""
    print(supplementary_data)
    parts = []
    gui_operator_outputs: list[tuple[str, str]] = []

    pool = requests.Session()
    SESSDATA = ""
    for i in mapper.config["cookies"].split(";"):
        if "SESSDATA" in i:
            SESSDATA = i.split("=")[1]
            break
    if SESSDATA == "":
        log_warning("SESSDATA is not set")
    cookies = {
        "SESSDATA": SESSDATA,
        "domain": ".biligame.com",
    }
    site = None

    def get_site():
        nonlocal site
        if site is not None:
            return site
        try:
            requests.utils.add_dict_to_cookiejar(pool.cookies, cookies)
            site = Site("wiki.biligame.com", path="/arknights/", scheme="https", pool=pool, custom_headers=site_headers)
            log_info("连接成功！站点名称：%s", site.site["sitename"])
            log_info("用户名: %s", site.username)
            return site
        except Exception as e:
            log_error("Wiki连接失败（懒连接）：%s", e)
            return None

    db_settings = resolve_database_settings(mapper.config)
    sup_repo = OperatorSupplementaryRepository(
        mapper.config,
        config_path=getattr(mapper, "config_path", None),
    )
    use_sup_db = sup_repo.available and db_settings["prefer_db"]

    for name, value in supplementary_data.items():
        stored_cid = sup_repo.get_char_id_by_name(name) if use_sup_db else None
        found_cid = resolve_operator_char_id_for_name(
            mapper, name, stored_char_id=stored_cid
        )
        alter_operator, alter_base_name = resolve_alter_for_operator(
            mapper, name, found_cid
        )
        parts: list[str] = []
        has_ammo_skill = False
        try:
            if found_cid is None:
                log_warning("未在 character_table 中找到干员：%s，游戏内字段留空", name)
                if alter_operator:
                    log_info(
                        "干员 %s 异格本体兜底（未进表）: %s (%s)",
                        name,
                        alter_operator,
                        alter_base_name,
                    )
                parts = build_operator_parts_without_local_json(
                    name,
                    value,
                    mapper,
                    alter_operator=alter_operator,
                    alter_base_name=alter_base_name,
                )
                Id = ""
            elif not _char_id_in_table(mapper, found_cid):
                log_info(
                    "干员 %s 使用库内 char_id=%s 生成简版模板（本地表无该 id）",
                    name,
                    found_cid,
                )
                parts = build_operator_parts_without_local_json(
                    name,
                    value,
                    mapper,
                    char_id=found_cid,
                    alter_operator=alter_operator,
                    alter_base_name=alter_base_name,
                )
                for idx, line in enumerate(parts):
                    if line.startswith("|charId="):
                        parts[idx] = f"|charId={found_cid}"
                        break
                Id = found_cid
            else:
                set_current_char_id(mapper,"character_table","currentCharId", found_cid)
                Id = found_cid
                parts.append("{{干员")
                parts.append(f"|干员代号={name}")
                parts.append("|背景=")
                parts.append(f"|实装日期={value.get('实装日期', '')}")
                parts.append(f"|charId={Id}")
                set_current_char_id(mapper,"character_table","currentCharId", Id)
                obtain = wiki_obtain_path(value)
                label = build_corner_labels(value, alter_operator=alter_operator or "")
                if label:
                    parts.append("|角标=" + "、".join(label))
                if is_limited_dynamic(value):
                    parts.append("|解限=否")
                if alter_operator:
                    parts.append(f"|异格干员={alter_operator}")
                    parts.insert(
                        0,
                        "{{多义词|同义名="
                        + f"{alter_base_name}"
                        + "|说明=是"
                        + f"{alter_base_name}"
                        + "的异格干员}}",
                    )
                parts.append(f"|英文名={mapper.get_data_safe('character_table', 'appellation') or ''}")
                parts.append(f"|职业={mapper.get_data_safe('character_table', 'profession')}")
                star = mapper.get_data_safe('character_table', 'rarity')
                parts.append(f"|星级={star}")
                parts.append(f"|干员编号={mapper.get_data_safe('character_table', 'displayNumber')}<!-- 类似B101格式的编号 -->")
                item = []
                main_power = mapper.get_data_safe("character_table", "mainPower")
                if main_power:
                    for i in main_power.values():
                        if i is not None:
                            item.append(i)
                parts.append(
                f"|阵营={'、'.join(_team_power_names(mapper, item))}<!-- 有多少写多少，顿号隔开 -->"
                )
                item.clear()
                subpower = mapper.get_data_safe("character_table", "subPower")
                if subpower:
                    for i in subpower:
                        for j in i.values():
                            if j is not None:
                                item.append(j)
                parts.append(f"|副阵营={'、'.join(_team_power_names(mapper, item))}")
                label = []
                pos_label = mapper.get_data_safe("character_table", "position")
                if pos_label:
                    label.append(pos_label)
                tag_list = mapper.get_data_safe("character_table", "tagList")
                if tag_list:
                    for i in tag_list:
                        label.append(i)
                parts.append(
                f"|标签={'、'.join(i for i in label if i)}<!-- 包括近战位/远程位，然后抄tag参数，顿号隔开 -->"
                )
                parts.append(f"|获取途径={obtain}")
                trait = mapper.get_data_safe("character_table", "trait")
                if isinstance(trait, dict):
                    trait_candidates = trait.get("candidates", [])
                else:
                    trait_candidates = []
                rich_styles = mapper.get_data_safe("gamedata_const", "richTextStyles")
                term_description_dict = mapper.get_data_safe("gamedata_const", "termDescriptionDict")
                term_index_cache = {}
                feature = process_description(
                mapper.get_data_safe("character_table", "description"),
                trait_candidates,
                rich_styles,
                term_description_dict,
                )
                parts.append(f"|特性={feature}")
                parts.append("|特性攻击范围=")
                parts.append(f"|分支={sub_profession_name(mapper, mapper.get_data_safe('character_table', 'subProfessionId'))}")

                parts.extend(render_operator_progression_fields(mapper, star))

                parts.append(f"|精二动态id={value['动态id'] if value.get('动态id') else ''}")

                level_up_cost = mapper.get_data_safe("character_table", "skill_level_up_cost_cond") or []
                skill_count = len(level_up_cost)
                for i in range(1, 4):
                    for j in range(7, 10):
                        if skill_count < i:
                            parts.append(f"|{i}技能{j}→{j+1}材料=")
                        else:
                            parts.append(
                                f"|{i}技能{j}→{j+1}材料={render_skill_materials(mapper, level_up_cost[i - 1], j - 6)}"
                            )
                parts.extend(
                    render_operator_talent_fields(
                        mapper,
                        trait_candidates,
                        rich_styles,
                        term_description_dict,
                        term_index_cache,
                    )
                )
                parts.extend(render_operator_potential_fields(mapper))

                for i in range(1, 7):
                    parts.append(
                    f"|技能{i}→{i+1}材料={render_skill_materials(mapper, mapper.get_data_safe('character_table', 'allSkillLvlup'), i)}"
                )

                parts.extend(render_operator_trust_fields(mapper))
                skill_lines, summon_entries, has_ammo_skill = render_operator_skill_fields(
                    mapper,
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    mapping_skill_type,
                    term_index_cache,
                )
                parts.extend(skill_lines)
                summon_array = set()
                for _, summon_key, summon_name in summon_entries:
                    summon_key = (summon_key or "").strip()
                    summon_name = (summon_name or "").strip()
                    if not summon_key or not summon_name or summon_name in summon_array:
                        continue
                    summon_lines = render_summon_template_lines(
                        mapper,
                        summon_key,
                        summon_name,
                        name,
                        star,
                        trait_candidates,
                        rich_styles,
                        term_description_dict,
                        mapping_skill_type,
                        skill_type,
                        skill_trigger_type,
                        term_index_cache,
                    )
                    if wiki_yes_no(
                        f"干员附带单位{summon_name}页面确定创建(Y/N):",
                        wiki_key="wiki_operator_page",
                        wiki_flags=wiki_flags,
                        interactive=interactive,
                        wiki_confirm=wiki_confirm,
                    ):
                        site_obj = get_site()
                        if site_obj is not None:
                            create_site_page(
                                site_obj,
                                summon_name,
                                "\n".join(summon_lines),
                                wiki_use_test_page,
                            )
                        else:
                            print("Wiki未连接，跳过创建召唤物页面")
                    summon_array.add(summon_name)
                    gui_operator_outputs.append(
                        (
                            summon_name.replace("|", "｜"),
                            "【干员附带单位】\n"
                            + ("-" * 56)
                            + "\n"
                            + "\n".join(summon_lines)
                        )
                    )
                parts.extend(
                render_operator_infrastructure_fields(
                    mapper,
                    Id,
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    INFRASTRUCTURE_CONDITION,
                    term_index_cache,
                )
                )

                drawer,drawer_source = resolve_drawer_with_fallback(
                    mapper, Id, db_drawer=value.get("画师")
                )
                if (
                    use_sup_db
                    and drawer.strip()
                    and drawer_source.startswith("skin_table") 
                    and drawer.strip() != (value.get("画师") or "").strip()
                ):
                    patch = dict(value)
                    patch["画师"] = drawer
                    sup_repo.upsert(
                        name,
                        patch,
                        char_id=Id or None,
                        source="skin_table",
                    )
                parts.append(f"|画师={drawer}")

                parts.extend(render_operator_skin_template_lines(mapper, Id))
                parts.extend(
                render_operator_dossier_fields(
                    mapper,
                    Id,
                    value,
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    safe_get_fn=safe_get,
                    process_description_fn=process_description,
                )
                )

                parts.extend(render_operator_cv_fields(mapper, Id))
                parts.append("}}")
                if has_ammo_skill:
                    parts.append("[[category:拥有弹药类技能的干员]]")
            main_wikitext = "\n".join(parts)

            publish_wiki_page_if_enabled(
                enabled=wiki_yes_no(
                    f"干员{name}页面确定创建(Y/N):",
                    wiki_key="wiki_operator_page",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                ),
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建干员页面",
            )

            parts.clear()
            if found_cid and _char_id_in_table(mapper, found_cid):
                parts.extend(render_operator_voice_template_lines(mapper, Id, name, VOICE_MAP))
            else:
                parts.extend(_empty_voice_template_lines(name))
            voice_wikitext = "\n".join(parts)
            safe_tab_name = name.replace("|", "｜")
            publish_wiki_page_if_enabled(
                enabled=wiki_yes_no(
                    f"干员{name}语音页面确定创建(Y/N):",
                    wiki_key="wiki_voice_page",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                ),
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}/默认/中文-普通话",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建语音页面",
            )
            parts.clear()
            portrait_enabled = False
            if (Id or "").strip():
                portrait_enabled = wiki_yes_no(
                    f"干员{name}半身像确定上传(Y/N):",
                    wiki_key="wiki_portrait",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                )
            upload_operator_portrait_if_enabled(
                enabled=portrait_enabled,
                requests_module=requests,
                get_site_fn=get_site,
                upload_fn=upload_site_file_with_retry,
                operator_id=Id,
                operator_name=name,
                headers=build_hycdn_portrait_headers(),
            )
            parts.clear()
            parts.append("{{材料图鉴")
            parts.append(f"|材料名称={name}招聘合同")
            parts.append(f"|材料介绍={mapper.get_data_safe('character_table', 'itemUsage') or ''}")
            parts.append(f"|材料备注={mapper.get_data_safe('character_table', 'itemDesc') or ''}")
            parts.append(f"|itemid={Id}")
            parts.append("|材料类型=干员信物")
            parts.append(f"|获得方式={mapper.get_data_safe('character_table', 'itemObtainApproach') or ''}")
            parts.append("|固定掉落=")
            parts.append("|大概率=")
            parts.append("|概率掉落=")
            parts.append("|小概率=")
            parts.append("|罕见=")
            parts.append("|额外物资=")
            parts.append("|基建生产=")
            parts.append(f"|稀有度={mapper.get_data_safe('character_table', 'rarity') or ''}")
            parts.append("|备注=")
            parts.append("}}")
            ContractAndToken_enabled = wiki_yes_no(
                    f"干员{name}招聘合同和信物页面确定创建(Y/N):",
                    wiki_key="wiki_ContractAndToken",
                    wiki_flags=wiki_flags,
                    interactive=interactive,
                    wiki_confirm=wiki_confirm,
                )
            publish_wiki_page_if_enabled(
                enabled=ContractAndToken_enabled,
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}的招聘合同",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建招聘合同页面",
            )
            Contract_wikitext = "\n".join(parts)
            parts.clear()
            potentialItemId = mapper.get_data_safe("character_table", "potentialItemId")
            if potentialItemId:
                set_current_char_id(mapper, "item_table", "item_id", potentialItemId)
                parts.append("{{材料图鉴")
                parts.append(f"|材料名称={mapper.get_data_safe('item_table', 'item_name') or ''}")
                parts.append(f"|材料介绍={mapper.get_data_safe('item_table', 'item_usage') or ''}")
                parts.append(f"|材料备注={mapper.get_data_safe('item_table', 'item_description') or ''}")
                parts.append(f"|itemid={potentialItemId}")
                parts.append("|材料类型=干员信物")
                parts.append(f"|获得方式={mapper.get_data_safe('item_table', 'item_obtain_approach') or ''}")
                parts.append("|固定掉落=")
                parts.append("|大概率=")
                parts.append("|概率掉落=")
                parts.append("|小概率=")
                parts.append("|罕见=")
                parts.append("|额外物资=")
                parts.append("|基建生产=")
                parts.append(f"|稀有度={mapper.get_data_safe('item_table', 'item_rarity') or ''}")
                parts.append("|备注=")
                parts.append("}}")
            publish_wiki_page_if_enabled(
                enabled=ContractAndToken_enabled,
                get_site_fn=get_site,
                create_site_page_fn=create_site_page,
                page_name=f"{name}的信物",
                page_content="\n".join(parts),
                wiki_use_test_page=wiki_use_test_page,
                offline_message="Wiki未连接，跳过创建信物页面",
            )
            Token_wikitext = "\n".join(parts)
            gui_operator_outputs.append(
                (
                    safe_tab_name,
                    "【干员页模板】\n"
                    + ("-" * 56)
                    + "\n"
                    + main_wikitext
                    + "\n\n【干员语音/套】\n"
                    + ("-" * 56)
                    + "\n"
                    + voice_wikitext
                    + "\n\n【招聘合同】\n"
                    + ("-" * 56)
                    + "\n"
                    + Contract_wikitext
                    + "\n\n【干员信物】\n"
                    + ("-" * 56)
                    + "\n"
                    + Token_wikitext
                )
            )
        except Exception:
            traceback.print_exc()
            error_msg = traceback.format_exc()
            print(error_msg)
            parts.append(name)
            parts.append(str(value))
            gui_operator_outputs.append(
                (str(name).replace("|", "｜"), f"（生成失败）\n\n{error_msg}")
            )
    if gui_operator_outputs:
        blocks: list[str] = []
        for tab_name, body in gui_operator_outputs:
            blocks.append(f"<<<ARK_GUI_OP|{tab_name}>>>\n{body}")
        return "\n\n".join(blocks)
    return "\n".join(parts)


def load_json_file(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
