"""设置对话框：多 Tab 壳 + 保存到 config.local.json。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from data.config_loader import read_local_config, save_local_patch
from gui.settings.page_bilibili import BilibiliSettingsPage


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class SettingsDialog(QDialog):
    def __init__(self, config_json_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(720, 480)
        self._config_path = str(config_json_path)

        self._tabs = QTabWidget()
        self._pages: list = []

        self._bili_page = BilibiliSettingsPage()
        self._add_page("B 站", self._bili_page)
        # 预留：Wiki / 数据库 Tab

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

        self._load()

    def _add_page(self, title: str, page) -> None:
        self._tabs.addTab(page, title)
        self._pages.append(page)

    def _load(self) -> None:
        try:
            data = read_local_config(self._config_path)
        except Exception as e:
            QMessageBox.warning(self, "读取 local 失败", str(e))
            data = {}
        for page in self._pages:
            page.load_from(data)

    def _on_save(self) -> None:
        patch: dict = {}
        for page in self._pages:
            patch.update(page.collect_patch())
        try:
            path = save_local_patch(self._config_path, patch)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"{type(e).__name__}: {e}")
            return
        QMessageBox.information(self, "已保存", f"已写入\n{path}")
        self.accept()


if __name__ == "__main__":
    root = _project_root()
    for p in (root, root.parent):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    cfg = root / "config" / "config.json"
    dlg = SettingsDialog(str(cfg))
    sys.exit(dlg.exec())
