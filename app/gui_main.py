"""GUI entrypoint in new package layout."""

from __future__ import annotations
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1] # 获取项目根目录F:\项目\arknights_toolbox
for p in (root.parent, root):
    p_str = str(p)
#  sys.path用来指定 Python 搜索模块（import）的路径
#     import foo
#     ↓
# 按 sys.path[0]、sys.path[1]、… 依次找：
#   sys.path[0]/foo.py
#   sys.path[0]/foo/__init__.py
#   sys.path[1]/foo.py
#   ...
# 找到就用，全找不到 → ModuleNotFoundError
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from gui.main_window import main
if __name__ == "__main__":
    main()

