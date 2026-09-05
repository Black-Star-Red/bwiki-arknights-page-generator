"""数据库引擎与 Session 工厂。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_ENGINE = None
_SESSION_FACTORY = None


def _dedupe_field_list(fields) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in fields or []:
        key = str(raw).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out

"""
合并 database 配置与 supplementary 子项默认值。
@param config: 配置
@return: 数据库设置
"""
def resolve_database_settings(config: dict) -> dict[str, Any]:
    """合并 database 配置与 supplementary 子项默认值。"""
    raw = config.get("database") if isinstance(config.get("database"), dict) else {}
    sup = raw.get("supplementary") if isinstance(raw.get("supplementary"), dict) else {}
    act = raw.get("activity") if isinstance(raw.get("activity"), dict) else {}
    return {
        "enabled": bool(raw.get("enabled", False)),
        "url": (raw.get("url") or "").strip(),
        "write_after_fallback": bool(raw.get("write_after_fallback", True)),
        "prefer_db": bool(sup.get("prefer_db", True)),
        "fallback_bilibili": bool(sup.get("fallback_bilibili", True)),
        # 库内完整记录已够 N 人时，批量模式不再先请求 B 站拿名单（避免重复 OCR）
        "skip_bilibili_discover_if_db_complete": bool(
            sup.get("skip_bilibili_discover_if_db_complete", True)
        ),
        "required_fields": list(sup.get("required_fields") or ["获取途径", "实装日期"]),
        "fill_fields": _dedupe_field_list(
            sup.get("fill_fields")
            or list(sup.get("required_fields") or ["获取途径", "实装日期"])
            + ["专精", "画师"]
        ),
        "activity_table": (act.get("table") or "activities").strip() or "activities",
        "activity_sync_from_data_source": bool(act.get("sync_from_data_source", True)),
    }


def is_database_enabled(config: dict) -> bool:
    settings = resolve_database_settings(config)
    return settings["enabled"] and bool(settings["url"])


def _resolve_sqlite_url(url: str, *, config_path: str | Path | None) -> str:
    if not url.startswith("sqlite:///"):
        return url
    if url.startswith("sqlite:////"):
        return url
    rel = url[len("sqlite:///") :]
    if Path(rel).is_absolute():
        return url
    if config_path:
        base = Path(config_path).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2] / "config"
    abs_path = (base / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{abs_path.as_posix()}"

"""
获取数据库引擎
@param config: 配置
@param config_path: 配置路径
@return: 数据库引擎
"""
def get_engine(config: dict, *, config_path: str | Path | None = None):
    global _ENGINE
    settings = resolve_database_settings(config)
    if not settings["enabled"] or not settings["url"]:
        return None
    if _ENGINE is not None:
        return _ENGINE
    url = _resolve_sqlite_url(settings["url"], config_path=config_path)
    _ENGINE = create_engine(url, future=True)
    Base.metadata.create_all(_ENGINE)
    _ensure_operator_supplementary_columns(_ENGINE)
    return _ENGINE


def _ensure_operator_supplementary_columns(engine) -> None:
    """已有表时补列（create_all 不会 ALTER）。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
        if "operator_supplementary" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("operator_supplementary")}
    except Exception:
        return
    if "drawer" in cols:
        return
    dialect = engine.dialect.name
    if dialect == "mysql":
        ddl = "ALTER TABLE operator_supplementary ADD COLUMN drawer TEXT"
    elif dialect == "sqlite":
        ddl = "ALTER TABLE operator_supplementary ADD COLUMN drawer TEXT DEFAULT ''"
    else:
        ddl = "ALTER TABLE operator_supplementary ADD COLUMN drawer TEXT DEFAULT ''"
    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
        from core.script_logging import log_info

        log_info("operator_supplementary 已补列 drawer")
    except Exception as exc:
        from core.script_logging import log_warning

        log_warning("operator_supplementary 补列 drawer 失败: %s", exc)


def get_session_factory(config: dict, *, config_path: str | Path | None = None):
    global _SESSION_FACTORY
    engine = get_engine(config, config_path=config_path)
    if engine is None:
        return None
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(bind=engine, expire_on_commit=False)
    return _SESSION_FACTORY


def reset_engine_cache() -> None:
    """测试用：重置单例。"""
    global _ENGINE, _SESSION_FACTORY
    _ENGINE = None
    _SESSION_FACTORY = None
