"""设置页：B 站 Cookie / mid / 登录状态。"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import requests
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.services.request_headers import build_bilibili_headers


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sessdata_expire_ts(cookie_str: str) -> int | None:
    for part in (cookie_str or "").split(";"):
        part = part.strip()
        if not part.lower().startswith("sessdata="):
            continue
        raw = unquote(part.split("=", 1)[1])
        bits = raw.split(",")
        if len(bits) >= 2 and bits[1].isdigit():
            return int(bits[1])
    return None


def cookie_status_text(cookie_str: str) -> str:
    """根据 SESSDATA 标注过期时间生成状态文案（本地解析，不请求网络）。"""
    lower = (cookie_str or "").lower()
    if "sessdata=" not in lower:
        return "未检测到 SESSDATA"
    ts = _sessdata_expire_ts(cookie_str)
    if ts is None:
        return "已有 SESSDATA，但无法解析过期时间"
    when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    uid = ""
    for part in (cookie_str or "").split(";"):
        part = part.strip()
        if part.startswith("DedeUserID=") and "__" not in part.split("=", 1)[0]:
            uid = part.split("=", 1)[1].strip()
            break
    uid_part = f"，DedeUserID={uid}" if uid else ""
    if time.time() >= ts:
        return f"已过期（标注至 {when}）{uid_part}"
    return f"未过期（有效至 {when}）{uid_part}"


class BilibiliSettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.lbl_status = QLabel("—")
        self.lbl_status.setWordWrap(True)
        self.edit_mid = QLineEdit()
        self.edit_mid.setPlaceholderText("例如官方动态 mid：161775300")
        self.edit_cookies = QPlainTextEdit()
        self.edit_cookies.setPlaceholderText(
            "粘贴 Cookie（需含 SESSDATA；可与 Wiki 的 gamecenter_wiki_* 写在同一串）"
        )
        self.edit_cookies.setMinimumHeight(160)

        self.btn_check_login = QPushButton("检测登录")
        self.btn_qr_login = QPushButton("扫码登录")
        self.btn_check_login.clicked.connect(self._on_check_login)
        self.btn_qr_login.clicked.connect(self._on_qr_login)
        self.edit_cookies.textChanged.connect(self._refresh_status_from_editor)

        row_btns = QHBoxLayout()
        row_btns.addWidget(self.btn_check_login)
        row_btns.addWidget(self.btn_qr_login)
        row_btns.addStretch(1)

        form = QFormLayout()
        form.addRow("登录状态", self.lbl_status)
        form.addRow("bilibili_mid", self.edit_mid)
        form.addRow("cookies", self.edit_cookies)

        layout = QVBoxLayout(self)
        layout.addLayout(row_btns)
        layout.addLayout(form)

    def load_from(self, local_data: dict) -> None:
        cookies = str((local_data or {}).get("cookies") or "")
        mid = str((local_data or {}).get("bilibili_mid") or "")
        self.edit_cookies.setPlainText(cookies)
        self.edit_mid.setText(mid)
        self.lbl_status.setText(cookie_status_text(cookies))

    def collect_patch(self) -> dict:
        return {
            "cookies": self.edit_cookies.toPlainText().strip(),
            "bilibili_mid": self.edit_mid.text().strip(),
        }

    def _refresh_status_from_editor(self) -> None:
        self.lbl_status.setText(cookie_status_text(self.edit_cookies.toPlainText()))

    def _on_qr_login(self) -> None:
        QMessageBox.information(self, "提示", "扫码登录尚未实现，请暂时手动粘贴 Cookie。")

    def _on_check_login(self) -> None:
        cookies = self.edit_cookies.toPlainText().strip()
        if not cookies:
            QMessageBox.warning(self, "提示", "请先填写 Cookie。")
            return
        mid = self.edit_mid.text().strip() or None
        headers = build_bilibili_headers(cookies, mid=mid)
        try:
            resp = requests.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=headers,
                timeout=15,
            )
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" not in ctype:
                QMessageBox.warning(
                    self,
                    "检测失败",
                    f"返回的不是 JSON（Content-Type={ctype or '空'}）。\n"
                    "请检查 Cookie / 网络，或稍后重试。",
                )
                return
            payload = resp.json()
            data = payload.get("data") or {}
            if payload.get("code") == 0 and data.get("isLogin"):
                uname = data.get("uname") or "?"
                uid = data.get("mid") or "?"
                local = cookie_status_text(cookies)
                self.lbl_status.setText(f"接口确认已登录：{uname}（mid={uid}）｜{local}")
                QMessageBox.information(self, "登录有效", f"已登录：{uname}\nmid={uid}")
            else:
                local = cookie_status_text(cookies)
                self.lbl_status.setText(f"接口判定未登录｜{local}")
                QMessageBox.warning(
                    self,
                    "未登录",
                    f"nav 接口判定未登录（code={payload.get('code')}）。\n"
                    "Cookie 可能已失效，请重新粘贴或等待扫码登录。",
                )
        except Exception as e:
            QMessageBox.critical(self, "检测失败", f"{type(e).__name__}: {e}")


# 兼容旧名
bilibiliSettingsPage = BilibiliSettingsPage


if __name__ == "__main__":
    root = _project_root()
    for p in (root, root.parent):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = BilibiliSettingsPage()
    cfg = root / "config" / "config.json"
    from data.config_loader import read_local_config

    w.load_from(read_local_config(cfg) if cfg.is_file() else {})
    w.setWindowTitle("B 站设置页预览")
    w.resize(720, 420)
    w.show()
    sys.exit(app.exec())
