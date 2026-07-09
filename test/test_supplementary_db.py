"""干员补充数据 DB 合并逻辑单元测试。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from data.db.engine import reset_engine_cache
from data.db.supplementary_repo import (
    OperatorSupplementaryRepository,
    apply_bili_ocr_over_empty,
    apply_db_with_bili_meta,
    lookup_supplementary_in_batch,
    merge_supplementary,
    merge_supplementary_bilibili_first,
    is_supplementary_complete,
    empty_supplementary_dict,
    resolve_supplementary_batch_key,
)
@pytest.fixture
def sqlite_config(tmp_path):
    db_file = tmp_path / "test.db"
    return {
        "database": {
            "enabled": True,
            "url": f"sqlite:///{db_file.as_posix()}",
            "write_after_fallback": True,
            "supplementary": {
                "prefer_db": True,
                "fallback_bilibili": True,
                "required_fields": ["获取途径", "实装日期"],
            },
        }
    }


def test_merge_db_over_bili():
    db = {
        "获取途径": "活动获取",
        "实装日期": "",
        "动态id": "",
        "专精": "",
        "画师": "",
        "宣传介绍": "",
    }
    bili = {
        "获取途径": "标准寻访",
        "实装日期": "2026-01-01",
        "动态id": "1",
        "专精": "",
        "画师": "",
        "宣传介绍": "",
    }
    merged = merge_supplementary(db, bili)
    assert merged["获取途径"] == "活动获取"
    assert merged["实装日期"] == "2026-01-01"
    assert merged["动态id"] == "1"


def test_upsert_drawer_persists(sqlite_config):
    reset_engine_cache()
    repo = OperatorSupplementaryRepository(sqlite_config)
    sup = {
        "获取途径": "标准寻访",
        "实装日期": "x",
        "动态id": "",
        "专精": "材料A",
        "画师": "Studio Montagne、Skade（原案）",
        "宣传介绍": "",
    }
    repo.upsert("画师测试", sup, source="bilibili")
    loaded = repo.get_by_name("画师测试")
    assert loaded is not None
    assert loaded["画师"] == sup["画师"]
    assert loaded["专精"] == "材料A"
    reset_engine_cache()


def test_bili_batch_name_alias_lookup():
    batch = {"焰狐龙梓兰": {"画师": "OCR画师", "获取途径": "标准寻访"}}
    key, part = lookup_supplementary_in_batch(batch, "焰狐龙·梓兰")
    assert key == "焰狐龙梓兰"
    assert part["画师"] == "OCR画师"
    assert resolve_supplementary_batch_key("凯尔希·思衡托", {"凯尔希思衡托"}) == "凯尔希思衡托"


def test_apply_bili_ocr_over_empty_keeps_db():
    db = merge_supplementary(
        {"获取途径": "活动", "实装日期": "1", "专精": "旧", "画师": ""},
        None,
    )
    bili = {"专精": "", "画师": "新画师"}
    out = apply_bili_ocr_over_empty(db, bili)
    assert out["专精"] == "旧"
    assert out["画师"] == "新画师"


def test_upsert_and_read(sqlite_config):
    reset_engine_cache()
    repo = OperatorSupplementaryRepository(sqlite_config)
    assert repo.available
    sup = {
        "获取途径": "SideStory「测试」】活动获取",
        "实装日期": "https://example.com",
        "动态id": "999",
        "专精": "专精材料A",
        "宣传介绍": "宣传",
    }
    repo.upsert("测试干员", sup, char_id="char_test_1", source="bilibili")
    loaded = repo.get_by_name("测试干员")
    assert loaded is not None
    assert loaded["获取途径"] == sup["获取途径"]
    assert loaded["动态id"] == "999"
    assert is_supplementary_complete(loaded, ["获取途径", "实装日期"])
    names = repo.list_complete_names(5, ["获取途径", "实装日期"])
    assert "测试干员" in names
    reset_engine_cache()


def test_empty_merge():
    assert merge_supplementary(None, None) == empty_supplementary_dict()


def test_apply_db_with_bili_meta():
    db = {"获取途径": "活动获取", "实装日期": "2020-01-01"}
    bili = {"联动": True, "联动卡池": "砺火成锋", "获取途径": "联动寻访、【砺火成锋】寻访"}
    out = apply_db_with_bili_meta(db, bili)
    assert out["获取途径"] == "活动获取"
    assert out["联动"] is True
    assert out["联动卡池"] == "砺火成锋"


def test_merge_prefers_bili_when_db_is_standard_gacha():
    db = {"获取途径": "标准寻访", "实装日期": "2020-01-01", "动态id": "", "专精": "", "宣传介绍": ""}
    bili = {
        "获取途径": "限定寻访、【承诺】限定寻访",
        "实装日期": "2026-01-01",
        "动态id": "1",
        "专精": "",
        "宣传介绍": "",
    }
    merged = merge_supplementary(db, bili)
    assert merged["获取途径"] == "限定寻访、【承诺】限定寻访"
    assert merged["实装日期"] == "2026-01-01"


def test_merge_bilibili_first_over_stale_db():
    db = {
        "获取途径": "联动寻访、【幽境狩人】寻访",
        "实装日期": "2020-01-01",
        "动态id": "old",
        "专精": "旧专精",
        "宣传介绍": "旧介绍",
    }
    bili = {
        "获取途径": "联动、联动寻访、【幽境狩人】寻访",
        "实装日期": "2026-06-01",
        "动态id": "new",
        "专精": "新专精",
        "宣传介绍": "新介绍",
        "联动": True,
        "联动卡池": "幽境狩人",
    }
    merged = merge_supplementary_bilibili_first(db, bili)
    assert merged["获取途径"] == bili["获取途径"]
    assert merged["实装日期"] == "2026-06-01"
    assert merged["动态id"] == "new"
    assert merged["专精"] == "新专精"
    assert merged["联动"] is True


def test_apply_db_infers_collab_from_obtain_when_no_bili():
    db = {
        "获取途径": "联动、联动寻访、【幽境狩人】寻访",
        "实装日期": "2026-06-01",
    }
    out = apply_db_with_bili_meta(db, None)
    assert out["联动"] is True
    assert out["联动卡池"] == "幽境狩人"


def test_supplementary_for_upsert_matches_wiki_obtain(sqlite_config):
    from data.db.supplementary_repo import supplementary_for_upsert

    activity = supplementary_for_upsert(
        {
            "获取途径": "活动获取、【泡影苍霆】活动获取",
            "联动": True,
            "联动卡池": "幽境狩人",
        }
    )
    assert activity["获取途径"] == "活动获取、【泡影苍霆】活动获取"
    gacha = supplementary_for_upsert(
        {
            "获取途径": "标准寻访",
            "联动": True,
            "联动卡池": "幽境狩人",
            "实装日期": "",
            "动态id": "",
            "专精": "",
            "宣传介绍": "",
        }
    )
    assert gacha["获取途径"] == "联动、联动寻访、【幽境狩人】寻访"


def test_apply_db_overrides_stale_standard_from_bili():
    db = {"获取途径": "标准寻访", "实装日期": "2020-01-01"}
    bili = {"获取途径": "限定寻访、【承诺】限定寻访", "联动": True, "联动卡池": "幽境狩人"}
    out = apply_db_with_bili_meta(db, bili)
    assert out["获取途径"] == "限定寻访、【承诺】限定寻访"
    assert out["联动"] is True
