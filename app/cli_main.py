"""CLI 入口：委托给 `core.character_script`。"""

from __future__ import annotations

from core.character_script import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
