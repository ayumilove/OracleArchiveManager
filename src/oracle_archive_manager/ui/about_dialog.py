"""关于弹窗：应用信息 + 原则 + 项目链接 + 检查更新。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .. import __version__
from ..services.update_checker import has_update
from .icons import icon
from .update_dialog import UpdateCheckWorker, UpdateDialog

GITHUB_URL = "https://github.com/ayumilove/OracleArchiveManager"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 Oracle Archive Manager")
        self.setFixedWidth(440)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icon("app").pixmap(48, 48))
        head.addWidget(logo)
        texts = QVBoxLayout()
        name = QLabel("Oracle Archive Manager")
        name.setStyleSheet("font-size:16px; font-weight:700;")
        ver = QLabel(f"v{__version__}")
        ver.setStyleSheet(
            "color:#2563eb; border:1px solid #2563eb66; background:#2563eb1a; "
            "border-radius:4px; padding:2px 8px; font-size:12px; font-weight:600;"
        )
        ver.setFixedWidth(60)
        texts.addWidget(name)
        texts.addWidget(ver, 0, Qt.AlignLeft)
        head.addLayout(texts)
        head.addStretch(1)
        lay.addLayout(head)

        desc = QLabel(
            "面向 Oracle 生产库的历史数据归档与清理工具：\n"
            "分析 → 复制 → 校验 → 人工确认 → 清理，全链路审计留痕。"
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        lay.addWidget(desc)

        principle = QLabel("原则：复制是自动的，清理必须经显式确认。")
        principle.setStyleSheet(
            "background:#fbfcfe; border:1px solid #e8edf3; border-radius:8px; "
            "padding:10px 12px; font-weight:600;"
        )
        principle.setWordWrap(True)
        lay.addWidget(principle)

        link = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
        link.setStyleSheet("color:#2563eb;")
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(lambda u: QDesktopServices.openUrl(QUrl(u)))
        lay.addWidget(link)

        copyright_lbl = QLabel("© 2026 xcode.im")
        copyright_lbl.setObjectName("muted")
        lay.addWidget(copyright_lbl)

        foot = QHBoxLayout()
        foot.addStretch(1)
        self.btn_check = QPushButton("检查更新")
        self.btn_check.clicked.connect(self._on_check_update)
        foot.addWidget(self.btn_check)
        btn_ok = QPushButton("关闭")
        btn_ok.setObjectName("primary")
        btn_ok.clicked.connect(self.accept)
        foot.addWidget(btn_ok)
        lay.addLayout(foot)

    def _on_check_update(self) -> None:
        self.btn_check.setEnabled(False)
        self.btn_check.setText("正在检查…")
        self._check_worker = UpdateCheckWorker(self)
        self._check_worker.done.connect(self._on_check_done)
        self._check_worker.start()

    def _on_check_done(self, info) -> None:
        self.btn_check.setEnabled(True)
        self.btn_check.setText("检查更新")
        if info is not None and has_update(__version__, info.latest):
            UpdateDialog(info, self).exec()
        elif info is None:
            QMessageBox.warning(self, "检查更新", "无法连接更新服务，请检查网络后重试。")
        else:
            QMessageBox.information(self, "检查更新",
                                    f"当前已是最新版本（v{__version__}）。")
