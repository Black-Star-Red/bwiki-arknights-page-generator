"""skin_table → 干员模板 |皮肤= 字段。"""

from shared.rendering.template_helpers import (
    collect_operator_skin_names,
    render_operator_skin_template_lines,
    resolve_operator_skin_names_with_fallback,
)


class _Mapper:
    def __init__(self, skins: dict[str, dict], current: str = "a"):
        self.config = {"data_sources": {"a": [], "b": []}}
        self.current_data_sources = current
        self._skins = skins

    def get_data_safe(self, source_id, key, default=None):
        if source_id == "skin_table" and key == "charSkins":
            return self._skins.get(self.current_data_sources, {})
        return default

    def temporary_source_group(self, alt: str):
        return _Ctx(self, alt)


class _Ctx:
    def __init__(self, mapper: _Mapper, alt: str):
        self._mapper = mapper
        self._alt = alt
        self._prev = ""

    def __enter__(self):
        self._prev = self._mapper.current_data_sources
        self._mapper.current_data_sources = self._alt
        return self._mapper

    def __exit__(self, *args):
        self._mapper.current_data_sources = self._prev


def _entry(char_id: str, skin_name: str, **extra: object) -> dict:
    return {
        "charId": char_id,
        "displaySkin": {"skinName": skin_name, **extra},
    }


def test_collect_by_char_id_and_regex_key():
    skins = {
        "char_193_frostl@boc#4": _entry("char_193_frostl", "寒冬信使"),
        "char_193_frostl@whirl#3": _entry("char_193_frostl", "覆雪"),
        "char_002_amiya@other#1": _entry("char_002_amiya", "播种者"),
    }
    m = _Mapper({"a": skins})
    assert collect_operator_skin_names(m, "char_193_frostl") == [
        "寒冬信使",
        "覆雪",
    ]


def test_collect_char_id_from_key_when_field_missing():
    skins = {
        "char_999_test@skin#1": {
            "displaySkin": {"skinName": "测试皮"},
        },
    }
    m = _Mapper({"a": skins})
    assert collect_operator_skin_names(m, "char_999_test") == ["测试皮"]


def test_render_skin_template_lines():
    skins = {
        "char_1@a#1": _entry("char_1", "皮A"),
        "char_1@b#2": _entry("char_1", "皮B"),
    }
    m = _Mapper({"a": skins})
    lines = render_operator_skin_template_lines(m, "char_1")
    assert lines[0] == "|皮肤=皮A"
    assert lines[1] == "|skin1动态id="
    assert lines[2] == "|皮肤2=皮B"
    assert lines[3] == "|skin2动态id="
    assert lines[4] == "|皮肤3="
    assert lines[-1] == "|skin6动态id="


def test_fallback_other_data_source():
    m = _Mapper(
        {
            "a": {},
            "b": {"char_1@x#1": _entry("char_1", "备用源")},
        }
    )
    assert resolve_operator_skin_names_with_fallback(m, "char_1") == ["备用源"]
