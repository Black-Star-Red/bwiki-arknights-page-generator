"""
Arknights 数据工具 — PySide6 界面（配置路径、数据源、Wiki 选项、运行、结果区）


运行: python Gui/ark_gui_mock.py
依赖: pip install PySide6
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

from arknights_toolbox.core.legacy_api import run_legacy_pipeline

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QSpinBox,
    QFormLayout,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_ark_gui_operator_sections(text: str) -> list[tuple[str, str]] | None:
    """解析「干员脚本2.0」返回的 <<<ARK_GUI_OP|名称>>> 分段；无法解析则返回 None。"""
    head = "<<<ARK_GUI_OP|"
    if head not in text:
        return None
    out: list[tuple[str, str]] = []
    rest = text
    while True:
        p = rest.find(head)
        if p == -1:
            break
        rest = rest[p + len(head) :]
        end_h = rest.find(">>>")
        if end_h == -1:
            return out or None
        name = rest[:end_h].strip()
        rest = rest[end_h + 3 :]
        if rest.startswith("\n"):
            rest = rest[1:]
        nxt = rest.find(head)
        body = rest if nxt == -1 else rest[:nxt]
        out.append((name, body.rstrip()))
        if nxt == -1:
            break
        rest = rest[nxt:]
    return out or None


class WikiConfirmBridge(QObject):
    """在主线程执行 QMessageBox；工作线程通过信号投递到 GUI 线程并同步等待结果。

    说明：原先用 QMetaObject.invokeMethod 调 Python @Slot，在 PySide6 上常返回失败，
    表现为不弹窗、wiki_confirm 恒为否、Wiki 步骤被跳过。
    """

    confirm_requested = Signal(str, str)

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(parent_window)
        self._w = parent_window
        self._last_answer = False
        self._done = threading.Event()
        self.confirm_requested.connect(self._ask_impl, Qt.ConnectionType.QueuedConnection)

    @Slot(str, str)
    def _ask_impl(self, prompt: str, wiki_key: str) -> None:
        title = "确认 Wiki 写入"
        body = (
            f"{prompt}\n\n"
            f"步骤：{wiki_key}\n"
            "界面上的勾选仅表示「允许尝试」；此处为写入前的二次确认。\n\n"
            "是否继续写入 Wiki？"
        )
        self._last_answer = (
            QMessageBox.question(
                self._w,
                title,
                body,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )
        self._done.set()

    def ask_blocking(self, prompt: str, wiki_key: str) -> bool:
        """供后台线程调用：在主线程弹窗，阻塞到用户选择。"""
        if QThread.currentThread() is self.thread():
            self._done.clear()
            self._ask_impl(prompt, wiki_key)
            return bool(self._last_answer)
        self._done.clear()
        self.confirm_requested.emit(prompt, wiki_key)
        self._done.wait()
        return bool(self._last_answer)


class OperatorRunThread(QThread):
    """在子线程中加载并执行干员脚本，避免阻塞 Qt 事件循环。"""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        config_path: str,
        data_source: str,
        wiki_flags: dict,
        wiki_bridge: WikiConfirmBridge | None,
        quiet: bool,
        wiki_use_test_page: bool,
        character_num: int,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._data_source = data_source
        self._wiki_flags = wiki_flags
        self._wiki_bridge = wiki_bridge
        self._quiet = quiet
        self._wiki_use_test_page = wiki_use_test_page
        self._character_num = character_num
    def run(self) -> None:
        # _project_root() = .../arknights_toolbox；import arknights_toolbox 需要仓库根在 sys.path
        pkg_root = _project_root()
        repo_root = str(pkg_root.parent)
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        try:
            wiki_confirm = None
            bridge = self._wiki_bridge
            if bridge is not None:

                def wiki_confirm(prompt: str, wiki_key: str) -> bool:
                    return bridge.ask_blocking(prompt, wiki_key)

            tpl = run_legacy_pipeline(
                config_path=self._config_path,
                data_source_group=self._data_source,
                wiki_flags=dict(self._wiki_flags),
                voice_json={},
                log_path=None,
                no_log_file=False,
                quiet=self._quiet,
                interactive=False,
                wiki_use_test_page=self._wiki_use_test_page,
                wiki_confirm=wiki_confirm,
                character_num=self._character_num,
            )
            self.succeeded.emit(tpl or "")
        except BaseException as e:
            self.failed.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


class ArknightsToolWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arknights 数据工具（PySide6）")
        self.resize(960, 640)
        self._run_thread: OperatorRunThread | None = None
        self._wiki_bridge = WikiConfirmBridge(self)

        root = _project_root()
        default_config = root / "config" / "config.json"

        self.edit_config = QLineEdit()
        self.edit_config.setPlaceholderText("config.json 路径")
        if default_config.is_file():
            self.edit_config.setText(str(default_config))

        btn_cfg = QPushButton("浏览…")
        btn_cfg.clicked.connect(self._pick_config)

        self.chk_wiki_test_page = QCheckBox("Wiki 沙盒（写入「用户:…/测试页」，取消则写入正式词条）")
        self.chk_wiki_test_page.setChecked(True)
        self.form_layout = QFormLayout()
        self.chk_character_num = QSpinBox()
        self.chk_character_num.setRange(1, 100)
        self.chk_character_num.setValue(3)
        self.chk_character_num.setSuffix(" 个干员")
        self.form_layout.addRow("选择干员数量(按实装顺序)", self.chk_character_num)
        row_left_check = QHBoxLayout()
        row_left_check.addWidget(self.chk_wiki_test_page)
        row_left_check.addLayout(self.form_layout)
        row_cfg = QHBoxLayout()
        row_cfg.addWidget(QLabel("配置文件"))
        row_cfg.addWidget(self.edit_config, stretch=1)
        row_cfg.addWidget(btn_cfg)

        self.combo_source = QComboBox()
        self.combo_source.addItems(
            (
                "Kengxxiao/ArknightsGameData",
                "yuanyan3060/ArknightsGameResource",
            )
        )
        self.combo_source.setCurrentIndex(0)

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("数据源"))
        row_src.addWidget(self.combo_source, stretch=1)

        log_mode_box = QGroupBox("日志 / 调试")
        log_mode_row = QHBoxLayout(log_mode_box)
        self.radio_log_normal = QRadioButton("普通（控制台少 DEBUG，等同 CLI 加 -q）")
        self.radio_log_debug = QRadioButton("调试（控制台输出 DEBUG，等同 CLI 不加 -q）")
        self.radio_log_normal.setChecked(True)
        self._log_mode_group = QButtonGroup(self)
        self._log_mode_group.addButton(self.radio_log_normal)
        self._log_mode_group.addButton(self.radio_log_debug)
        log_mode_row.addWidget(self.radio_log_normal)
        log_mode_row.addWidget(self.radio_log_debug)
        log_mode_row.addStretch(1)

        wiki_box = QGroupBox("Wiki")
        wiki_grid = QGridLayout(wiki_box)

        self.chk_wiki_operator = QCheckBox("创建 / 更新干员页面")
        self.chk_wiki_operator.setChecked(True)
        self.chk_wiki_voice = QCheckBox("创建 / 更新语音页面")
        self.chk_wiki_voice.setChecked(True)
        self.chk_wiki_portrait = QCheckBox("上传半身像")
        self.chk_wiki_portrait.setChecked(False)

        wiki_grid.addWidget(self.chk_wiki_operator, 0, 0)
        wiki_grid.addWidget(self.chk_wiki_voice, 0, 1)
        wiki_grid.addWidget(self.chk_wiki_portrait, 1, 0)

        btn_all = QPushButton("Wiki 全选")
        btn_all.clicked.connect(self._wiki_select_all)
        btn_none = QPushButton("Wiki 清空")
        btn_none.clicked.connect(self._wiki_select_none)
        row_wiki_btns = QHBoxLayout()
        row_wiki_btns.addWidget(btn_all)
        row_wiki_btns.addWidget(btn_none)
        row_wiki_btns.addStretch(1)
        wiki_grid.addLayout(row_wiki_btns, 2, 0, 1, 2)

        self.btn_run = QPushButton("运行")
        self.btn_run.setMinimumHeight(36)
        self.btn_run.clicked.connect(self._on_run)

        self.result_tabs = QTabWidget()
        self.result_tabs.setDocumentMode(True)
        self.result_tabs.setTabsClosable(False)
        self._placeholder_result = "运行摘要、每位干员的模板预览将显示在下方标签页…"

        main = QVBoxLayout(self)
        main.addLayout(row_left_check)
        main.addLayout(row_cfg)
        main.addLayout(row_src)
        main.addWidget(log_mode_box)
        main.addWidget(wiki_box)
        main.addWidget(self.btn_run)
        main.addWidget(QLabel("结果（按干员分页）"), alignment=Qt.AlignmentFlag.AlignLeft)
        main.addWidget(self.result_tabs, stretch=1)

        self._clear_result_tabs()
        self._add_result_tab("提示", self._placeholder_result, editable=False)

    def _clear_result_tabs(self) -> None:
        while self.result_tabs.count():
            w = self.result_tabs.widget(0)
            self.result_tabs.removeTab(0)
            if w is not None:
                w.deleteLater()

    def _add_result_tab(self, title: str, body: str, *, editable: bool) -> QPlainTextEdit:
        te = QPlainTextEdit()
        te.setReadOnly(not editable)
        te.setPlainText(body)
        self.result_tabs.addTab(te, title[:40] + ("…" if len(title) > 40 else ""))
        return te

    def _show_result_text(self, text: str, *, fallback_tab_title: str = "结果") -> None:
        """按干员拆分显示；若无分段标记则单页展示全文。"""
        self._clear_result_tabs()
        parsed = _parse_ark_gui_operator_sections(text)
        if parsed:
            for name, body in parsed:
                self._add_result_tab(name or "（未命名）", body, editable=False)
            return
        self._add_result_tab(fallback_tab_title, text or "", editable=False)

    def _pick_config(self) -> None:
        start = _project_root()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 config.json",
            str(start),
            "JSON (*.json);;所有文件 (*.*)",
        )
        if path:
            self.edit_config.setText(path)

    def _wiki_select_all(self) -> None:
        self.chk_wiki_operator.setChecked(True)
        self.chk_wiki_voice.setChecked(True)
        self.chk_wiki_portrait.setChecked(True)

    def _wiki_select_none(self) -> None:
        self.chk_wiki_operator.setChecked(False)
        self.chk_wiki_voice.setChecked(False)
        self.chk_wiki_portrait.setChecked(False)

    def wiki_flags(self) -> dict[str, bool]:
        return {
            "wiki_operator_page": self.chk_wiki_operator.isChecked(),
            "wiki_voice_page": self.chk_wiki_voice.isChecked(),
            "wiki_portrait": self.chk_wiki_portrait.isChecked(),
        }

    def log_quiet(self) -> bool:
        """True=普通/安静；False=调试（与 run_character_pipeline(quiet=...) 一致）。"""
        return not self.radio_log_debug.isChecked()

    def _on_run(self) -> None:
        cfg = self.edit_config.text().strip()
        if not cfg or not os.path.isfile(cfg):
            QMessageBox.warning(self, "提示", "请先选择有效的 config.json 路径。")
            return
        if self._run_thread is not None and self._run_thread.isRunning():
            QMessageBox.information(self, "提示", "已有任务在运行，请稍候。")
            return

        src = self.combo_source.currentText()
        flags = self.wiki_flags()
        quiet = self.log_quiet()
        wiki_sandbox = self.chk_wiki_test_page.isChecked()
        character_num = self.chk_character_num.value()
        self._show_result_text(
            "—— 运行中 ——\n"
            f"配置: {cfg}\n"
            f"数据源: {src}\n"
            f"日志模式: {'普通(quiet=True)' if quiet else '调试(quiet=False)'}\n"
            f"Wiki(非交互): 干员页={flags['wiki_operator_page']} "
            f"语音页={flags['wiki_voice_page']} 半身像={flags['wiki_portrait']}\n"
            f"Wiki 写入目标: {'沙盒测试页' if wiki_sandbox else '正式词条标题'}\n"
            f"选择干员数量: {character_num} 个\n"
            "写入 Wiki 前将弹出二次确认（主线程对话框）。\n\n"
            "日志写入项目目录下 debug.log …\n",
            fallback_tab_title="运行状态",
        )
        self.btn_run.setEnabled(False)

        self._run_thread = OperatorRunThread(
            config_path=cfg,
            data_source=src,
            wiki_flags=flags,
            wiki_bridge=self._wiki_bridge,
            quiet=quiet,
            wiki_use_test_page=wiki_sandbox,
            character_num=character_num,
        )
        self._run_thread.succeeded.connect(self._on_run_succeeded)
        self._run_thread.failed.connect(self._on_run_failed)
        self._run_thread.finished.connect(self._on_run_thread_finished)
        self._run_thread.start()

    def _on_run_succeeded(self, text: str) -> None:
        self._show_result_text(text or "", fallback_tab_title="输出")
        if not (text or "").strip():
            QMessageBox.warning(
                self,
                "完成（无输出）",
                "流水线已结束，但生成的模板为空。\n"
                "常见原因：B 站动态/API 未解析到任何干员（补充数据为空），"
                "脚本主循环未执行，因而不会出现 Wiki 确认弹窗。\n"
                "请查看项目目录下 debug.log，或改用 CLI/检查网络与 cookies。",
            )
        else:
            QMessageBox.information(self, "完成", "生成结束，结果已填入下方文本框。")

    def _on_run_failed(self, err: str) -> None:
        self._show_result_text("—— 运行失败 ——\n\n" + err, fallback_tab_title="错误")
        QMessageBox.critical(self, "运行失败", err[:800] + ("…" if len(err) > 800 else ""))

    def _on_run_thread_finished(self) -> None:
        self.btn_run.setEnabled(True)
        self._run_thread = None


def main() -> None:
    # 干员脚本会按「含 arknights_toolbox/log 的目录」解析工程根；B 站配图写入 arknights_toolbox/photo/。
    # GUI 若从 IDE/快捷方式启动 cwd 不一致时，这里切到包目录，避免日志与路径解析跑偏。
    try:
        os.chdir(_project_root())
    except OSError:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ArknightsToolWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()