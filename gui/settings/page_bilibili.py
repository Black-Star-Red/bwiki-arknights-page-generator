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
    QWidget,
)
from pathlib import Path
from data.config_loader import load_config
import sys
class bilibiliSettingsPage(QWidget):
    def __init__(self, config_path:str,parent= None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(720, 480)
        self.config_path = config_path
        self.lbl_status = QLabel()
        self.edit_mid = QLineEdit()
        self.edit_cookies = QPlainTextEdit()
        self.edit_cookies.setPlaceholderText("请输入Cookies(需含SESSDATA)")
        form = QFormLayout(self)
        form.addRow("登录状态",self.lbl_status)
        form.addRow("bilibili_mid",self.edit_mid)
        form.addRow("Cookies",self.edit_cookies)
    def load_from(self):
        config =load_config(self.config_path)
        self.edit_mid.setText(config.get("bilibili_mid",""))
        self.edit_cookies.setText(config.get("cookies",""))

        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = bilibiliSettingsPage("config.json")
    sys.exit(dialog.exec())
