"""干员补充数据读写。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.script_logging import log_info, log_warning

from shared.collab_supplementary import enrich_collab_meta

from .engine import get_session_factory, resolve_database_settings
from .models import OperatorSupplementary

# 与 generate_template / bilibili_service 使用的键一致
SUPPLEMENTARY_KEYS = ("获取途径", "实装日期", "动态id", "专精", "画师", "宣传介绍")

# 仅内存传递、不入库的补充元数据（merge 时从 B 站侧保留）
SUPPLEMENTARY_META_KEYS = ("联动", "联动卡池")

_KEY_TO_COLUMN = {
    "获取途径": "acquisition_path",
    "实装日期": "release_date",
    "动态id": "dynamic_id",
    "专精": "specialization",
    "画师": "drawer",
    "宣传介绍": "promo_intro",
}

_COLUMN_TO_KEY = {v: k for k, v in _KEY_TO_COLUMN.items()}

_NAME_STRIP_RE = re.compile(r"[\s·・•．.\-]")
_OCR_FILL_KEYS = ("专精", "画师")


def normalize_supplementary_name_key(name: str) -> str:
    return _NAME_STRIP_RE.sub("", (name or "").strip())


def resolve_supplementary_batch_key(name: str, keys: set[str] | list[str]) -> str | None:
    """将 mapper/库内名对齐到 B 站 batch 或 fetch targets 中的键。"""
    if not name:
        return None
    key_set = set(keys)
    if name in key_set:
        return name
    nk = normalize_supplementary_name_key(name)
    if not nk:
        return None
    by_norm: dict[str, str] = {}
    for k in key_set:
        kn = normalize_supplementary_name_key(k)
        if kn and kn not in by_norm:
            by_norm[kn] = k
    if nk in by_norm:
        return by_norm[nk]
    best: str | None = None
    best_len = -1
    for k in key_set:
        kn = normalize_supplementary_name_key(k)
        if not kn:
            continue
        if kn in nk or nk in kn:
            span = min(len(kn), len(nk))
            if span > best_len:
                best_len = span
                best = k
    return best


def lookup_supplementary_in_batch(
    batch: dict[str, dict[str, Any]],
    name: str,
) -> tuple[str | None, dict[str, Any]]:
    if not batch or not name:
        return None, {}
    key = resolve_supplementary_batch_key(name, batch.keys())
    if key is None:
        return None, {}
    return key, batch[key]


def apply_bili_ocr_over_empty(
    merged: dict[str, Any],
    bili_part: dict[str, Any] | None,
) -> dict[str, Any]:
    """DB 优先合并后，仍用 B 站 OCR 填补空的专精/画师。"""
    out = dict(merged)
    for key in _OCR_FILL_KEYS:
        bv = str((bili_part or {}).get(key) or "").strip()
        if bv and not str(out.get(key) or "").strip():
            out[key] = bv
    return out


def supplementary_for_upsert(sup: dict[str, Any]) -> dict[str, str]:
    """仅保留可入库的补充字段（中文键）。"""
    return {k: str(sup.get(k) or "").strip() for k in SUPPLEMENTARY_KEYS}


def _is_generic_acquire_path(path: str) -> bool:
    p = (path or "").strip()
    return not p or p == "标准寻访"


def empty_supplementary_dict() -> dict[str, str]:
    return {k: "" for k in SUPPLEMENTARY_KEYS}


def row_to_dict(row: OperatorSupplementary | None) -> dict[str, str]:
    if row is None:
        return empty_supplementary_dict()
    return {
        "获取途径": row.acquisition_path or "",
        "实装日期": row.release_date or "",
        "动态id": row.dynamic_id or "",
        "专精": row.specialization or "",
        "画师": getattr(row, "drawer", None) or "",
        "宣传介绍": row.promo_intro or "",
    }


def merge_supplementary(
    db_part: dict[str, Any] | None,
    bili_part: dict[str, Any] | None,
) -> dict[str, Any]:
    """DB 优先；B 站仅填补空位。联动等元数据从 B 站侧保留。"""
    out: dict[str, Any] = empty_supplementary_dict()
    for key in SUPPLEMENTARY_KEYS:
        dv = (db_part or {}).get(key) or ""
        bv = (bili_part or {}).get(key) or ""
        if key == "获取途径" and _is_generic_acquire_path(str(dv)) and str(bv).strip():
            out[key] = str(bv)
        else:
            out[key] = dv if str(dv).strip() else str(bv or "")
    if bili_part:
        if bili_part.get("联动") is True:
            out["联动"] = True
        pool = (bili_part.get("联动卡池") or "").strip()
        if pool:
            out["联动卡池"] = pool
    return out


def merge_supplementary_bilibili_first(
    db_part: dict[str, Any] | None,
    bili_part: dict[str, Any] | None,
) -> dict[str, Any]:
    """B 站优先；DB 仅填补 B 站空位。联动等元数据从 B 站侧保留。"""
    out: dict[str, Any] = empty_supplementary_dict()
    for key in SUPPLEMENTARY_KEYS:
        bv = (bili_part or {}).get(key) or ""
        dv = (db_part or {}).get(key) or ""
        out[key] = bv if str(bv).strip() else str(dv or "")
    if bili_part:
        if bili_part.get("联动") is True:
            out["联动"] = True
        pool = (bili_part.get("联动卡池") or "").strip()
        if pool:
            out["联动卡池"] = pool
    return enrich_collab_meta(out)


def apply_db_with_bili_meta(
    db_part: dict[str, Any],
    bili_part: dict[str, Any] | None,
) -> dict[str, Any]:
    """库内完整记录为主，保留 B 站侧的联动等元数据。"""
    out = dict(db_part)
    if not bili_part:
        return enrich_collab_meta(out)
    bili_obtain = (bili_part.get("获取途径") or "").strip()
    db_obtain = (out.get("获取途径") or "").strip()
    if bili_obtain and _is_generic_acquire_path(db_obtain) and not _is_generic_acquire_path(
        bili_obtain
    ):
        out["获取途径"] = bili_obtain
    if bili_part.get("联动") is True:
        out["联动"] = True
    pool = (bili_part.get("联动卡池") or "").strip()
    if pool:
        out["联动卡池"] = pool
    return enrich_collab_meta(out)


def is_supplementary_complete(
    sup: dict[str, str],
    required_fields: list[str],
) -> bool:
    for key in required_fields:
        if not str(sup.get(key) or "").strip():
            return False
    return True


def missing_supplementary_fields(
    sup: dict[str, Any] | None,
    fields: list[str],
) -> list[str]:
    """返回仍为空缺的字段名列表。"""
    if not sup:
        return list(fields)
    return [key for key in fields if not str(sup.get(key) or "").strip()]


def needs_supplementary_fetch(
    sup: dict[str, Any] | None,
    fill_fields: list[str],
) -> bool:
    return bool(missing_supplementary_fields(sup, fill_fields))


def has_meaningful_supplementary(sup: dict[str, str]) -> bool:
    return any(str(sup.get(k) or "").strip() for k in SUPPLEMENTARY_KEYS)


class OperatorSupplementaryRepository:
    def __init__(self, config: dict, *, config_path: str | None = None):
        self._config = config
        self._config_path = config_path
        self._settings = resolve_database_settings(config)
        self._factory = get_session_factory(config, config_path=config_path)

    @property
    def available(self) -> bool:
        return self._factory is not None and self._settings["enabled"]

    def get_char_id_by_name(self, name: str) -> str | None:
        """读取 operator_supplementary 中保存的 char_id（OCR/写入时落库）。"""
        if not self.available or not name:
            return None
        with self._factory() as session:
            row = session.get(OperatorSupplementary, name)
            if row is None:
                return None
            cid = (row.char_id or "").strip()
            return cid or None

    def get_by_name(self, name: str) -> dict[str, str] | None:
        if not self.available:
            return None
        with self._factory() as session:
            row = session.get(OperatorSupplementary, name)
            if row is None:
                return None
            return enrich_collab_meta(row_to_dict(row))

    def list_complete_names(
        self,
        limit: int,
        required_fields: list[str],
    ) -> list[str]:
        """按更新时间倒序，返回补充字段已齐全的干员名。"""
        if not self.available or limit <= 0:
            return []
        with self._factory() as session:
            rows = session.scalars(select(OperatorSupplementary)).all()
        out: list[str] = []
        for row in sorted(
            rows,
            key=lambda r: r.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        ):
            sup = row_to_dict(row)
            if is_supplementary_complete(sup, required_fields):
                out.append(row.name)
            if len(out) >= limit:
                break
        return out

    def get_by_char_id(self, char_id: str) -> dict[str, str] | None:
        if not self.available or not char_id:
            return None
        with self._factory() as session:
            stmt = select(OperatorSupplementary).where(
                OperatorSupplementary.char_id == char_id
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None
            return enrich_collab_meta(row_to_dict(row))

    def upsert(
        self,
        name: str,
        supplementary: dict[str, str],
        *,
        char_id: str | None = None,
        source: str = "bilibili",
    ) -> None:
        if not self.available or not self._settings["write_after_fallback"]:
            return
        if not has_meaningful_supplementary(supplementary):
            log_warning("跳过写入数据库（补充字段均为空）：%s", name)
            return
        now = datetime.now(timezone.utc)
        row_payload = supplementary_for_upsert(supplementary)
        with self._factory() as session:
            row = session.get(OperatorSupplementary, name)
            if row is None:
                row = OperatorSupplementary(name=name)
                session.add(row)
            if char_id:
                row.char_id = char_id
            for key, col in _KEY_TO_COLUMN.items():
                val = row_payload.get(key) or ""
                if val:
                    setattr(row, col, val)
            row.source = source
            row.updated_at = now
            session.commit()
        drawer = row_payload.get("画师") or ""
        spec = row_payload.get("专精") or ""
        log_info(
            "已写入 operator_supplementary：%s char_id=%s 画师=%s 专精=%s",
            name,
            char_id or "",
            drawer[:40] + ("…" if len(drawer) > 40 else ""),
            spec[:40] + ("…" if len(spec) > 40 else ""),
        )
