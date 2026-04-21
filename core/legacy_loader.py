import importlib.util
from pathlib import Path

_LEGACY_FILE = "干员脚本2.0.py"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_legacy_script_module():
    script_path = _project_root() / "arknights_toolbox" / "core" / _LEGACY_FILE
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到 CLI 脚本: {script_path}")
    spec = importlib.util.spec_from_file_location("arknights_toolbox_core_cli", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法创建模块 spec: {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod