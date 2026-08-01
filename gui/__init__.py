"""GUI exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import ArknightsToolWindow

__all__ = ["ArknightsToolWindow", "main"]


def __getattr__(name: str):
    if name in ("ArknightsToolWindow", "main"):
        from .main_window import ArknightsToolWindow, main

        return ArknightsToolWindow if name == "ArknightsToolWindow" else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

