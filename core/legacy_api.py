"""已弃用：请改用 `arknights_toolbox.core.character_script`。"""

from __future__ import annotations

import warnings
from typing import Any

from .character_script import main as _main
from .character_script.pipeline import run_character_pipeline as _run_character_pipeline


def _warn_legacy(name: str) -> None:
    warnings.warn(
        f"{name} 已弃用，请改用 arknights_toolbox.core.character_script",
        DeprecationWarning,
        stacklevel=3,
    )


def run_legacy_pipeline(*args: Any, **kwargs: Any) -> str:
    _warn_legacy("run_legacy_pipeline")
    return _run_character_pipeline(*args, **kwargs)


def run_legacy_cli() -> None:
    _warn_legacy("run_legacy_cli")
    _main()


__all__ = ["run_legacy_pipeline", "run_legacy_cli"]
