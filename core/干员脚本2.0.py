"""
向后兼容占位：原单体脚本已拆分为 `arknights_toolbox.core.character_script`。

请使用：
  from arknights_toolbox.core.character_script import run_character_pipeline, main
"""

from __future__ import annotations

from core.character_script import main, run_character_pipeline

__all__ = ["main", "run_character_pipeline"]


if __name__ == "__main__":
    main()
