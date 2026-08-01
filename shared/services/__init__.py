"""Shared service modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .activity_catalog import (
    ACTIVITY_TABLE_SOURCE_ID,
    ActivityRecord,
    list_activities_for_ui,
    list_activities_from_data_source,
    list_activities_from_mapper,
)
from .bilibili_service import (
    fetch_character_supplementary_data,
    fetch_user_dynamics,
    operator_photo_dir,
)
from .hypergryph_settings import resolve_hypergryph_settings
from .request_headers import (
    build_bilibili_headers,
    build_hycdn_portrait_headers,
    build_wiki_headers,
)
from .wiki_service import (
    publish_wiki_page_if_enabled,
    upload_operator_portrait_if_enabled,
    upload_site_file_with_retry,
    write_site_page,
)

if TYPE_CHECKING:
    from .ocr_service import ocr_exec, ocr_operator_profile

__all__ = [
    "ACTIVITY_TABLE_SOURCE_ID",
    "ActivityRecord",
    "list_activities_for_ui",
    "list_activities_from_data_source",
    "list_activities_from_mapper",
    "fetch_character_supplementary_data",
    "fetch_user_dynamics",
    "operator_photo_dir",
    "build_bilibili_headers",
    "build_hycdn_portrait_headers",
    "build_wiki_headers",
    "write_site_page",
    "upload_site_file_with_retry",
    "publish_wiki_page_if_enabled",
    "ocr_exec",
    "ocr_operator_profile",
    "upload_operator_portrait_if_enabled",
    "resolve_hypergryph_settings",
]


def __getattr__(name: str):
    if name in ("ocr_exec", "ocr_operator_profile"):
        from .ocr_service import ocr_exec, ocr_operator_profile

        return ocr_exec if name == "ocr_exec" else ocr_operator_profile
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
