"""共享辅助工具，提取自旧脚本。"""

from __future__ import annotations

import re
from typing import Any

from shared.globals import VOICE_ORDER


def safe_get(data: Any, keys: list[Any], default: Any = None):
    """
    从嵌套的字典/列表结构中安全地检索值。

    如果任何段缺失或无效，则返回 `default`。
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

__all__ = ["safe_get"]
