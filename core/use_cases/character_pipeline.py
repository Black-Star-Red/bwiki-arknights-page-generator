"""Application use case for character page generation."""

from __future__ import annotations

from typing import Any

from ..legacy_api import run_legacy_pipeline


def run_character_pipeline(*args: Any, **kwargs: Any) -> str:
    """
    Public use-case entry for character generation.

    This isolates callers from the legacy script location and loading details.
    """
    return run_legacy_pipeline(*args, **kwargs)


__all__ = ["run_character_pipeline"]
