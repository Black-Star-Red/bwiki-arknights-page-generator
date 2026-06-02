"""干员模板生成（由原 core/干员脚本2.0.py 拆分）。

对外入口（CLI / GUI / 脚本请统一由此 import）：
  from arknights_toolbox.core.character_script import run_character_pipeline, main
"""

from __future__ import annotations

from .cli import main
from .generate_operator_template import generate_template, load_json_file
from .gui_markers import strip_ark_gui_operator_markers
from .mapper_ops import collect_cid_name_pairs, resolve_operator_char_id
from .pipeline import run_character_pipeline
from .summon_template import generate_summon_template_by_charid

__all__ = [
    "main",
    "run_character_pipeline",
    "generate_template",
    "generate_summon_template_by_charid",
    "load_json_file",
    "strip_ark_gui_operator_markers",
    "collect_cid_name_pairs",
    "resolve_operator_char_id",
]
