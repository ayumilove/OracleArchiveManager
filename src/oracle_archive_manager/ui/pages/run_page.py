"""运行管理页：卡片式 Run 列表 + 五步 Stepper 详情 + 批次表 + 日志，见 06 §3.3。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ...domain.run import RunStatus
from ...domain.task import ArchiveTask
from ...services import reports
from ...utils.time import to_local
from ..icons import icon
from ..labels import level_zh, stage_zh, status_zh
from ..widgets import Stepper, apply_pill, card
from .purge_dialog import PurgePreviewDialog

_LOG_STYLE = (
    "QTextEdit { background:#fbfcfe; border:1px solid #e8edf3; border-radius:8px; "
    "font-family:Consolas,'Microsoft YaHei',monospace; font-size:12px; }"
)


def _pill(status: str) -> QLabel:
    lbl = QLabel(status_zh(status))
    apply_pill(lbl, status)
    return lbl


def _elapsed(start: str | None, end: str | None) -> str:
    if not start:
        return "—"
    from datetime import datetime

    fmt = "%Y-%m-%dT%H:%M:%S"
    try:
        s = datetime.fromisoformat(start[:19])
        e = datetime.fromisoformat(end[:19]) if end else datetime.now()
        sec = int((e - s).total_seconds())
        return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    except ValueError:
        return "—"


class RunPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._current_run: str | None = None
        self._run = None
        self._batches: list = []
        self._sig: tuple = ()

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---- 左：Run 列表卡片 ----
        left_frame, left_body, self.btn_start = card("运行列表", "启动运行", "play")
        self.btn_start.setObjectName("primary")
        self.btn_start.setIcon(icon("play", "#ffffff"))

        pick = QHBoxLayout()
        pick.setSpacing(8)
        k = QLabel("任务")
        k.setObjectName("muted")
        self.cb_task = QComboBox()
        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(icon("refresh"))
        self.btn_refresh.setObjectName("flat")
        self.btn_refresh.setToolTip("刷新")
        pick.addWidget(k)
        pick.addWidget(self.cb_task, 1)
        pick.addWidget(self.btn_refresh)
        left_body.addLayout(pick)

        self.list = QListWidget()
        self.list.setObjectName("tasklist")
        self.list.currentRowChanged.connect(self._on_select)
        left_body.addWidget(self.list, 1)
        left_frame.setFixedWidth(400)
        root.addWidget(left_frame)

        # ---- 右：Run 详情卡片 ----
        right_frame, right_body, _ = card("运行详情")

        head = QHBoxLayout()
        head.setSpacing(10)
        self.lbl_run = QLabel("未选择运行")
        self.lbl_run.setObjectName("card_title")
        self.lbl_pill = QLabel("")
        self.lbl_pill.hide()
        head.addWidget(self.lbl_run)
        head.addWidget(self.lbl_pill)
        head.addStretch(1)
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setIcon(icon("pause"))
        self.btn_pause.setToolTip("当前批次复制完成后暂停；大数据量批次可能耗时较长")
        self.btn_resume = QPushButton("继续")
        self.btn_resume.setIcon(icon("play"))
        self.btn_cancel = QPushButton("安全停止")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setIcon(icon("stop"))
        self.btn_complete = QPushButton("完结（无需清理）")
        self.btn_complete.setIcon(icon("toggle"))
        self.btn_complete.setToolTip(
            "校验已通过且不再清理源数据时，人工完结该运行，释放任务的再运行名额")
        self.btn_export = QPushButton("导出运行报告")
        self.btn_export.setIcon(icon("save"))
        self.btn_export.setEnabled(False)
        self.btn_purge = QPushButton("清理预览…")
        self.btn_purge.setObjectName("danger")
        self.btn_purge.setIcon(icon("trash-red"))
        for b in (self.btn_pause, self.btn_resume, self.btn_cancel,
                  self.btn_complete, self.btn_export, self.btn_purge):
            head.addWidget(b)
        right_body.addLayout(head)

        self.stepper = Stepper()
        self.stepper.setMaximumHeight(150)
        right_body.addWidget(self.stepper)

        metrics = QGridLayout()
        metrics.setContentsMargins(4, 4, 4, 4)
        metrics.setHorizontalSpacing(16)
        metrics.setVerticalSpacing(8)

        def add_metric(row: int, col: int, key: str, color: str = "") -> QLabel:
            k = QLabel(key)
            k.setObjectName("muted")
            v = QLabel("—")
            v.setStyleSheet(f"color:{color or '#1f2937'}; font-weight:600;")
            metrics.addWidget(k, row, col)
            metrics.addWidget(v, row, col + 1)
            return v

        self.v_expected = add_metric(0, 0, "预期行数")
        self.v_copied = add_metric(0, 2, "已复制", "#2563eb")
        self.v_verified = add_metric(1, 0, "已验证", "#16a34a")
        self.v_batches = add_metric(1, 2, "批次")
        self.v_cutoff = add_metric(2, 0, "截止时间")
        self.v_elapsed = add_metric(2, 2, "耗时")
        self.v_start = add_metric(3, 0, "开始时间")
        self.v_end = add_metric(3, 2, "结束时间")
        metrics.setColumnStretch(1, 1)
        metrics.setColumnStretch(3, 1)
        right_body.addLayout(metrics)

        t1 = QLabel("批次列表（双击查看错误详情）")
        t1.setObjectName("muted")
        right_body.addWidget(t1)
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(7)
        self.tbl.setHorizontalHeaderLabels(
            ["批次", "状态", "选中", "已复制", "已验证", "错误", "开始时间"]
        )
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.horizontalHeader().setMinimumSectionSize(48)
        self.tbl.setMinimumWidth(520)
        self.tbl.setMinimumHeight(180)
        right_body.addWidget(self.tbl, 3)

        t2 = QLabel("运行日志")
        t2.setObjectName("muted")
        right_body.addWidget(t2)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(_LOG_STYLE)
        self.log.setMinimumHeight(140)
        right_body.addWidget(self.log, 2)
        root.addWidget(right_frame, 1)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_resume.clicked.connect(self._on_resume)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_purge.clicked.connect(self._on_purge)
        self.btn_complete.clicked.connect(self._on_complete)
        self.btn_export.clicked.connect(self._on_export_report)
        self.tbl.cellDoubleClicked.connect(self._on_batch_dblclick)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(2000)

        self.refresh()

    # ---- 刷新 ----
    def refresh(self) -> None:
        self.cb_task.blockSignals(True)
        cur = self.cb_task.currentData()
        self.cb_task.clear()
        for t in self.controller.list_tasks():
            self.cb_task.addItem(t.task_name, t.id)
        if cur is not None:
            idx = self.cb_task.findData(cur)
            if idx >= 0:
                self.cb_task.setCurrentIndex(idx)
        self.cb_task.blockSignals(False)
        self._reload_runs()
        self._reload_detail()

    def _tick(self) -> None:
        if self.isVisible():
            self._reload_runs()
            self._reload_detail()

    def _reload_runs(self) -> None:
        task_id = self.cb_task.currentData()
        runs = self.controller.list_runs(task_id)
        sig = tuple(
            (r.run_id, r.status.value, r.transferred_rows, r.expected_rows,
             r.success_batches, r.failed_batches)
            for r in runs
        )
        if sig == self._sig:
            return
        self._sig = sig
        self.list.blockSignals(True)
        self.list.clear()
        for r in runs:
            item = QListWidgetItem()
            w = QFrame()
            w.setObjectName("listitem")
            w.setProperty("selected", r.run_id == self._current_run)
            w.setMinimumHeight(60)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(10, 6, 10, 6)
            lay.setSpacing(4)
            top = QHBoxLayout()
            rid = QLabel(r.run_id)
            rid.setStyleSheet("font-weight:600;")
            top.addWidget(rid)
            top.addStretch(1)
            top.addWidget(_pill(r.status.value))
            lay.addLayout(top)
            lay.addWidget(QLabel(
                f"行数 {r.transferred_rows}/{r.expected_rows}　"
                f"批次 {r.success_batches + r.failed_batches}/{r.total_batches}　"
                f"{to_local(r.start_time)}"
            ))
            item.setData(Qt.UserRole, r.run_id)
            item.setSizeHint(QSize(0, 66))
            self.list.addItem(item)
            self.list.setItemWidget(item, w)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == self._current_run:
                self.list.setCurrentRow(i)
                break
        self.list.blockSignals(False)

    def _on_select(self, row: int) -> None:
        item = self.list.item(row)
        if item is None:
            return
        self._current_run = item.data(Qt.UserRole)
        self._sig = ()
        self._reload_runs()
        self._reload_detail()

    def _stepper_states(self, r) -> list[tuple[str, str]]:
        s = r.status
        failed = s is RunStatus.FAILED
        copy_done = r.copy_end_time is not None
        verify_done = s in (RunStatus.VERIFIED, RunStatus.COMPLETED) or (
            copy_done and r.transferred_rows > 0 and r.verified_rows >= r.transferred_rows
        )
        purge_done = s is RunStatus.COMPLETED
        states: list[tuple[str, str]] = [("done", "结构/行数分析")]
        if copy_done:
            states.append(("done", f"{r.transferred_rows} 行"))
        elif s in (RunStatus.RUNNING, RunStatus.PAUSING):
            states.append(("active", "复制中…"))
        elif failed:
            states.append(("fail", "失败"))
        else:
            states.append(("pending", ""))
        if verify_done:
            states.append(("done", f"{r.verified_rows} 行"))
        elif s is RunStatus.RUNNING and copy_done:
            states.append(("active", "校验中…"))
        elif failed and copy_done:
            states.append(("fail", "失败"))
        else:
            states.append(("pending", ""))
        if purge_done:
            states.append(("done", "已确认清理"))
        elif s is RunStatus.VERIFIED:
            states.append(("active", "待人工确认"))
        elif failed and verify_done:
            states.append(("pending", "未执行"))
        else:
            states.append(("pending", ""))
        if purge_done:
            states.append(("done", f"删除 {r.deleted_rows} 行"))
        elif failed:
            states.append(("pending", "未执行"))
        else:
            states.append(("pending", ""))
        return states

    def _reload_detail(self) -> None:
        if self._current_run is None:
            return
        r, batches = self.controller.run_detail(self._current_run)
        if r is None:
            return
        self._run = r
        self._batches = batches

        self.lbl_run.setText(f"运行 {r.run_id}")
        self.lbl_pill.setText(status_zh(r.status.value))
        apply_pill(self.lbl_pill, r.status.value)
        self.lbl_pill.show()

        self.stepper.set_state(self._stepper_states(r))

        self.v_expected.setText(str(r.expected_rows))
        self.v_copied.setText(str(r.transferred_rows))
        self.v_verified.setText(str(r.verified_rows))
        self.v_batches.setText(
            f"{r.success_batches + r.failed_batches}/{r.total_batches}"
            f"（失败 {r.failed_batches}）"
        )
        self.v_cutoff.setText(r.cutoff_value or "无")
        self.v_start.setText(to_local(r.start_time) or "—")
        self.v_end.setText(to_local(r.end_time) or "—")
        self.v_elapsed.setText(_elapsed(r.start_time, r.end_time))
        if r.error_message:
            self.v_end.setText(f"{to_local(r.end_time) or '—'}　错误：{r.error_message}")
            self.v_end.setStyleSheet("color:#dc2626;")
        else:
            self.v_end.setStyleSheet("")

        self.btn_pause.setEnabled(r.status in (RunStatus.RUNNING, RunStatus.PAUSING)
                                  and self.controller.has_worker(r.run_id))
        orphan = (r.status in (RunStatus.PAUSING, RunStatus.RUNNING)
                  and not self.controller.has_worker(r.run_id))
        self.btn_resume.setEnabled(r.status in (RunStatus.PAUSED, RunStatus.FAILED) or orphan)
        self.btn_cancel.setEnabled(r.status in (RunStatus.PAUSED, RunStatus.FAILED) or orphan)
        allow_purge = bool((r.task_snapshot or {}).get("allow_purge", True))
        self.btn_purge.setEnabled(r.status is RunStatus.VERIFIED and allow_purge)
        self.btn_purge.setToolTip(
            "" if allow_purge else "该任务配置为禁止清理源数据；"
            "如需清理请在任务设置中开启允许后重新运行")
        self.btn_complete.setEnabled(r.status is RunStatus.VERIFIED)
        self.btn_export.setEnabled(True)

        self.tbl.setRowCount(len(batches))
        for i, b in enumerate(batches):
            vals = [
                str(b.batch_no), status_zh(b.status.value), str(b.selected_rows),
                str(b.transferred_rows), str(b.verified_rows),
                b.error_message or "", to_local(b.start_time),
            ]
            for j, v in enumerate(vals):
                self.tbl.setItem(i, j, QTableWidgetItem(v))

        logs = self.controller.run_logs(self._current_run)
        self.log.setPlainText(
            "\n".join(f"{to_local(l['log_time'])}  {level_zh(l['level'])}  "
                      f"[{stage_zh(l['stage'])}] {l['message']}"
                      for l in reversed(logs))
        )

    # ---- 动作 ----
    def _on_start(self) -> None:
        task_id = self.cb_task.currentData()
        if task_id is None:
            QMessageBox.warning(self, "启动运行", "请先在任务管理页创建任务")
            return
        try:
            run_id = self.controller.start_run(task_id)
        except Exception as exc:
            QMessageBox.warning(self, "启动运行失败", str(exc))
            return
        self._current_run = run_id
        self._sig = ()
        self.refresh()

    def _on_pause(self) -> None:
        if self._current_run:
            self.controller.pause_run(self._current_run)
            self._reload_detail()

    def _on_resume(self) -> None:
        if not self._current_run:
            return
        try:
            self.controller.resume_run(self._current_run)
        except Exception as exc:
            QMessageBox.warning(self, "继续失败", str(exc))
            return
        self._reload_detail()

    def _on_purge(self) -> None:
        if not self._current_run:
            return
        try:
            dlg = PurgePreviewDialog(self.controller, self._current_run, self)
        except Exception as exc:
            QMessageBox.warning(self, "清理预览", str(exc))
            return
        dlg.exec()
        self._sig = ()
        self._reload_runs()
        self._reload_detail()

    def _on_complete(self) -> None:
        if not self._current_run:
            return
        if QMessageBox.question(
            self, "完结运行",
            "确认不再清理源数据并标记完结？"
            "完结后该任务可再次运行；已复制到归档库的数据保留。",
        ) != QMessageBox.Yes:
            return
        try:
            self.controller.complete_run(self._current_run)
        except Exception as exc:
            QMessageBox.warning(self, "完结运行", str(exc))
        self.refresh()

    def _on_export_report(self) -> None:
        """运行报告导出为 Markdown（含批次明细/日志/维护建议）。"""
        from pathlib import Path

        if not self._current_run:
            return
        r, batches = self.controller.run_detail(self._current_run)
        if r is None:
            return
        task = ArchiveTask(**r.task_snapshot)
        logs = self.controller.run_logs(r.run_id)
        path, _ = QFileDialog.getSaveFileName(
            self, "导出运行报告", f"run_{r.run_id}.md", "Markdown (*.md)")
        if not path:
            return
        Path(path).write_text(
            reports.run_report_md(r, batches, logs, task), encoding="utf-8")
        QMessageBox.information(self, "导出报告", f"已导出：{path}")

    def _on_cancel(self) -> None:
        if not self._current_run:
            return
        if QMessageBox.question(
            self, "安全停止",
            "取消该运行？已完成批次与目标库数据保留，可随时继续或另行处理。",
        ) != QMessageBox.Yes:
            return
        try:
            self.controller.cancel_run(self._current_run)
        except Exception as exc:
            QMessageBox.warning(self, "安全停止失败", str(exc))
            return
        self._sig = ()
        self._reload_runs()
        self._reload_detail()

    def _on_batch_dblclick(self, row: int, _col: int) -> None:
        """双击批次行查看错误明细。"""
        if not (0 <= row < len(self._batches)):
            return
        b = self._batches[row]
        run = self._run
        lines = [
            f"批次：{b.batch_id}",
            f"状态：{status_zh(b.status.value)}",
            f"选中/复制/验证行数：{b.selected_rows} / {b.transferred_rows} / {b.verified_rows}",
            f"选区快照：{b.selection_snapshot}",
            "",
            f"批次错误：{b.error_message or '无'}",
            f"运行错误：{(run.error_message if run else '') or '无'}",
        ]
        dlg = QDialog(self)
        dlg.setWindowTitle(f"错误详情 — {b.batch_id}")
        dlg.resize(640, 360)
        lay = QVBoxLayout(dlg)
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText("\n".join(lines))
        lay.addWidget(box)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.clicked.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()
