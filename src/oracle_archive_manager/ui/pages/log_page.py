"""日志查看页：卡片式按 Run / 级别 / 阶段过滤归档审计日志，见 06 §3.6。"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ...utils.time import to_local
from ..icons import icon
from ..labels import level_zh, stage_zh
from ..widgets import card

LEVELS = ["", "INFO", "WARN", "ERROR"]
STAGES = ["", "RUN", "COPY", "VERIFY", "PURGE"]
LEVEL_COLOR = {"ERROR": "#dc2626", "WARN": "#d97706", "INFO": "#16a34a"}


class LogPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        frame, body, _ = card("日志查看")

        bar = QHBoxLayout()
        bar.setSpacing(8)
        k_run = QLabel("运行 ID")
        k_run.setObjectName("muted")
        self.ed_run = QLineEdit()
        self.ed_run.setPlaceholderText("留空 = 全部")
        k_level = QLabel("级别")
        k_level.setObjectName("muted")
        self.cb_level = QComboBox()
        for lv in LEVELS:
            self.cb_level.addItem(level_zh(lv) if lv else "全部", lv)
        k_stage = QLabel("阶段")
        k_stage.setObjectName("muted")
        self.cb_stage = QComboBox()
        for st in STAGES:
            self.cb_stage.addItem(stage_zh(st) if st else "全部", st)
        btn = QPushButton("查询")
        btn.setObjectName("primary")
        btn.setIcon(icon("analyze", "#ffffff"))
        btn.clicked.connect(self.refresh)
        bar.addWidget(k_run)
        bar.addWidget(self.ed_run, 1)
        bar.addWidget(k_level)
        bar.addWidget(self.cb_level)
        bar.addWidget(k_stage)
        bar.addWidget(self.cb_stage)
        bar.addWidget(btn)
        body.addLayout(bar)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["时间", "运行", "级别", "阶段", "内容"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setMinimumSectionSize(48)
        self.tbl.verticalHeader().setVisible(False)
        body.addWidget(self.tbl, 1)
        root.addWidget(frame, 1)

        self.refresh()

    def refresh(self) -> None:
        rows = self.controller.recent_logs(
            run_id=self.ed_run.text().strip() or None,
            level=self.cb_level.currentData() or None,
            stage=self.cb_stage.currentData() or None,
        )
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(reversed(rows)):  # 最新在上
            vals = [to_local(r["log_time"]), r["run_id"], level_zh(r["level"]),
                    stage_zh(r["stage"]), r["message"]]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if j == 2:  # 级别列按原始枚举值着色（展示已中文化）
                    color = LEVEL_COLOR.get(r["level"])
                    if color:
                        item.setForeground(QColor(color))
                    item.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(i, j, item)
