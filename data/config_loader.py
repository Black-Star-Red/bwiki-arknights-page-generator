"""配置文件发现与加载（与 DataMapper 解耦）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence


def default_config_search_dirs() -> list[Path]:
    """本仓库默认配置搜索目录；拆出去用时由调用方传入 search_dirs。"""
    pkg_root = Path(__file__).resolve().parents[1]
    return [
        pkg_root / "config",
        pkg_root,
        Path.cwd(),
    ]


def resolve_config_path(
    config_path: str | Path,
    *,
    search_dirs: Sequence[Path] | None = None,
) -> Path:
    """将相对/绝对路径解析为存在的配置文件绝对路径。"""
    p = Path(config_path)
    if p.is_file():
        return p.resolve()

    if p.is_absolute():
        raise FileNotFoundError(f"配置文件不存在: {p}")

    dirs = list(search_dirs or default_config_search_dirs())
    for base in dirs:
        candidate = (base / p).resolve()
        if candidate.is_file():
            return candidate

    legacy = (Path.cwd() / "ArknightsGameData" / p).resolve()
    if legacy.is_file():
        return legacy

    tried = [str(base / p) for base in dirs] + [str(legacy)]
    raise FileNotFoundError(
        f"配置文件未找到: {config_path!r}\n已尝试:\n  " + "\n  ".join(tried)
    )


def read_config_file(path: Path) -> dict:
    """读取单个 JSON/YAML 配置文件。"""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError(
                f"配置文件是 YAML，但未安装 PyYAML: {path}\n请安装: pip install pyyaml"
            ) from e
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    raise RuntimeError(f"不支持的配置格式: {path}")

def _deep_merge(base: dict, patch: dict) -> dict:
    """递归合并：patch 覆盖 base 同名 key。"""
    out = dict(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
def _resolve_include_path(include:str,base_dir:Path) -> Path:
    p = Path(include)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()
def _load_with_includes(path: Path, *, _stack: set[Path] | None = None) -> dict:
    """读单个文件并展开 $include（相对路径相对于当前文件所在目录）。"""
    _stack = _stack or set()
    path = path.resolve()
    if path in _stack:
        raise RuntimeError(f"配置循环引用: {path}")
    _stack.add(path)
    config = read_config_file(path)
    includes = config.pop("$include", None)
    if not includes:
        return config
    if isinstance(includes, str):
        includes = [includes]
    if not isinstance(includes, list):
        raise RuntimeError(f"$include 必须是字符串或字符串列表: {path}")
    merged = config
    for item in includes:
        child_path = _resolve_include_path(item, path.parent)
        if not child_path.is_file():
            raise FileNotFoundError(f"$include 文件不存在: {item} (来自 {path})")
        child = _load_with_includes(child_path, _stack=_stack)
        merged = _deep_merge(merged, child)
    return merged
def load_config(
    config_path: str | Path,
    *,
    search_dirs: Sequence[Path] | None = None,
) -> dict:
    """解析路径 → 读主配置 → 合并 *.local → 应用环境变量。"""
    base_path = resolve_config_path(config_path, search_dirs=search_dirs)
    config = _load_with_includes(base_path)
    local_path = local_config_path(base_path)
    if local_path.is_file():
        local = _load_with_includes(local_path)
        config = _deep_merge(config, local)

    env_cookies = os.getenv("ARK_TOOL_COOKIES")
    if env_cookies:
        config["cookies"] = env_cookies

    return config


def local_config_path(config_path: str | Path, *, search_dirs: Sequence[Path] | None = None) -> Path:
    """主 config.json → 同目录 config.local.json（不要求 local 已存在）。"""
    base = Path(config_path)
    if not base.is_file():
        base = resolve_config_path(config_path, search_dirs=search_dirs)
    else:
        base = base.resolve()
    return base.with_name(f"{base.stem}.local{base.suffix}")


def read_local_config(
    config_path: str | Path,
    *,
    search_dirs: Sequence[Path] | None = None,
) -> dict:
    """只读 *.local.json；不存在则返回空 dict。"""
    path = local_config_path(config_path, search_dirs=search_dirs)
    if not path.is_file():
        return {}
    return read_config_file(path) or {}


def save_local_patch(
    config_path: str | Path,
    patch: dict,
    *,
    search_dirs: Sequence[Path] | None = None,
) -> Path:
    """深合并 patch 进 *.local.json 并写回；保留 database 等未改字段。"""
    path = local_config_path(config_path, search_dirs=search_dirs)
    existing = read_local_config(config_path, search_dirs=search_dirs)
    merged = _deep_merge(existing, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "default_config_search_dirs",
    "resolve_config_path",
    "read_config_file",
    "load_config",
    "local_config_path",
    "read_local_config",
    "save_local_patch",
]
