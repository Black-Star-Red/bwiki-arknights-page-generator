"""数据库访问层（干员 B 站补充数据缓存）。"""

from .engine import get_session_factory, is_database_enabled, resolve_database_settings
from .activity_repo import ActivityRepository
from .models import Activity, Base, OperatorSupplementary
from .supplementary_repo import (
    OperatorSupplementaryRepository,
    SUPPLEMENTARY_KEYS,
    apply_bili_ocr_over_empty,
    apply_db_with_bili_meta,
    empty_supplementary_dict,
    has_meaningful_supplementary,
    is_supplementary_complete,
    lookup_supplementary_in_batch,
    merge_supplementary,
    merge_supplementary_bilibili_first,
    normalize_supplementary_name_key,
    resolve_supplementary_batch_key,
    row_to_dict,
    needs_supplementary_fetch,
    missing_supplementary_fields,
    supplementary_for_upsert,
)

__all__ = [
    "Activity",
    "ActivityRepository",
    "Base",
    "OperatorSupplementary",
    "OperatorSupplementaryRepository",
    "SUPPLEMENTARY_KEYS",
    "empty_supplementary_dict",
    "has_meaningful_supplementary",
    "is_supplementary_complete",
    "apply_bili_ocr_over_empty",
    "apply_db_with_bili_meta",
    "lookup_supplementary_in_batch",
    "normalize_supplementary_name_key",
    "resolve_supplementary_batch_key",
    "supplementary_for_upsert",
    "merge_supplementary",
    "merge_supplementary_bilibili_first",
    "row_to_dict",
    "get_session_factory",
    "is_database_enabled",
    "resolve_database_settings",
    "needs_supplementary_fetch",
    "missing_supplementary_fields",
]
