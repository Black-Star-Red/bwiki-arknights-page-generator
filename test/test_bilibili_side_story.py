"""B 站 SideStory / 活动奖励干员获取途径。"""

import importlib.util
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "bilibili_service", _root / "shared/services/bilibili_service.py"
)
_bili = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bili)

_extract_text = _bili._extract_side_story_from_text
_extract_nodes = _bili._extract_side_story_from_nodes
_obtain = _bili._activity_reward_obtain_path
_collab = _bili._dynamic_is_collaboration
_COLLAB_RE = __import__("re").compile(r"^【明日方舟\s*[×xX][^】]+】")
_ACQ = {"活动奖励干员": "活动获取、【"}

# 来自 polymer_data_page0.json 的真实公告节选
_COLLAB_ANNOUNCE_TEXT = (
    "【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启\n\n"
    "一、【明日方舟 × 怪物猎人】，SideStory「泡影苍霆」活动关卡开启\n"
    "二、【幽境狩人】限时寻访开启\n"
)

_MAINTENANCE_SNIPPET = (
    "【其他】\n"
    "◆修复主题曲「二次呼吸」关卡【3-2】中部分地块显示异常的问题\n"
)


def test_extract_side_story_inline():
    assert _extract_text("SideStory「泡影苍霆」限时活动") == "SideStory「泡影苍霆」"
    assert _extract_text(_COLLAB_ANNOUNCE_TEXT) == "SideStory「泡影苍霆」"
    assert _extract_text("主题曲「残阳」篇章限时活动") == "主题曲「残阳」"
    assert _extract_text(_MAINTENANCE_SNIPPET) is None
    assert _extract_text("普通活动文案") is None


def test_collab_announce_side_story_via_nodes():
    nodes = [{"orig_text": _COLLAB_ANNOUNCE_TEXT}]
    assert _extract_nodes(nodes) == "SideStory「泡影苍霆」"


def test_collab_detection_multiline():
    item = {"modules": [{"module_desc": {"rich_text_nodes": [{"orig_text": _COLLAB_ANNOUNCE_TEXT}]}}]}
    assert _collab(item, _COLLAB_RE)


def test_activity_reward_not_main_theme():
    side = "SideStory「泡影苍霆」"
    assert _obtain(side, _ACQ) == "活动获取、【泡影苍霆】活动获取"
    assert "主题曲获得" not in _obtain(side, _ACQ)


def test_activity_reward_main_theme():
    side = "主题曲「残阳」"
    assert _obtain(side, _ACQ) == "主题曲获得 / "


def test_activity_reward_no_side_story():
    assert _obtain(None, _ACQ) == "活动获取"


_obtain_pool = _bili._obtain_path_for_gacha_pool
_extract_collab_pools = _bili._extract_collab_gacha_pools_from_nodes
_collect_nodes = _bili._collect_rich_text_nodes
_collect_with_src = _bili._collect_rich_text_nodes_with_source
_ANNOUNCE_RE = __import__("re").compile(
    r"^\s*(?:互动抽奖\s*)?【([^】]+)】\n//([^\n]+)\n(?:\u201c|\")(.*?)(?:\u201d|\")"
)
_ACQ_FULL = {
    "活动奖励干员": "活动获取、【",
    "新增干员": "标准寻访",
    "采购凭证区-新增干员": "采购凭证区",
}


def test_named_pool_defaults_to_limited_not_standard():
    assert _obtain_pool("承诺", _ACQ_FULL) == "限定寻访、【承诺】限定寻访"
    assert _obtain_pool("新增干员", _ACQ_FULL) == "标准寻访"


def test_collab_pool_from_overview_and_obtain_path():
    nodes = [{"orig_text": _COLLAB_ANNOUNCE_TEXT}]
    assert _extract_collab_pools(nodes) == {"幽境狩人"}
    assert _obtain_pool("幽境狩人", _ACQ_FULL, collab=True) == "联动、联动寻访、【幽境狩人】寻访"


def test_forwarded_dynamic_collects_operator_announce():
    item = {
        "modules": [
            {
                "module_dynamic": {
                    "dyn_forward": {
                        "item": {
                            "modules": [
                                {
                                    "module_desc": {
                                        "rich_text_nodes": [
                                            {
                                                "orig_text": (
                                                    " 【承诺】\n//凯尔希·思衡托\n"
                                                    "“博士......？”\n"
                                                )
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        ]
    }
    texts = [n["orig_text"] for n in _collect_nodes(item)]
    assert any("//凯尔希·思衡托" in t for t in texts)


def test_lottery_repost_does_not_match_embedded_announce():
    """抽奖公示转发：顶层「恭喜…中奖」不匹配；内嵌【承诺】//凯尔希 不当作新干员。"""
    item = {
        "modules": [
            {
                "module_desc": {
                    "rich_text_nodes": [
                        {
                            "orig_text": (
                                "恭喜@海绵宝宝星熊儿@花仙白百何等10位同学中奖，"
                                "已私信通知，详情请点击抽奖查看。"
                            )
                        }
                    ]
                }
            },
            {
                "module_dynamic": {
                    "dyn_forward": {
                        "item": {
                            "modules": [
                                {
                                    "module_desc": {
                                        "rich_text_nodes": [
                                            {
                                                "orig_text": (
                                                    " 【承诺】\n//凯尔希·思衡托\n"
                                                    "“博士......？”\n"
                                                )
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            },
        ]
    }
    hits = [
        _ANNOUNCE_RE.match(n["orig_text"])
        for n, fwd in _collect_with_src(item)
        if not fwd and _ANNOUNCE_RE.match(n["orig_text"])
    ]
    assert hits == []


def test_top_level_announce_still_matches():
    text = " 【承诺】\n//凯尔希·思衡托\n“博士......？”\n"
    assert _ANNOUNCE_RE.match(text)


_extract_limited = _bili._extract_limited_operators_from_article_summary
_is_limited = _bili._is_limited_operator_in_pool

_CHENGNUO_ARTICLE_SUMMARY = (
    "[图片] 活动时间：05月01日 12:00 - 05月15日 03:59 活动说明：活动期间【限定寻访·庆典】"
    "-【承诺】寻访开启，该寻访中以下干员出现率上升 "
    "★★★★★★：凯尔希·思衡托 [限定] \\ 可露希尔（占6★出率的70%） "
    "★★★★★★：新约能天使 [限定] \\ 荒芜拉普兰德 [限定] \\ 维什戴尔 [限定] "
    "（在6★剩余出率【30%】中以5倍权值出率提升）"
)


def test_limited_operators_parsed_from_article_summary():
    limited = _extract_limited(_CHENGNUO_ARTICLE_SUMMARY)
    assert "凯尔希·思衡托" in limited
    assert "新约能天使" in limited
    assert "可露希尔" not in limited


def test_pool_up_without_limited_tag_is_not_limited():
    limited = _extract_limited(_CHENGNUO_ARTICLE_SUMMARY)
    assert _is_limited("凯尔希·思衡托", limited)
    assert not _is_limited("可露希尔", limited)
