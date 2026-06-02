"""活动表：数据源更新库，界面只读库。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data.db.activity_repo import ActivityRepository, _datetime_to_ts
from data.db.engine import reset_engine_cache
from data.db.models import Activity
from shared.services.activity_catalog import ActivityRecord


@pytest.fixture
def sqlite_config(tmp_path):
    db_file = tmp_path / "test.db"
    return {
        "database": {
            "enabled": True,
            "url": f"sqlite:///{db_file.as_posix()}",
            "activity": {"table": "activities", "sync_from_data_source": True},
        }
    }


def _rec(name: str, start: int, end: int) -> ActivityRecord:
    return ActivityRecord(
        name=name,
        start_ts=start,
        end_ts=end,
        act_type="TYPE_ACT9D0",
        activity_id="act_test",
    )


def test_list_for_ui_reads_database_only(sqlite_config):
    reset_engine_cache()
    repo = ActivityRepository(sqlite_config)
    repo.sync_from_data_source([_rec("A活动", 100, 200), _rec("B活动", 300, 400)])
    names = [r.name for r in repo.list_for_ui()]
    assert names == ["B活动", "A活动"]
    assert repo.list_for_ui()[0].start_ts == 300
    reset_engine_cache()


def test_sync_updates_times_from_data_source(sqlite_config):
    reset_engine_cache()
    repo = ActivityRepository(sqlite_config)
    repo.sync_from_data_source([_rec("X", 100, 200)])

    manual = datetime(2025, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    with repo._factory() as session:
        row = session.get(Activity, "X")
        row.start_time = manual
        session.commit()

    repo.sync_from_data_source([_rec("X", 1709784000, 1710964799)])
    row = repo.get_by_name("X")
    assert _datetime_to_ts(row.start_time) == 1709784000
    reset_engine_cache()
