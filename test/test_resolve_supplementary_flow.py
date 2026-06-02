"""补充数据：按人补缺判定。"""

from core.character_script.resolve_supplementary import _has_activity_time_filter
from data.db.supplementary_repo import (
    missing_supplementary_fields,
    needs_supplementary_fetch,
)


def test_activity_filter_and_character_num_exclusive():
    assert _has_activity_time_filter(100, 200)
    assert not _has_activity_time_filter(None, None)


def test_needs_fetch_when_missing_specialization():
    db = {
        "获取途径": "标准寻访",
        "实装日期": "x",
        "专精": "",
        "画师": "A",
    }
    fill = ["获取途径", "实装日期", "专精", "画师"]
    assert needs_supplementary_fetch(db, fill)
    assert "专精" in missing_supplementary_fields(db, fill)


def test_no_fetch_when_fill_complete():
    db = {
        "获取途径": "标准寻访",
        "实装日期": "x",
        "专精": "a、b",
        "画师": "X",
    }
    fill = ["获取途径", "实装日期", "专精", "画师"]
    assert not needs_supplementary_fetch(db, fill)
