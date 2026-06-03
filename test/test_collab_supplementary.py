"""联动活动识别与角标。"""

import importlib.util
import re
from pathlib import Path

_root = Path(__file__).resolve().parents[1]

COLLAB_ACTIVITY_RE = re.compile(r"^【明日方舟\s*[×xX][^】]+】")


def _load_module(name: str, rel_path: str):
    import sys

    spec = importlib.util.spec_from_file_location(name, _root / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_collab_shared = _load_module("collab_supplementary", "shared/collab_supplementary.py")
_labels = _load_module("supplementary_labels", "core/character_script/supplementary_labels.py")
_bili = _load_module("bilibili_service", "shared/services/bilibili_service.py")

build_corner_labels = _labels.build_corner_labels
enrich_collab_meta = _collab_shared.enrich_collab_meta
is_collaboration = _labels.is_collaboration
is_limited_dynamic = _labels.is_limited_dynamic
_dynamic_is_collaboration = _bili._dynamic_is_collaboration


def test_collab_activity_re_matches():
    assert COLLAB_ACTIVITY_RE.match("【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启")
    assert COLLAB_ACTIVITY_RE.match("【明日方舟×怪物猎人】活动")
    assert not COLLAB_ACTIVITY_RE.match("SideStory「xxx」")


def test_dynamic_is_collaboration():
    item = {
        "modules": [
            {
                "module_desc": {
                    "rich_text_nodes": [
                        {"orig_text": "【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启"},
                        {"orig_text": "其他文案"},
                    ]
                }
            }
        ]
    }
    assert _dynamic_is_collaboration(item, COLLAB_ACTIVITY_RE)
    assert not _dynamic_is_collaboration({"modules": []}, COLLAB_ACTIVITY_RE)


def test_is_collaboration_bool():
    assert is_collaboration({"联动": True})
    assert is_collaboration(
        {"获取途径": "联动、联动寻访、【幽境狩人】寻访"}
    )
    assert not is_collaboration({"联动": False, "获取途径": "标准寻访"})


def test_enrich_collab_meta_from_obtain_path():
    out = enrich_collab_meta(
        {"获取途径": "联动、联动寻访、【幽境狩人】寻访", "实装日期": "x"}
    )
    assert out["联动"] is True
    assert out["联动卡池"] == "幽境狩人"


def test_collab_event_standard_pools_get_lian_label():
    """联动期内 新增干员仅「联」；活动奖励为「联、活」。"""
    assert build_corner_labels({"联动": True, "获取途径": "标准寻访"}) == ["联"]
    assert build_corner_labels(
        {"联动": True, "获取途径": "联动、联动寻访、【幽境狩人】寻访"}
    ) == ["联"]
    assert build_corner_labels(
        {"联动": True, "获取途径": "【泡影苍霆】活动获取、活动获取、联动"}
    ) == ["联", "活"]
    assert build_corner_labels(
        {"联动": True, "获取途径": "标准寻访"},
        alter_operator="char_409_1bison",
    ) == ["联", "异"]
    assert build_corner_labels(
        {
            "联动": True,
            "获取途径": "【泡影苍霆】活动获取、活动获取、联动",
        },
        alter_operator="char_409_1bison",
    ) == ["联", "活", "异"]


def test_build_corner_labels_collab():
    value = {
        "联动": True,
        "联动卡池": "砺火成锋",
        "获取途径": "联动、联动寻访、【砺火成锋】寻访",
        "动态id": "123",
    }
    assert build_corner_labels(value) == ["联"]
    assert build_corner_labels(value, alter_operator="char_123") == ["联", "异"]
    assert not is_limited_dynamic(value)


def test_build_corner_labels_limited():
    value = {"动态id": "123", "获取途径": "限定寻访、【春节】限定寻访"}
    assert build_corner_labels(value) == ["限定"]
    assert is_limited_dynamic(value)
