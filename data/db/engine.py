"""数据库引擎与 Session 工厂。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_ENGINE = None
_SESSION_FACTORY = None


def resolve_database_settings(config: dict) -> dict[str, Any]:
    """合并 database 配置与 supplementary 子项默认值。"""
    raw = config.get("database") if isinstance(config.get("database"), dict) else {}
    sup = raw.get("supplementary") if isinstance(raw.get("supplementary"), dict) else {}
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
    }


def is_database_enabled(config: dict) -> bool:
    settings = resolve_database_settings(config)
    return settings["enabled"] and bool(settings["url"])


def _resolve_sqlite_url(url: str, *, config_path: str | Path | None) -> str:
    if not url.startswith("sqlite:///"):
        return url
    # 已是绝对路径（sqlite:////C:/... 或 sqlite:////tmp/x.db）
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
    return _ENGINE


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
