"""CLI entrypoint for new package layout."""

from __future__ import annotations

import sys
from pathlib import Path
import importlib.util
def _project_root() -> Path:

    return  Path(__file__).resolve().parents[1]
def _load_cli_module():
    root = _project_root()
    for p in (root.parent, root):
        p_str = str(p)
        if p_str not in sys.path:
            sys.path.insert(0, p_str)
    script_path = root / "core" / "干员脚本2.0.py"
    spec = importlib.util.spec_from_file_location("arknights_toolbox_core_cli", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def main() -> None:
    mod = _load_cli_module()
    mod.main()


def run_character_pipeline(*args, **kwargs):
    mod = _load_cli_module()
    return mod.run_character_pipeline(*args, **kwargs)
__all__ = ["run_character_pipeline", "main"]


if __name__ == "__main__":
    main()

