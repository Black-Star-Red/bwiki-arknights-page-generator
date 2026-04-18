"""Pipeline bridge to legacy operator script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_LEGACY_FILE = "干员脚本2.0.py"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_legacy_module() -> ModuleType:
    root = _project_root()
    script_path = root / "arknights_toolbox" / "core" / _LEGACY_FILE
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到脚本文件: {script_path}")
    spec = importlib.util.spec_from_file_location("ark_legacy_pipeline", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法创建模块 spec: {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_character_pipeline(*args, **kwargs):
    """Call legacy run_character_pipeline via new package path."""
    mod = _load_legacy_module()
    run_fn = getattr(mod, "run_character_pipeline", None)
    if run_fn is None:
        raise AttributeError("Legacy script does not expose run_character_pipeline")
    return run_fn(*args, **kwargs)

