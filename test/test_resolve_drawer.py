"""画师解析顺序：数据源 → 其它源 → 库内 OCR。"""

from shared.rendering.template_helpers import resolve_drawer_with_fallback


class _Mapper:
    def __init__(self, drawers: dict[str, dict[str, str]], current: str = "a"):
        self.config = {"data_sources": {"a": [], "b": []}}
        self.current_data_sources = current
        self._drawers = drawers

    def get_data_safe(self, source_id, key, default=None):
        if source_id == "skin_table" and key == "charSkins":
            return self._drawers.get(self.current_data_sources, {})
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


def _skin(char_id: str, drawer: str, designer: str = "") -> dict:
    return {
        "charId": char_id,
        "displaySkin": {
            "skinGroupId": "ILLUST_0",
            "drawerList": [drawer] if drawer else [],
            "designerList": [designer] if designer else [],
        },
    }


def test_current_source_first():
    m = _Mapper(
        {
            "a": {"s1": _skin("char_1", "A")},
            "b": {"s2": _skin("char_1", "B")},
        }
    )
    assert resolve_drawer_with_fallback(m, "char_1", db_drawer="DB") == "A"


def test_other_source_before_db():
    m = _Mapper(
        {
            "a": {},
            "b": {"s2": _skin("char_1", "B")},
        }
    )
    assert resolve_drawer_with_fallback(m, "char_1", db_drawer="DB") == "B"


def test_db_when_no_skins():
    m = _Mapper({"a": {}, "b": {}})
    assert resolve_drawer_with_fallback(m, "char_1", db_drawer="OCR画师") == "OCR画师"
