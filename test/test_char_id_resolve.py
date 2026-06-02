"""charId 解析：库内 char_id 与联动显示名。"""

import importlib.util
from pathlib import Path

_root = Path(__file__).resolve().parents[1]


def _load(rel: str):
    spec = importlib.util.spec_from_file_location("_mod", _root / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mapper_ops = _load("core/character_script/mapper_ops.py")
_resolve = _mapper_ops.resolve_operator_char_id_for_name
_char_in = _mapper_ops._char_id_in_table


class _FakeMapper:
    def __init__(self, table: dict, ids: list[str]):
        self._table = table
        self._ids = ids
        self.mappings = {"character_table": {}}

    def get_data(self, source_id, key=None):
        if key == "charIdS":
            return self._ids
        if source_id == "character_table":
            return self._table
        return {}

    def get_data_safe(self, source_id, key, default=None):
        cid = self.mappings.get("character_table", {}).get("currentCharId")
        if source_id == "character_table" and cid:
            row = self._table.get(cid, {})
            return row.get(key, default)
        return default


def test_stored_char_id_used_when_exact_name_missing():
    mapper = _FakeMapper(
        {"char_1038_orchid": {"name": "梓兰"}},
        ["char_1038_orchid"],
    )
    cid = _resolve(mapper, "焰狐龙梓兰", stored_char_id="char_1048_orchd2")
    assert cid == "char_1048_orchd2"


def test_exact_name_wins_over_stored():
    mapper = _FakeMapper(
        {
            "char_1048_orchd2": {"name": "焰狐龙梓兰"},
            "char_1038_orchid": {"name": "梓兰"},
        },
        ["char_1048_orchd2", "char_1038_orchid"],
    )
    cid = _resolve(mapper, "焰狐龙梓兰", stored_char_id="char_1038_orchid")
    assert cid == "char_1048_orchd2"
