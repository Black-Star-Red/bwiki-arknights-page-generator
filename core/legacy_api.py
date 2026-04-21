"""Typed adapter layer for the legacy operator script."""

from __future__ import annotations

from types import ModuleType
from typing import Any

from .legacy_loader import load_legacy_script_module


def _load_legacy_module() -> ModuleType:
    """Load the legacy script module through a single adapter."""
    return load_legacy_script_module()


def run_legacy_pipeline(*args: Any, **kwargs: Any) -> str:
    """Run `run_character_pipeline` exposed by the legacy script."""
    mod = _load_legacy_module()
    run_fn = getattr(mod, "run_character_pipeline", None)
    if run_fn is None:
        raise AttributeError("Legacy script does not expose run_character_pipeline")
    return run_fn(*args, **kwargs)


def run_legacy_cli() -> None:
    """Run `main()` exposed by the legacy CLI script."""
    mod = _load_legacy_module()
    cli_main = getattr(mod, "main", None)
    if cli_main is None:
        raise AttributeError("core/干员脚本2.0.py 缺少 main()")
    cli_main()


__all__ = ["run_legacy_pipeline", "run_legacy_cli"]
