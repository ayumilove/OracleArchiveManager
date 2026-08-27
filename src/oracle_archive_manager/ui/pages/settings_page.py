"""系统设置页：卡片式全局开关与信息展示，风格对齐首页，见 06_GUI_DESIGN.md §2。"""
from __future__ import annotations

import getpass

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ..widgets import card, kv_grid


class SettingsPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(12)

        # ---- 运行设置 ----
        run_frame, run_body, _ = card("运行设置")
        self.chk_thick = QCheckBox("Thick Mode")
        self.chk_thick.setStyleSheet("font-weight:600;")
        self.chk_thick.setChecked(bool(controller.config.get("thick_mode")))
        self.chk_thick.toggled.connect(lambda v: controller.config.set("thick_mode", v))
        run_body.addWidget(self.chk_thick)
        hint = QLabel(
            "Oracle 11g 必需 Thick Mode；需本机安装 Oracle Client，切换后重启程序生效。"
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        run_body.addWidget(hint)
        col.addWidget(run_frame)

        # ---- 日志保留（P1）----
        log_frame, log_body, _ = card("日志保留")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("文件日志保留"))
        self.sp_file_days = QSpinBox()
        self.sp_file_days.setRange(1, 365)
        self.sp_file_days.setSuffix(" 天")
        self.sp_file_days.setValue(int(controller.config.get("log_retention_days")))
        self.sp_file_days.valueChanged.connect(
            lambda v: controller.config.set("log_retention_days", v))
        row.addWidget(self.sp_file_days)
        row.addSpacing(16)
        row.addWidget(QLabel("控制库日志保留"))
        self.sp_db_days = QSpinBox()
        self.sp_db_days.setRange(7, 3650)
        self.sp_db_days.setSuffix(" 天")
        self.sp_db_days.setValue(int(controller.config.get("db_log_retention_days")))
        self.sp_db_days.valueChanged.connect(
            lambda v: controller.config.set("db_log_retention_days", v))
        row.addWidget(self.sp_db_days)
        row.addStretch(1)
        log_body.addLayout(row)
        hint2 = QLabel(
            "文件日志轮转后自动 gzip 压缩；控制库日志在每次启动时自动清理超期记录。"
            "文件日志保留天数重启后生效。")
        hint2.setObjectName("muted")
        hint2.setWordWrap(True)
        log_body.addWidget(hint2)
        col.addWidget(log_frame)

        # ---- 控制库 ----
        db_frame, db_body, _ = card("控制库")
        _, kv = kv_grid()
        kv["add_row"]("数据库文件", str(controller.db.path))
        kv["add_row"]("当前用户", getpass.getuser())
        db_body.addWidget(_)
        col.addWidget(db_frame)

        # ---- 安全原则 ----
        safe_frame, safe_body, _ = card("安全原则")
        for line in (
            "复制是自动的，清理必须经显式确认。",
            "清理生产库必须经过清理预览双重人工确认。",
            "安全停止保留已复制批次与目标库数据，可随时继续。",
        ):
            lbl = QLabel(f"• {line}")
            lbl.setObjectName("muted")
            lbl.setWordWrap(True)
            safe_body.addWidget(lbl)
        col.addWidget(safe_frame)

        col.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(col)
        wrap.setMaximumWidth(760)
        root.addWidget(wrap)
        root.addStretch(1)
