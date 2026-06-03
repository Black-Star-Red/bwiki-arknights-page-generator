"""B 站 SideStory / 活动奖励干员获取途径。"""

import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "bilibili_service", _root / "shared/services/bilibili_service.py"
)
_bili = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _bili
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
    assert _obtain(side, _ACQ) == "【残阳】主题曲获取、主题曲获取"


def test_main_theme_reward_pool_obtain_path():
    assert (
        _obtain_pool("主题曲奖励干员", _ACQ_FULL, activity_name="相变临界")
        == "【相变临界】主题曲获取、主题曲获取"
    )


def test_should_use_main_theme_reward_with_gui_flag():
    should = _bili.should_use_main_theme_reward_obtain
    ctx = _BilibiliScanContext(
        gui_activity_name="相变临界",
        gui_activity_is_main_theme=True,
    )
    assert should("活动奖励干员", None, ctx)
    assert should("主题曲奖励干员", None, ctx)
    ctx2 = _BilibiliScanContext(gui_activity_name="泡影苍霆")
    assert not should("活动奖励干员", "SideStory「泡影苍霆」", ctx2)


def test_apply_gui_main_theme_converts_activity_obtain():
    apply = _bili.apply_gui_activity_obtain_path
    assert (
        apply(
            {"获取途径": "活动获取、【人们，我们】活动获取"},
            "相变临界",
            gui_activity_is_main_theme=True,
        )["获取途径"]
        == "【相变临界】主题曲获取、主题曲获取"
    )


def test_activity_reward_no_side_story():
    assert _obtain(None, _ACQ) == "活动获取"


def test_collab_activity_reward_obtain_path():
    side = "SideStory「泡影苍霆」"
    assert (
        _obtain(side, _ACQ, collab=True)
        == "【泡影苍霆】活动获取、活动获取、联动"
    )
    assert (
        _obtain(side, _ACQ, collab=True, activity_name="GUI活动")
        == "【GUI活动】活动获取、活动获取、联动"
    )
    assert _obtain(None, _ACQ, collab=True) == "活动获取、活动获取、联动"


_resolve_collab = _bili.resolve_collab_activity_name
_BilibiliScanContext = _bili.BilibiliScanContext


def test_apply_gui_activity_obtain_path_overrides_stale_obtain():
    apply = _bili.apply_gui_activity_obtain_path
    assert (
        apply({"获取途径": "活动获取、【人们，我们】活动获取"}, "相变临界")[
            "获取途径"
        ]
        == "活动获取、【相变临界】活动获取"
    )
    assert (
        apply({"获取途径": "【人们，我们】活动获取、活动获取、联动"}, "泡影苍霆")[
            "获取途径"
        ]
        == "【泡影苍霆】活动获取、活动获取、联动"
    )


def test_activity_reward_gui_overrides_cached_side_story():
    ctx = _BilibiliScanContext(
        gui_activity_name="相变临界",
        cached_side_story="SideStory「人们，我们」",
        cached_activity_name="人们，我们",
    )
    assert (
        _resolve_collab(side_story="SideStory「人们，我们」", scan_ctx=ctx)
        == "相变临界"
    )
    assert (
        _obtain("SideStory「人们，我们」", _ACQ, activity_name="相变临界")
        == "活动获取、【相变临界】活动获取"
    )


def test_resolve_collab_activity_name_priority():
    ctx = _BilibiliScanContext(gui_activity_name="泡影苍霆", cached_activity_name="缓存名")
    assert _resolve_collab(side_story=None, scan_ctx=ctx) == "泡影苍霆"
    ctx2 = _BilibiliScanContext(cached_activity_name="缓存名")
    assert _resolve_collab(side_story="SideStory「其他」", scan_ctx=ctx2) == "其他"
    assert _resolve_collab(side_story=None, scan_ctx=ctx2) == "缓存名"


def test_refresh_scan_cache_collab_title_without_side_story():
    refresh = _bili.refresh_scan_activity_cache
    ctx = _BilibiliScanContext()
    refresh(ctx, [{"orig_text": _COLLAB_ANNOUNCE_TEXT.split("\n")[0]}])
    assert ctx.cached_activity_name == "泡影苍霆"
    assert ctx.cached_side_story is None
    refresh(ctx, [{"orig_text": _COLLAB_ANNOUNCE_TEXT}])
    assert ctx.cached_side_story == "SideStory「泡影苍霆」"
    assert ctx.cached_activity_name == "泡影苍霆"
    assert "幽境狩人" in ctx.cached_collab_gacha_pools


