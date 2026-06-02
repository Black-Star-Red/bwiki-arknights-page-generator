"""DataMapper 当前干员上下文与分支名解析。"""

from __future__ import annotations

from shared.sp_char_meta import find_sp_char_alter_partner, resolve_char_id_by_sp_groups


def set_current_char_id(mapper, cid):
    """设置 character_table 的 currentCharId（供 {currentCharId} 路径替换）"""
    mapper.mappings.setdefault("character_table", {})
    mapper.mappings["character_table"]["currentCharId"] = cid


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
        set_current_char_id(mapper, cid)
        nm = mapper.get_data_safe("character_table", "name")
        if nm:
            pairs.append((str(cid), str(nm)))
    return pairs


def find_char_id_by_name(mapper, name: str) -> str | None:
    """按干员显示名在 character_table 中查找 charId；未找到返回 None。"""
    for cid in mapper.get_data("character_table", "charIdS"):
        set_current_char_id(mapper, cid)
        if mapper.get_data_safe("character_table", "name") == name:
            return cid
    return None


def _char_id_in_table(mapper, char_id: str) -> bool:
    table = mapper.get_data("character_table")
    return isinstance(table, dict) and bool(char_id) and char_id in table


def resolve_operator_char_id_for_name(
    mapper,
    name: str,
    *,
    stored_char_id: str | None = None,
) -> str | None:
    """
    解析模板用 charId：精确名 → 库内 char_id → spCharGroups 组内匹配
    → 最长「游戏名⊂显示名」→ 模糊匹配。
    """
    name = (name or "").strip()
    if not name:
        return None
    exact = find_char_id_by_name(mapper, name)
    if exact:
        return exact
    stored = (stored_char_id or "").strip()
    if stored:
        return stored
    sp_cid = resolve_char_id_by_sp_groups(mapper, name)
    if sp_cid:
        return sp_cid
    best_len = -1
    best_cid: str | None = None
    for cid in mapper.get_data("character_table", "charIdS") or []:
        set_current_char_id(mapper, cid)
        nm = (mapper.get_data_safe("character_table", "name") or "").strip()
        if nm and nm in name and len(nm) > best_len:
            best_len = len(nm)
            best_cid = str(cid)
    if best_cid:
        return best_cid
    return resolve_operator_char_id(mapper, name)


def resolve_alter_operator_char_id(mapper, char_id: str) -> tuple[str | None, str | None]:
    """异格/联动皮对应本体 (charId, 显示名)；优先 char_meta spCharGroups。"""
    return find_sp_char_alter_partner(mapper, char_id)


def resolve_operator_char_id(mapper, selected: str) -> str | None:
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
