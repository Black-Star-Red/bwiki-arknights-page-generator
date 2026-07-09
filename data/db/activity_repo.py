"""活动表：界面只读库；数据源负责写入/更新库。"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING

from sqlalchemy import select

from core.script_logging import log_info, log_warning

from .engine import get_engine, get_session_factory, resolve_database_settings
from .models import Activity

if TYPE_CHECKING:
    from shared.services.activity_catalog import ActivityRecord


def _ts_to_datetime(ts: int | None) -> datetime | None:
    """存库用 naive UTC 时刻（与游戏 startTime Unix 秒一致）。"""
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=ZoneInfo("UTC")).replace(tzinfo=None)


def _datetime_to_ts(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _row_to_record(row: Activity) -> ActivityRecord:
    from shared.services.activity_catalog import ActivityRecord

    return ActivityRecord(
        name=row.name,
        start_ts=_datetime_to_ts(row.start_time),
        end_ts=_datetime_to_ts(row.end_time),
    )


class ActivityRepository:
    def __init__(self, config: dict, *, config_path: str | None = None):
        self._config = config
        self._config_path = config_path
        self._settings = resolve_database_settings(config)
        self._factory = get_session_factory(config, config_path=config_path)

    @property
    def available(self) -> bool:
        return self._factory is not None and self._settings["enabled"]

    def _table_ok(self) -> bool:
        from sqlalchemy import inspect

        engine = get_engine(self._config, config_path=self._config_path)
        if engine is None:
            return False
        try:
            return self._settings["activity_table"] in inspect(engine).get_table_names()
        except Exception:
            return False

    def get_by_name(self, name: str) -> Activity | None:
        if not self._factory or not name:
            return None
        with self._factory() as session:
            return session.get(Activity, name)

    def sync_from_data_source(self, records: list[ActivityRecord]) -> int:
        """用数据源 activity_table 写入/更新库（以游戏表为准刷新时间）。"""
        if not self.available or not records:
            return 0
        if not self._settings.get("activity_sync_from_data_source", True):
            return 0
        if not self._table_ok():
            log_warning(
                "活动表 %s 不存在，跳过同步",
                self._settings["activity_table"],
            )
            return 0

        touched = 0
        with self._factory() as session:
            for rec in records:
                row = session.get(Activity, rec.name)
                if row is None:
                    row = Activity(name=rec.name)
                    session.add(row)
                    touched += 1
                row.start_time = _ts_to_datetime(rec.start_ts)
                row.end_time = _ts_to_datetime(rec.end_ts)
            session.commit()
        if touched:
            log_info("活动表同步（数据源→库）新增 %s 条", touched)
        elif records:
            log_info("活动表同步（数据源→库）已更新 %s 条", len(records))
        return len(records)

    def list_for_ui(self) -> list[ActivityRecord]:
        """下拉框：只读数据库，按开始时间倒序。"""
        if not self._factory:
            return []
        with self._factory() as session:
            rows = session.scalars(select(Activity)).all()
        records = [_row_to_record(r) for r in rows]
        records.sort(key=lambda r: (r.start_ts or 0), reverse=True)
        return records


__all__ = [
    "ActivityRepository",
    "_datetime_to_ts",
    "_ts_to_datetime",
]