def test_refresh_scan_cache_keeps_side_story_over_later_title():
    refresh = _bili.refresh_scan_activity_cache
    ctx = _BilibiliScanContext()
    refresh(ctx, [{"orig_text": _COLLAB_ANNOUNCE_TEXT}])
    refresh(ctx, [{"orig_text": "【其他】\n◆争锋频道：绿藤城篇章限时活动"}])
    assert ctx.cached_side_story == "SideStory「泡影苍霆」"
    assert ctx.cached_activity_name == "泡影苍霆"


def test_resolve_fetch_target_by_discovered_dynamic_id():
    from shared.services.bilibili_supplementary_fetch import (
        _AnnounceHit,
        _resolve_fetch_target_key_for_hit,
    )

    item = {"id_str": "1206954531858939921"}
    hit = _AnnounceHit(
        name="B站预告名与库不一致",
        text="",
        item=item,
        photo_url="http://x",
        gacha_pool="活动奖励干员",
        is_collab=True,
        side_story=None,
    )
    ctx = _BilibiliScanContext(
        discovered_dynamic_ids={"罗德岛隐秘队": "1206954531858939921"},
    )
    key = _resolve_fetch_target_key_for_hit(hit, {"罗德岛隐秘队"}, ctx)
    assert key == "罗德岛隐秘队"


def test_refresh_scan_cache_theme_does_not_overwrite_side_story():
    refresh = _bili.refresh_scan_activity_cache
    ctx = _BilibiliScanContext()
    refresh(ctx, [{"orig_text": _COLLAB_ANNOUNCE_TEXT}])
    refresh(ctx, [{"orig_text": "主题曲「相变临界」篇章限时活动即将开启"}])
    assert ctx.cached_side_story == "SideStory「泡影苍霆」"
    assert ctx.cached_activity_name == "泡影苍霆"
    assert ctx.cached_main_theme_activity_name == "相变临界"


def test_extract_collab_event_title_from_announce_header():
    title = _bili._extract_collab_event_title_from_text(
        "【明日方舟 × 怪物猎人】「泡影苍霆」限时活动即将开启"
    )
    assert title == "泡影苍霆"


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


def test_named_pool_without_article_scan_defaults_to_standard():
    assert _obtain_pool("承诺", _ACQ_FULL) == "标准寻访"
    assert _obtain_pool("辟路之人", _ACQ_FULL) == "标准寻访"
    assert _obtain_pool("新增干员", _ACQ_FULL) == "标准寻访"
    assert (
        _obtain_pool("新增干员", _ACQ_FULL, collab=True, collab_pool="幽境狩人")
        == "联动、联动寻访、【幽境狩人】寻访"
    )


def test_named_pool_not_collab_without_dynamic_header():
    """未匹配专栏 [限定] 时，命名池不臆断为限定寻访。"""
    _obtain_pool = _bili._obtain_path_for_gacha_pool
    assert _obtain_pool("定向甄选", _ACQ_FULL, collab=False) == "标准寻访"
    assert (
        _obtain_pool("定向甄选", _ACQ_FULL, collab=True)
        == "联动、联动寻访、【定向甄选】寻访"
    )


def test_collab_pool_from_overview_and_obtain_path():
    nodes = [{"orig_text": _COLLAB_ANNOUNCE_TEXT}]
    assert _extract_collab_pools(nodes) == {"幽境狩人"}
    assert _obtain_pool("幽境狩人", _ACQ_FULL, collab=True) == "联动、联动寻访、【幽境狩人】寻访"


def test_collab_activity_reward_via_obtain_pool():
    side = "SideStory「泡影苍霆」"
    assert (
        _obtain_pool("活动奖励干员", _ACQ_FULL, collab=True, side_story=side)
        == "【泡影苍霆】活动获取、活动获取、联动"
    )


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


def test_extract_article_pool_keys_from_summary():
    extract = _bili.extract_article_pool_keys
    title = "【限定寻访·庆典】「辟路之人」限时寻访活动即将开启"
    summary = (
        "[图片] 活动时间：05月01日 12:00 - 05月15日 03:59 "
        "活动说明：活动期间【限定寻访·庆典】-【辟路之人】寻访开启"
    )
    pool, banner = extract(title, summary)
    assert pool == "辟路之人"
    assert banner == "限定寻访·庆典"


def test_limited_name_substring_does_not_match_longer_operator():
    limited = {"凛冬"}
    assert not _is_limited("怒潮凛冬", limited)


def test_pool_obtain_requires_limited_tag_not_empty_pool_fallback():
    """专栏已解析出 [限定] 名单时：仅名单内为限定，其余（如怒潮凛冬式 UP）为标准。"""
    limited = _extract_limited(_CHENGNUO_ARTICLE_SUMMARY)
    assert limited
    assert not (
        limited and _is_limited("可露希尔", limited)
    )
    assert not (
        limited and _is_limited("怒潮凛冬", limited)
    )
