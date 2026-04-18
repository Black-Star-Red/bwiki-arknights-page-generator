"""CLI entrypoint for new package layout."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from arknights_toolbox.core.pipeline import run_character_pipeline


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_cli_module():
    script_path = _project_root() / "arknights_toolbox" / "core" / "干员脚本2.0.py"
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到 CLI 脚本: {script_path}")
    spec = importlib.util.spec_from_file_location("arknights_toolbox_core_cli", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法创建模块 spec: {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    mod = _load_cli_module()
    cli_main = getattr(mod, "main", None)
    if cli_main is None:
        raise AttributeError("core/干员脚本2.0.py 缺少 main()")
    cli_main()


__all__ = ["run_character_pipeline", "main"]


if __name__ == "__main__":
    main()

