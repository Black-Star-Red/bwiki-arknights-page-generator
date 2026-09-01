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

apply_collab_period = _collab_shared.apply_collab_period_supplementary_meta
build_corner_labels = _labels.build_corner_labels
enrich_collab_meta = _collab_shared.enrich_collab_meta
is_collaboration = _labels.is_collaboration
is_collab_period_activity_reward_context = (
    _collab_shared.is_collab_period_activity_reward_context
)
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


def test_apply_collab_period_fixes_wrong_cached_pool_in_obtain():
    ctx = _bili.BilibiliScanContext(
        gui_activity_name="泡影苍霆",
        cached_collab_gacha_pools={"幽境狩人"},
    )
    out = apply_collab_period(
        {
            "联动": True,
            "联动卡池": "定向甄选",
            "获取途径": "联动、联动寻访、【定向甄选】寻访",
        },
        ctx,
    )
    assert out["联动卡池"] == "幽境狩人"
    assert out["获取途径"] == "联动、联动寻访、【幽境狩人】寻访"


def test_apply_collab_period_marks_activity_reward_with_gui_name():
    ctx = _bili.BilibiliScanContext(
        gui_activity_name="泡影苍霆",
        cached_collab_gacha_pools={"幽境狩人"},
    )
    out = apply_collab_period(
        {"获取途径": "活动获取、【泡影苍霆】活动获取"},
        ctx,
    )
    assert out["联动"] is True
    assert out["获取途径"] == "活动获取、【泡影苍霆】活动获取"
    assert build_corner_labels(out) == ["联", "活"]


def test_collab_period_activity_reward_without_gui_when_feed_has_collab_pools():
    """按数量批量、未选手动活动时，feed 已缓存联动池 → 活动奖励判联。"""
    ctx = _bili.BilibiliScanContext(
        cached_activity_name="月行水上",
        cached_side_story="SideStory「月行水上」",
        cached_collab_gacha_pools={"石白深蓝之夜"},
    )
    assert is_collab_period_activity_reward_context(
        ctx,
        gui_activity="",
        pools_at_or_before={"石白深蓝之夜"},
    )
    out = apply_collab_period(
        {"获取途径": "活动获取、【月行水上】活动获取"},
        ctx,
    )
    assert out["联动"] is True
    assert build_corner_labels(out) == ["联", "活"]


def test_collab_period_activity_reward_without_gui_requires_collab_signal():
    ctx = _bili.BilibiliScanContext(cached_activity_name="普通SideStory")
    assert not is_collab_period_activity_reward_context(
        ctx,
        gui_activity="",
        pools_at_or_before=set(),
    )


def test_apply_collab_period_meta_for_db_standard_gacha():
    ctx = _bili.BilibiliScanContext(
        gui_activity_name="泡影苍霆",
        cached_collab_gacha_pools={"幽境狩人"},
    )
    out = apply_collab_period(
        {"获取途径": "标准寻访", "实装日期": "x"},
        ctx,
    )
    assert out["联动"] is True
    assert out["联动卡池"] == "幽境狩人"
    assert build_corner_labels(out, alter_operator="char_278_orchid") == [
        "联",
        "异",
    ]


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


def test_wiki_obtain_path_collab_activity_reward():
    wiki = _labels.wiki_obtain_path
    value = {
        "联动": True,
        "联动卡池": "幽境狩人",
        "获取途径": "活动获取、【泡影苍霆】活动获取",
    }
    assert wiki(value) == "【泡影苍霆】活动获取、活动获取、联动"
    assert _labels.collab_obtain_path(value) == "【泡影苍霆】活动获取、活动获取、联动"


def test_wiki_obtain_path_collab_activity_reward_yuexingshuishang():
    wiki = _labels.wiki_obtain_path
    value = {
        "联动": True,
        "获取途径": "活动获取、【月行水上】活动获取",
    }
    assert wiki(value) == "【月行水上】活动获取、活动获取、联动"


def test_wiki_obtain_path_normalizes_legacy_collab_gacha():
    wiki = _labels.wiki_obtain_path
    value = {
        "联动": True,
        "获取途径": "联动寻访、【幽境狩人】寻访",
    }
    assert wiki(value) == "联动、联动寻访、【幽境狩人】寻访"


def test_wiki_obtain_path_uses_collab_pool_for_standard_gacha():
    wiki = _labels.wiki_obtain_path
    value = {
        "联动": True,
        "联动卡池": "幽境狩人",
        "获取途径": "标准寻访",
    }
    assert wiki(value) == "联动、联动寻访、【幽境狩人】寻访"


def test_build_corner_labels_limited():
    value = {"动态id": "123", "获取途径": "限定寻访、【春节】限定寻访"}
    assert build_corner_labels(value) == ["限定"]
    assert is_limited_dynamic(value)
