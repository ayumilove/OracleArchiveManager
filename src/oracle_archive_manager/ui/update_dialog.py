"""更新提示与 OTA 安装对话框：发现新版 → 引导下载或就地替换，见 12 §9。"""
from __future__ import annotations

import subprocess

from loguru import logger
from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .. import __version__
from ..services import update_checker as uc

_background_workers: list = []  # 防止后台 QThread 被 GC 提前回收


class UpdateCheckWorker(QThread):
    """后台检查 GitHub 最新版本，不阻塞 UI。"""

    done = Signal(object)  # UpdateInfo | None

    def run(self) -> None:
        try:
            info = uc.fetch_latest_release()
        except Exception as e:  # noqa: BLE001 - 网络/解析异常均按“未更新”降级
            logger.warning(f"检查更新失败：{e}")
            info = None
        self.done.emit(info)


class UpdateDownloadWorker(QThread):
    """后台下载新版 exe，带进度回调。"""

    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, info: uc.UpdateInfo, parent=None) -> None:
        super().__init__(parent)
        self.info = info

    def run(self) -> None:
        try:
            path = uc.download_asset(
                self.info, progress=lambda d, t: self.progress.emit(d, t))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"下载新版本失败：{e}")
            self.failed.emit(str(e))
            return
        self.done.emit(path)


class UpdateDialog(QDialog):
    """发现新版本时的引导对话框：就地安装（exe）或跳转发布页（源码运行）。"""

    def __init__(self, info: uc.UpdateInfo, parent=None) -> None:
        super().__init__(parent)
        self.info = info
        self.setWindowTitle("发现新版本")
        self.setFixedWidth(480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(10)

        title = QLabel(f"发现新版本 v{info.latest}")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        lay.addWidget(title)

        ver = QLabel(f"当前版本 v{__version__} → 最新版本 v{info.latest}")
        ver.setStyleSheet("color:#2563eb; font-weight:600;")
        lay.addWidget(ver)

        if info.notes:
            notes = QPlainTextEdit(info.notes)
            notes.setReadOnly(True)
            notes.setFixedHeight(150)
            lay.addWidget(notes)

        self.can_install = uc.is_frozen() and bool(info.asset_url)
        hint = QLabel(
            "点击「下载并安装」后程序将自动退出，替换为新版本并重新启动。"
            if self.can_install else
            "当前运行环境不支持自动安装，请前往发布页手动下载新版本。"
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        lay.addWidget(self.progress)

        foot = QHBoxLayout()
        foot.addStretch(1)
        if self.can_install:
            self.btn_install = QPushButton("下载并安装")
            self.btn_install.setObjectName("primary")
            self.btn_install.clicked.connect(self._on_install)
            foot.addWidget(self.btn_install)
        btn_page = QPushButton("前往发布页")
        btn_page.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(info.html_url)))
        foot.addWidget(btn_page)
        btn_later = QPushButton("稍后提醒")
        btn_later.clicked.connect(self.reject)
        foot.addWidget(btn_later)
        lay.addLayout(foot)

    def _on_install(self) -> None:
        self.btn_install.setEnabled(False)
        self.btn_install.setText("正在下载…")
        self.progress.setValue(0)
        self.progress.show()
        self._worker = UpdateDownloadWorker(self.info, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_downloaded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(done * 100 // total if total else 0)

    def _on_failed(self, msg: str) -> None:
        self.btn_install.setEnabled(True)
        self.btn_install.setText("下载并安装")
        self.progress.hide()
        QMessageBox.warning(
            self, "下载失败",
            f"下载新版本失败：{msg}\n\n可点击「前往发布页」手动下载。")

    def _on_downloaded(self, new_exe: str) -> None:
        bat = uc.build_updater_script(new_exe)
        logger.info(f"OTA 更新就绪：{new_exe}，更新脚本 {bat}")
        QMessageBox.information(
            self, "下载完成", "新版本已下载。程序即将退出，自动替换并重新启动。")
        # 脚本内会等待本进程退出后再替换，因此可以先启动脚本再退出
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        QApplication.quit()


def start_background_check(parent, silent: bool = True) -> None:
    """后台检查更新：有新版弹引导对话框；silent=False 时提示“已是最新”。"""
    worker = UpdateCheckWorker(parent)

    def _done(info) -> None:
        if worker in _background_workers:
            _background_workers.remove(worker)
        if info is not None and uc.has_update(__version__, info.latest):
            UpdateDialog(info, parent).show()
        elif not silent:
            QMessageBox.information(parent, "检查更新",
                                    f"当前已是最新版本（v{__version__}）。")

    worker.done.connect(_done)
    _background_workers.append(worker)
    worker.start()
