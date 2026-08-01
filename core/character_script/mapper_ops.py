"""DataMapper 当前干员上下文与分支名解析。"""

from __future__ import annotations

from shared.sp_char_meta import find_sp_char_alter_partner


def set_current_char_id(mapper, table_name, id_name, id):
    """设置 character_table 的 currentCharId（供 {currentCharId} 路径替换）"""
    mapper.mappings.setdefault(f"{table_name}", {})
    mapper.mappings[f"{table_name}"][f"{id_name}"] = id


def current_character_row(mapper):
    """通过公开接口取当前干员整行数据（避免直接读 data_cache）"""
    cid = mapper.mappings.get("character_table", {}).get("currentCharId")
    if not cid:
        return None
    table = mapper.get_data("character_table")
    if not isinstance(table, dict):
        return None
    return table.get(cid)


def collect_cid_name_pairs(mapper) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for cid in mapper.get_data("character_table", "charIdS"):
        set_current_char_id(mapper, "character_table", "currentCharId", cid)
        nm = mapper.get_data_safe("character_table", "name")
        if nm:
            pairs.append((str(cid), str(nm)))
    return pairs


def find_char_id_by_name(mapper, name: str) -> str | None:
    """按干员显示名在 character_table 中查找 charId；未找到返回 None。"""
    for cid in mapper.get_data("character_table", "charIdS"):
        set_current_char_id(mapper, "character_table", "currentCharId", cid)
        if mapper.get_data_safe("character_table", "name") == name:
            return cid
    return None


def _char_id_in_table(mapper, char_id: str) -> bool:
    table = mapper.get_data("character_table")
    return isinstance(table, dict) and bool(char_id) and char_id in table


def _table_name_for_cid(mapper, char_id: str) -> str:
    if not _char_id_in_table(mapper, char_id):
        return ""
    prev = mapper.mappings.get("character_table", {}).get("currentCharId")
    try:
        set_current_char_id(mapper, "character_table", "currentCharId", char_id)
        return (mapper.get_data_safe("character_table", "name") or "").strip()
    finally:
        set_current_char_id(mapper, "character_table", "currentCharId", prev)


def resolve_operator_char_id_for_name(
    mapper,
    name: str,
    *,
    stored_char_id: str | None = None,
) -> str | None:
    """
    解析「当前干员」charId（仅本人，不当异格本体）。

    精确名 → 库内 char_id（表内须与显示名一致；表外 id 可保留作简版）→ None。
    「游戏名 ⊂ 显示名」不在此返回，见 guess_alter_base_by_name_substring。
    """
    name = (name or "").strip()
    if not name:
        return None
    exact = find_char_id_by_name(mapper, name)
    if exact:
        return exact
    stored = (stored_char_id or "").strip()
    if not stored:
        return None
    if _char_id_in_table(mapper, stored):
        if _table_name_for_cid(mapper, stored) == name:
            return stored
        return None
    return stored


def guess_alter_base_by_name_substring(
    mapper, display_name: str
) -> tuple[str | None, str]:
    """
    异格本体兜底：最长「游戏名 ⊂ 显示名」且游戏名 ≠ 显示名。

    只用于 |异格干员= / 角标「异」，禁止当作当前 charId。
    """
    display_name = (display_name or "").strip()
    if not display_name:
        return None, ""
    prev = mapper.mappings.get("character_table", {}).get("currentCharId")
    best_len = -1
    best_cid: str | None = None
    best_nm = ""
    try:
        for cid in mapper.get_data("character_table", "charIdS") or []:
            set_current_char_id(mapper, "character_table", "currentCharId", cid)
            nm = (mapper.get_data_safe("character_table", "name") or "").strip()
            if not nm or nm == display_name:
                continue
            if nm in display_name and len(nm) > best_len:
                best_len = len(nm)
                best_cid = str(cid)
                best_nm = nm
        return best_cid, best_nm
    finally:
        set_current_char_id(mapper, "character_table", "currentCharId", prev)


def resolve_alter_for_operator(
    mapper,
    display_name: str,
    found_cid: str | None,
) -> tuple[str | None, str]:
    """
    异格本体：优先 char_meta spCharGroups；否则短名⊂长名兜底。
    当前 id 已是猜到的本体时不标异格。
    """
    cid = (found_cid or "").strip() or None
    if cid and _char_id_in_table(mapper, cid):
        alter, base_name = find_sp_char_alter_partner(mapper, cid)
        if alter:
            return str(alter), (base_name or "").strip()
    base_cid, base_nm = guess_alter_base_by_name_substring(mapper, display_name)
    if not base_cid:
        return None, ""
    if cid and cid == base_cid:
        return None, ""
    return base_cid, base_nm


def resolve_alter_operator_char_id(mapper, char_id: str) -> tuple[str | None, str | None]:
    """异格/联动皮对应本体 (charId, 显示名)；优先 char_meta spCharGroups。"""
    return find_sp_char_alter_partner(mapper, char_id)


def resolve_operator_char_id(mapper, selected: str) -> str | None:
    """手输短关键字兜底（CLI/指定干员）；B 站批量名解析勿依赖此层。"""
    selected = (selected or "").strip().lower()
    if not selected:
        return None
    for cid, name in collect_cid_name_pairs(mapper):
        if selected == cid.lower() or selected == name.lower() or selected in name.lower():
            return cid
    return None


def sub_profession_name(mapper, sub_profession_id):
    if sub_profession_id is None or sub_profession_id == "":
        return ""
    mapper.add_mapping("uniequip_table", "subProfessionId", sub_profession_id)
    return mapper.get_data_safe("uniequip_table", "sub_profession_name", default="")
