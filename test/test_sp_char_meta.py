"""spCharGroups：charId 与异格本体解析。"""

import importlib.util
from pathlib import Path

_root = Path(__file__).resolve().parents[1]


def _load(rel: str):
    spec = importlib.util.spec_from_file_location("_mod", _root / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mapper_ops = _load("core/character_script/mapper_ops.py")
_sp = _load("shared/sp_char_meta.py")
_resolve = _mapper_ops.resolve_operator_char_id_for_name
_alter = _mapper_ops.resolve_alter_operator_char_id

_ORCH_GROUPS = {
    "char_278_orchid": ["char_278_orchid", "char_1048_orchd2"],
}
_CATAP_GROUPS = {
    "char_282_catap": ["char_282_catap", "char_1049_catap2"],
}


class _FakeMapper:
    def __init__(
        self,
        table: dict,
        ids: list[str],
        *,
        sp_groups: dict | None = None,
    ):
        self._table = table
        self._ids = ids
        self._sp_groups = sp_groups or {}
        self.mappings = {"character_table": {}}

    def get_data(self, source_id, key=None):
        if key == "charIdS":
            return self._ids
        if source_id == "character_table":
            return self._table
        if source_id == "char_meta_table" and key == "spCharGroups":
            return self._sp_groups
        if source_id == "char_meta_table" and key is None:
            return {"spCharGroups": self._sp_groups}
        return {}

    def get_data_safe(self, source_id, key, default=None):
        cid = self.mappings.get("character_table", {}).get("currentCharId")
        if source_id == "character_table" and cid:
            row = self._table.get(cid, {})
            return row.get(key, default)
        return default


def test_sp_group_resolves_collab_skin_over_base_substring():
    mapper = _FakeMapper(
        {
            "char_278_orchid": {"name": "梓兰"},
            "char_1048_orchd2": {"name": "焰狐龙梓兰"},
        },
        ["char_278_orchid", "char_1048_orchd2"],
        sp_groups=_ORCH_GROUPS,
    )
    assert _resolve(mapper, "焰狐龙梓兰") == "char_1048_orchd2"


def test_sp_group_without_meta_falls_back_to_longest_substring():
    mapper = _FakeMapper(
        {
            "char_278_orchid": {"name": "梓兰"},
            "char_1048_orchd2": {"name": "焰狐龙梓兰"},
        },
        ["char_278_orchid", "char_1048_orchd2"],
        sp_groups=None,
    )
    assert _resolve(mapper, "焰狐龙梓兰") == "char_1048_orchd2"


def test_alter_partner_collab_skin_points_to_base():
    mapper = _FakeMapper(
        {
            "char_278_orchid": {"name": "梓兰", "isSpChar": False},
            "char_1048_orchd2": {"name": "焰狐龙梓兰", "isSpChar": True},
        },
        ["char_278_orchid", "char_1048_orchd2"],
        sp_groups=_ORCH_GROUPS,
    )
    base, nm = _alter(mapper, "char_1048_orchd2")
    assert base == "char_278_orchid"
    assert nm == "梓兰"


def test_alter_partner_standard_alter():
    mapper = _FakeMapper(
        {
            "char_282_catap": {"name": "空爆", "isSpChar": False},
            "char_1049_catap2": {"name": "空爆S", "isSpChar": True},
        },
        ["char_282_catap", "char_1049_catap2"],
        sp_groups=_CATAP_GROUPS,
    )
    base, nm = _alter(mapper, "char_1049_catap2")
    assert base == "char_282_catap"
    assert nm == "空爆"


def test_base_char_has_no_alter_partner():
    mapper = _FakeMapper(
        {
            "char_282_catap": {"name": "空爆"},
            "char_1049_catap2": {"name": "空爆S"},
        },
        ["char_282_catap", "char_1049_catap2"],
        sp_groups=_CATAP_GROUPS,
    )
    assert _alter(mapper, "char_282_catap") == (None, None)
