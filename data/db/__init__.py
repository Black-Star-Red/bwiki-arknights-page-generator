"""数据库访问层（干员 B 站补充数据缓存）。"""

from .engine import get_session_factory, is_database_enabled, resolve_database_settings
from .models import Base, OperatorSupplementary
from .supplementary_repo import (
    OperatorSupplementaryRepository,
    SUPPLEMENTARY_KEYS,
    apply_db_with_bili_meta,
    empty_supplementary_dict,
    has_meaningful_supplementary,
    is_supplementary_complete,
    merge_supplementary,
    merge_supplementary_bilibili_first,
    row_to_dict,
)

__all__ = [
    "Base",
    "OperatorSupplementary",
    "OperatorSupplementaryRepository",
    "SUPPLEMENTARY_KEYS",
    "empty_supplementary_dict",
    "has_meaningful_supplementary",
    "is_supplementary_complete",
    "apply_db_with_bili_meta",
    "merge_supplementary",
    "merge_supplementary_bilibili_first",
    "row_to_dict",
    "get_session_factory",
    "is_database_enabled",
    "resolve_database_settings",
]
