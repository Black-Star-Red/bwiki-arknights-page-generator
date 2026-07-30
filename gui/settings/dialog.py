from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QApplication,
    QFileDialog,
    QFormLayout,
    QPlainTextEdit,
    QTabWidget,
)
from pathlib import Path
from page_bilibili import bilibili_Dialog
import sys
class SettingsDialog(QDialog):
    def __init__(self, config_path:str,parent= None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(720, 480)
        self.tab = QTabWidget(self)
        self.tab.setGeometry(10, 10, 700, 460)
        self.tab.addTab(bilibili_Dialog(config_path), "Bilibili")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = SettingsDialog("config.json")
    sys.exit(dialog.exec())
