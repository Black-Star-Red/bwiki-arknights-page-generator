"""GUI entrypoint in new package layout."""

from __future__ import annotations
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for p in (root.parent, root):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from gui.main_window import main
if __name__ == "__main__":
    main()

