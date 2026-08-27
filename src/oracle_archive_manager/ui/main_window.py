"""主窗口：深色左导航 + 顶栏 + 状态栏，见 06_GUI_DESIGN.md §1/§2。"""
from __future__ import annotations

import getpass

from PySide6.QtCore import QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QPainter, QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from ..app.controller import AppController
from .about_dialog import AboutDialog, GITHUB_URL
from .icons import icon
from .pages.connection_page import ConnectionPage
from .pages.home_page import HomePage
from .pages.log_page import LogPage
from .pages.run_page import RunPage
from .pages.settings_page import SettingsPage
from .pages.task_page import TaskPage

_TOP_ACTIONS = [("设置", "settings-dark"), ("帮助", "help"), ("关于", "info")]

NAV_ITEMS = [
    ("首页\n(仪表盘)", "home"),
    ("任务管理", "task"),
    ("运行管理", "run"),
    ("连接管理", "connection"),
    ("日志查看", "log"),
    ("系统设置", "settings"),
]

_NAV_STYLE = """
    QListWidget { background:#16202c; color:#d7e0ea; border:none; font-size:13px; padding:10px 0px; }
    QListWidget::item { margin:3px 6px; }
"""


class _NavDelegate(QStyledItemDelegate):
    """导航项自绘：大图标在上 + 标题在下，整体水平居中。"""

    _ICON = 30

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(2, 2, -2, -2)

        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#1f3550" if selected else "#1a2836"))
            painter.drawRoundedRect(rect, 8, 8)

        pixmap = index.data(Qt.DecorationRole).pixmap(self._ICON, self._ICON)
        px = rect.x() + (rect.width() - pixmap.width()) // 2
        py = rect.y() + 6
        painter.drawPixmap(px, py, pixmap)

        painter.setPen(QColor("#ffffff" if selected else "#d7e0ea"))
        painter.setFont(option.font)
        text_rect = QRectF(rect.x(), py + pixmap.height() + 4,
                           rect.width(), rect.height() - (py - rect.y()) - pixmap.height() - 6)
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                         index.data(Qt.DisplayRole) or "")
        painter.restore()


def _status_item(icon_name: str, text: str, color: str = "#64748b") -> QWidget:
    """状态栏分组：小图标 + 文字，带内边距避免拥挤。"""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(10, 0, 10, 0)
    h.setSpacing(6)
    ic = QLabel()
    ic.setPixmap(icon(icon_name).pixmap(14, 14))
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{color};")
    h.addWidget(ic)
    h.addWidget(lbl)
    return w


def _status_sep() -> QWidget:
    """1px 单细线分隔（QFrame VLine 会画出双竖线，太生硬）。"""
    w = QWidget()
    w.setFixedSize(1, 16)
    w.setStyleSheet("background:#e3e8ee;")
    return w


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        from .. import __version__

        self._version = __version__
        self.setWindowTitle(f"Oracle Archive Manager {__version__}")
        self.setWindowIcon(icon("app"))

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧深色导航：大图标在上 + 标题在下，整体居中（自绘委托）
        self.nav = QListWidget()
        for text, icon_name in NAV_ITEMS:
            item = QListWidgetItem(icon(icon_name), text)
            item.setSizeHint(QSize(104, 80))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.nav.addItem(item)
        self.nav.setItemDelegate(_NavDelegate(self.nav))
        self.nav.setIconSize(QSize(30, 30))
        self.nav.setFixedWidth(116)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setFocusPolicy(Qt.NoFocus)  # 去掉点击后的焦点框
        self.nav.setStyleSheet(_NAV_STYLE)
        self.nav.currentRowChanged.connect(self.pages_set_index)
        root.addWidget(self.nav)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 顶栏：设置 / 帮助 / 关于 置于右上
        top = QHBoxLayout()
        top.setContentsMargins(12, 8, 12, 8)
        top.addStretch(1)
        for label, icon_name in _TOP_ACTIONS:
            btn = QPushButton(label)
            btn.setObjectName("flat")
            btn.setIcon(icon(icon_name))
            btn.clicked.connect(self._on_top_action)
            top.addWidget(btn)
        right_layout.addLayout(top)

        self.pages = QStackedWidget()
        self.pages.addWidget(HomePage(controller, self.nav.setCurrentRow))
        self.pages.addWidget(TaskPage(controller))
        self.pages.addWidget(RunPage(controller))
        self.pages.addWidget(ConnectionPage(controller))
        self.pages.addWidget(LogPage(controller))
        self.pages.addWidget(SettingsPage(controller))
        right_layout.addWidget(self.pages)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        # 初始/最小尺寸：避免被页面 sizeHint 撞开
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)

        # 状态栏：就绪状态 + 图标点缀的用户/控制库/版权分组，竖线分隔避免拥挤
        status = QStatusBar()
        ready = QLabel("● 就绪")
        ready.setStyleSheet(
            "color:#16a34a; background:#eafaf0; border:1px solid #bbe5c8; "
            "border-radius:5px; padding:2px 10px; font-weight:600;")
        status.addWidget(ready)
        self.setStatusBar(status)
        status.addPermanentWidget(_status_sep())
        status.addPermanentWidget(_status_item("user", f"当前用户：{getpass.getuser()}"))
        status.addPermanentWidget(_status_sep())
        status.addPermanentWidget(_status_item("database", controller.db.path.name))
        status.addPermanentWidget(_status_sep())
        status.addPermanentWidget(_status_item("info", "© xcode.im", "#8a94a0"))

        # 默认落在首页仪表盘
        self.nav.setCurrentRow(0)

    def pages_set_index(self, row: int) -> None:
        self.pages.setCurrentIndex(row)

    def _on_top_action(self) -> None:
        label = self.sender().text()
        if label == "设置":
            self.nav.setCurrentRow(5)
        elif label == "帮助":
            QDesktopServices.openUrl(QUrl(GITHUB_URL))
        elif label == "关于":
            AboutDialog(self).exec()

    @staticmethod
    def _placeholder(title: str, note: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addStretch(1)
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-size:20px; font-weight:600;")
        layout.addWidget(heading)
        body = QLabel(note)
        body.setAlignment(Qt.AlignCenter)
        body.setStyleSheet("color:#8a94a0;")
        layout.addWidget(body)
        layout.addStretch(1)
        return w
