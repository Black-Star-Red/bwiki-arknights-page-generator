"""Shared helper utilities extracted from legacy script."""

from __future__ import annotations

import re
from typing import Any

from arknights_toolbox.shared.globals import VOICE_ORDER


def safe_get(data: Any, keys: list[Any], default: Any = None):
    """
    Safely retrieve value from nested dict/list structures.

    Returns `default` if any segment is missing or invalid.
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        elif isinstance(current, list) and isinstance(key, int):
            if 0 <= key < len(current):
                current = current[key]
            else:
                return default
        else:
            return default
    return current


def normalize_voice_id(vid):
    """Extract numeric voice id and normalize to 3-digit string."""
    if vid is None:
        return None
    m = re.search(r"(\d+)", str(vid))
    if not m:
        return None
    return m.group(1).zfill(3)


def sort_key(item):
    """Sort key for voice rows: prioritized order first, then numeric id."""
    _, norm_vid, _ = item
    if norm_vid in VOICE_ORDER:
        return (1, VOICE_ORDER[norm_vid])
    return (0, int(norm_vid or 0))


def PHASE(phase_str):
    """Convert phase code (e.g. PHASE_0) to Chinese label."""
    mapping = {
        "PHASE_0": "精英化0",
        "PHASE_1": "精英化1",
        "PHASE_2": "精英化2",
    }
    return mapping.get(phase_str, phase_str)


__all__ = ["safe_get", "normalize_voice_id", "sort_key", "PHASE"]
