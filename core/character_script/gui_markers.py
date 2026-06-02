"""GUI 分标签标记的剥离。"""

from __future__ import annotations

import re


def strip_ark_gui_operator_markers(text: str) -> str:
    """去掉供 GUI 分标签用的行首标记；CLI 打印/写文件时更易读。"""
    return re.sub(r"^<<<ARK_GUI_OP\|[^>\n]+>>>\s*\n?", "", text or "", flags=re.MULTILINE)
