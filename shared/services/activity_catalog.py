"""通过 DataMapper 读取 data_sources 中配置的 activity_table。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data import DataMapper

ACTIVITY_TABLE_SOURCE_ID = "activity_table"

# 与 test/test_activate.py 一致：SideStory + 故事集/主题曲插曲
_DEFAULT_EXTRA_TYPES = frozenset({"MINISTORY", "TYPE_MAINSS"})


@dataclass(frozen=True)
class ActivityRecord:
    name: str
    start_ts: int | None
    end_ts: int | None
    act_type: str = ""

    @property
    def label(self) -> str:
        if self.start_ts is None and self.end_ts is None:
            return self.name
        s = _format_ts(self.start_ts) if self.start_ts else "?"
        e = _format_ts(self.end_ts) if self.end_ts else "?"
        return f"{self.name}（{s} ~ {e}）"


def _format_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_activities_from_table(
    table: dict[str, Any],
    *,
    extra_types: frozenset[str] | None = None,
    exclude_recap_name: bool = True,
) -> list[ActivityRecord]:
    extra = extra_types if extra_types is not None else _DEFAULT_EXTRA_TYPES
    records: list[ActivityRecord] = []
    for info in (table.get("basicInfo") or {}).values():
        if not isinstance(info, dict):
            continue
        name = str(info.get("name") or "").strip()
        act_type = str(info.get("type") or "")
        if not name:
            continue
        if exclude_recap_name and "复刻" in name:
            continue
        if not (act_type.startswith("TYPE_ACT") or act_type in extra):
            continue
        start_ts = info.get("startTime")
        end_ts = info.get("endTime")
        records.append(
            ActivityRecord(
                name=name,
                start_ts=int(start_ts) if start_ts is not None else None,
                end_ts=int(end_ts) if end_ts is not None else None,
                act_type=act_type,
            )
        )
    records.sort(key=lambda r: (r.start_ts or 0), reverse=True)
    return records


def list_activities_from_mapper(mapper: DataMapper) -> list[ActivityRecord]:
    """从已初始化的 DataMapper 加载 activity_table 数据源。"""
    table = mapper.get_data(ACTIVITY_TABLE_SOURCE_ID)
    if not isinstance(table, dict):
        raise TypeError(
            f"数据源 {ACTIVITY_TABLE_SOURCE_ID!r} 应返回 dict，实际为 {type(table).__name__}"
        )
    return parse_activities_from_table(table)


def list_activities_from_data_source(
    config_path: str | Path,
    data_source_group: str,
) -> list[ActivityRecord]:
    """按 config 与数据源组构造 DataMapper 并加载活动列表。"""
    mapper = DataMapper.from_file(
        config_path,
        data_source_group=data_source_group,
        interactive=False,
    )
    return list_activities_from_mapper(mapper)


__all__ = [
    "ACTIVITY_TABLE_SOURCE_ID",
    "ActivityRecord",
    "list_activities_from_data_source",
    "list_activities_from_mapper",
    "parse_activities_from_table",
]
