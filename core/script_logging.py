"""干员脚本 CLI/GUI 共用的日志：工程根探测、默认日志路径、logger 与 print 兼容层。"""

from __future__ import annotations

import logging
import sys
from builtins import print as _builtin_print
from datetime import datetime
from pathlib import Path

script_log = logging.getLogger("arknights_tool.script")


def _detect_project_root() -> Path:
    """
    首先从运行时的当前工作目录检测项目根目录，如果失败则回退到模块路径。
    """
    starts = [Path.cwd(), Path(__file__).resolve()]
    for start in starts:
        for parent in [start, *start.parents]:
            if (parent / "log").is_dir():
                return parent
            # 兼容「从更高一级目录打开工程」的场景
            nested = parent / "arknights_toolbox"
            if (nested / "log").is_dir():
                return nested
    return Path(__file__).resolve().parents[2]


def default_log_path() -> str:
    """返回项目日志目录下的每日日志文件路径。"""
    root = _detect_project_root()
    log_dir = root / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log")


def setup_script_logger(log_path: str | None, quiet: bool) -> None:
    """为脚本级日志附加控制台/文件处理程序。"""
    logger = script_log
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_level = logging.INFO if quiet else logging.DEBUG
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if log_path:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)


def log_info(message, *args):
    script_log.info(message, *args)


def log_warning(message, *args):
    script_log.warning(message, *args)


def log_error(message, *args):
    script_log.error(message, *args)


def script_print(*args, **kwargs):
    """
    统一兼容旧 print 调用：默认转为 logger，显式 file 输出时保持原行为。
    这样 GUI/CLI 都可直接消费同一套日志流。
    """
    if kwargs.get("file") is not None:
        return _builtin_print(*args, **kwargs)
    sep = kwargs.get("sep", " ")
    message = sep.join(str(x) for x in args)
    level = kwargs.pop("level", None)
    if level is None:
        # 轻量规则：含「失败/错误」默认 warning；含「fatal/critical」按 error
        lower = message.lower()
        if "fatal" in lower or "critical" in lower:
            level = "error"
        elif "失败" in message or "错误" in message:
            level = "warning"
        else:
            level = "info"
    level = str(level).lower()
    if level == "error":
        log_error("%s", message)
    elif level in ("warn", "warning"):
        log_warning("%s", message)
    else:
        log_info("%s", message)
