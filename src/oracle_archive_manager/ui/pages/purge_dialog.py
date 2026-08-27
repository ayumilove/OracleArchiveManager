"""清理预览独立窗口：批次预览 + 双确认（勾选 + 表名手输），见 04 §4 / 06。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...app.controller import AppController
from ..icons import icon
from ..labels import status_zh


class PurgePreviewDialog(QDialog):
    def __init__(self, controller: AppController, run_id: str, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.run_id = run_id
        preview = controller.purge_preview(run_id)
        task = preview["task"]
        batches = preview["batches"]

        self.setWindowTitle(f"清理预览 — {run_id}")
        self.resize(640, 480)
        layout = QVBoxLayout(self)

        warn = QLabel(
            "⚠ 本操作将从【生产库】删除以下已验证批次的数据，不可撤销。\n"
            "复制是自动的，清理必须经显式确认。"
        )
        warn.setStyleSheet("color:#c0392b; font-weight:600;")
        layout.addWidget(warn)

        info = QLabel(
            f"源：{task.source_schema}.{task.source_table}　"
            f"批次 {len(batches)} 个　共 {preview['total_rows']:,} 行"
        )
        layout.addWidget(info)

        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["批次", "状态", "已验证行数", "键区间"])
        tbl.setRowCount(len(batches))
        for i, b in enumerate(batches):
            snap = b.selection_snapshot or {}
            last = snap.get("last_keys")
            vals = [str(b.batch_no), status_zh(b.status.value), f"{b.verified_rows:,}",
                    f"… → {last}"]
            for j, v in enumerate(vals):
                tbl.setItem(i, j, QTableWidgetItem(v))
        layout.addWidget(tbl, 1)

        self.chk = QCheckBox("我知悉上述数据将从生产库删除且不可撤销")
        layout.addWidget(self.chk)

        row = QHBoxLayout()
        row.addWidget(QLabel("请输入源表名确认："))
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("手输源表名二次确认")
        row.addWidget(self.ed, 1)
        layout.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.btn_purge = QPushButton("删除源数据（清理）")
        self.btn_purge.setIcon(icon("trash-red"))
        self.btn_purge.setEnabled(False)
        self.btn_purge.setStyleSheet("background:#c0392b; color:white; font-weight:600;")
        btns.addButton(self.btn_purge, QDialogButtonBox.AcceptRole)
        btns.rejected.connect(self.reject)
        self.btn_purge.clicked.connect(self._on_confirm)
        layout.addWidget(btns)

        self.chk.toggled.connect(self._sync)
        self.ed.textChanged.connect(self._sync)
        self._target = task.source_table

    def _sync(self, *_args) -> None:
        self.btn_purge.setEnabled(
            self.chk.isChecked()
            and self.ed.text().strip().upper() == self._target.upper()
        )

    def _on_confirm(self) -> None:
        try:
            self.controller.start_purge(self.run_id, self.ed.text())
        except Exception as exc:
            QMessageBox.critical(self, "清理启动失败", str(exc))
            return
        self.accept()
