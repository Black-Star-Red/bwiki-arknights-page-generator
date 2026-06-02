"""联动补充字段：获取途径解析与 联动/联动卡池 推断（供 DB merge 与角标共用）。"""

from __future__ import annotations

import re
from typing import Any

_COLLAB_OBTAIN_RE = re.compile(r"^联动、联动寻访、【([^】]+)】寻访")
_COLLAB_OBTAIN_LEGACY_RE = re.compile(r"^联动寻访、【([^】]+)】寻访")


def collab_pool_from_obtain(obtain: str) -> str | None:
    text = (obtain or "").strip()
    for pat in (_COLLAB_OBTAIN_RE, _COLLAB_OBTAIN_LEGACY_RE):
        m = pat.match(text)
        if m:
            return m.group(1).strip()
    return None


def enrich_collab_meta(value: dict[str, Any]) -> dict[str, Any]:
    """从 联动 标记或联动寻访获取途径补全 联动/联动卡池。"""
    out = dict(value)
    if out.get("联动") is True:
        return out
    pool = collab_pool_from_obtain(str(out.get("获取途径") or ""))
    if pool:
        out["联动"] = True
        if not str(out.get("联动卡池") or "").strip():
            out["联动卡池"] = pool
    return out
