"""附属单位模板生成。"""

from __future__ import annotations

from data.mapper_helpers import bind_operator

from core.script_logging import log_warning
from shared.globals import (
    MAPPING_SKILL_TYPE as mapping_skill_type,
    SKILL_TRIGGER_TYPE as skill_trigger_type,
    SKILL_TYPE as skill_type,
)
from shared.rendering.summon import (
    collect_operator_token_keys,
    render_summon_template_lines,
    resolve_token_display_name,
)

def resolve_summon_target_by_charid(mapper, summon_charid: str):
    """通过附属单位 charId(overrideTokenKey) 反查所属干员与召唤物信息。"""
    selected = (summon_charid or "").strip()
    if not selected:
        return None
    selected_lower = selected.lower()
    char_table = mapper.get_data("character_table")
    if not isinstance(char_table, dict):
        return None
    for owner_cid, owner_row in char_table.items():
        if not isinstance(owner_row, dict):
            continue
        owner_name = owner_row.get("name") or owner_cid
        owner_star = owner_row.get("rarity", 0)
        trait = owner_row.get("trait")
        if isinstance(trait, dict):
            trait_candidates = trait.get("candidates", [])
        else:
            trait_candidates = []
        rich_styles = mapper.get_data_safe("gamedata_const", "richTextStyles")
        term_description_dict = mapper.get_data_safe("gamedata_const", "termDescriptionDict")
        term_index_cache = {}
        skills = owner_row.get("skills") or []
        token_candidates: list[str] = []
        for skill in skills:
            token_key = (skill or {}).get("overrideTokenKey")
            token_key_str = (token_key or "").strip()
            if token_key_str:
                token_candidates.append(token_key_str)
        token_candidates.extend(_collect_token_keys(owner_row.get("tokenKey")))

        seen_keys: set[str] = set()
        for token_key_str in token_candidates:
            if token_key_str in seen_keys:
                continue
            seen_keys.add(token_key_str)
            if token_key_str:
                bind_operator(mapper, token_key_str)
            summon_name_str = (
                mapper.get_data_safe("character_table", "operator_name")
                if token_key_str
                else ""
            )
            summon_name_str = (summon_name_str or "").strip()
            if not token_key_str:
                continue
            if token_key_str.lower() == selected_lower or summon_name_str.lower() == selected_lower:
                return (
                    owner_name,
                    owner_star,
                    trait_candidates,
                    rich_styles,
                    term_description_dict,
                    token_key_str,
                    summon_name_str or token_key_str,
                    term_index_cache,
                )
    summon_row = char_table.get(selected)
    if not summon_row:
        for key in char_table.keys():
            if str(key).lower() == selected_lower:
                summon_row = char_table.get(key)
                selected = str(key)
                break
    if isinstance(summon_row, dict):
        rich_styles = mapper.get_data_safe("gamedata_const", "richTextStyles")
        term_description_dict = mapper.get_data_safe("gamedata_const", "termDescriptionDict")
        summon_name = summon_row.get("name") or selected
        return (
            "",
            0,
            [],
            rich_styles,
            term_description_dict,
            selected,
            summon_name,
            {},
        )
    return None


def generate_summon_template_by_charid(mapper, charid: str) -> str:
    """按附属单位 charId(overrideTokenKey) 输出 {{干员附带单位}} 模板。"""
    resolved = resolve_summon_target_by_charid(mapper, charid)
    if resolved is None:
        log_warning("未匹配到附属单位 charId：%s", charid)
        return ""
    (
        owner_name,
        owner_star,
        trait_candidates,
        rich_styles,
        term_description_dict,
        summon_key,
        summon_name,
        term_index_cache,
    ) = resolved

    lines = render_summon_template_lines(
        mapper,
        summon_key,
        summon_name,
        owner_name,
        owner_star,
        trait_candidates,
        rich_styles,
        term_description_dict,
        mapping_skill_type,
        skill_type,
        skill_trigger_type,
        term_index_cache,
    )
    return f"【{summon_name}】\n" + "\n".join(lines)
