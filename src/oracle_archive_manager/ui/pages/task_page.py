"""任务管理页：卡片式任务 CRUD + 级联元数据选择 + Analyze/Dry Run，见 06 §3.2/3.3。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, QTime, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ...domain.task import ArchiveTask, VerifyMode
from ...services import reports
from ...services.analyze_service import AnalyzeReport
from ...utils.time import to_local
from ..icons import icon
from ..labels import VERIFY_ZH, status_zh
from ..widgets import card

_REPORT_STYLE = (
    "QTextEdit { background:#fbfcfe; border:1px solid #e8edf3; border-radius:8px; "
    "font-family:Consolas,'Microsoft YaHei',monospace; font-size:12px; }"
)


class _AnalyzeWorker(QThread):
    """后台执行 Dry Run，避免 COUNT(*) 阻塞 UI。"""

    finished = Signal(object, object)

    def __init__(self, controller: AppController, task: ArchiveTask, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.task = task

    def run(self) -> None:
        try:
            self.finished.emit(self.controller.analyze_task(self.task), None)
        except Exception as exc:  # 元数据/连接类错误统一在报告区展示
            self.finished.emit(None, str(exc))


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GB"


class TaskPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._editing_id: int | None = None
        self._worker: _AnalyzeWorker | None = None
        self._loading = False
        self._sig: tuple = ()

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---- 左：任务列表卡片 ----
        left_frame, left_body, self.btn_new = card("任务列表", "新建任务", "plus")
        self.btn_new.setObjectName("primary")
        self.btn_new.setIcon(icon("plus", "#ffffff"))
        self.btn_new.clicked.connect(self._on_new)
        self.list = QListWidget()
        self.list.setObjectName("tasklist")
        self.list.currentRowChanged.connect(self._on_select)
        left_body.addWidget(self.list, 1)
        self.btn_toggle = QPushButton("禁用任务")
        self.btn_toggle.setIcon(icon("toggle"))
        self.btn_toggle.clicked.connect(self._on_toggle)
        left_body.addWidget(self.btn_toggle)
        left_frame.setFixedWidth(360)
        root.addWidget(left_frame)

        # ---- 右：Tabs ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_form_tab(), "归档设置")
        self.tabs.addTab(self._build_history_tab(), "运行历史")
        self.tabs.addTab(self._build_schedule_tab(), "调度设置")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        # ---- 信号 ----
        self.cb_src_conn.currentIndexChanged.connect(lambda _: self._fill_schemas("src"))
        self.cb_src_conn.activated.connect(lambda _: self._fill_schemas("src"))
        self.cb_src_schema.currentTextChanged.connect(lambda _: self._fill_tables("src"))
        self.cb_src_table.currentTextChanged.connect(self._on_src_table)
        self.cb_tgt_conn.currentIndexChanged.connect(lambda _: self._fill_schemas("tgt"))
        self.cb_tgt_conn.activated.connect(lambda _: self._fill_schemas("tgt"))
        self.cb_tgt_schema.currentTextChanged.connect(lambda _: self._fill_tables("tgt"))
        self.btn_save.clicked.connect(self._on_save)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_export_report.clicked.connect(self._on_export_report)

        self._reload_connections()
        self.refresh()

    # ---- 右侧 Tabs 构建 ----
    def _build_form_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        form_frame, form_body, _ = card("归档设置")
        grid = QGridLayout()
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        self.ed_name = QLineEdit()
        self.cb_src_conn = QComboBox()
        self.cb_src_schema = QComboBox()
        self.cb_src_schema.setEditable(True)
        self.cb_src_table = QComboBox()
        self.cb_src_table.setEditable(True)
        self.cb_tgt_conn = QComboBox()
        self.cb_tgt_schema = QComboBox()
        self.cb_tgt_schema.setEditable(True)
        self.cb_tgt_table = QComboBox()
        self.cb_tgt_table.setEditable(True)
        self.cb_column = QComboBox()
        self.cb_column.setEditable(True)
        self.cb_column.setPlaceholderText("可选；留空 = 按附加 WHERE 或全表归档")
        self.sp_months = QSpinBox()
        self.sp_months.setRange(1, 1200)
        self.sp_months.setValue(24)
        self.ed_where = QLineEdit()
        self.ed_keys = QLineEdit()
        self.ed_keys.setPlaceholderText("逗号分隔；默认取主键")
        self.sp_batch = QSpinBox()
        self.sp_batch.setRange(1000, 50000)
        self.sp_batch.setSingleStep(1000)
        self.sp_batch.setValue(5000)
        self.cb_verify = QComboBox()
        for m in VerifyMode:
            self.cb_verify.addItem(VERIFY_ZH[m.value], m.value)
        self.chk_create_target = QCheckBox("如果不存在则创建目标表")
        self.chk_allow_purge = QCheckBox("允许清理源数据（验证通过后可人工执行）")
        self.chk_allow_purge.setChecked(True)
        self.chk_allow_purge.setToolTip(
            "取消勾选后，该任务的所有运行均禁止清理（删除源数据），"
            "适用于测试表、需保留源表的场景。设置保存在运行快照中，立即生效")

        def add_field(row: int, col: int, label: str, field: QWidget) -> None:
            k = QLabel(label)
            k.setObjectName("muted")
            grid.addWidget(k, row, col, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(field, row, col + 1)

        add_field(0, 0, "任务名称", self.ed_name)
        add_field(0, 2, "校验方式", self.cb_verify)
        add_field(1, 0, "源连接", self.cb_src_conn)
        add_field(1, 2, "目标连接", self.cb_tgt_conn)
        add_field(2, 0, "源模式", self.cb_src_schema)
        add_field(2, 2, "目标模式", self.cb_tgt_schema)
        add_field(3, 0, "源表", self.cb_src_table)
        add_field(3, 2, "目标表", self.cb_tgt_table)
        add_field(4, 0, "归档日期字段", self.cb_column)
        add_field(4, 2, "保留月份", self.sp_months)
        add_field(5, 0, "附加条件", self.ed_where)
        add_field(5, 2, "键列", self.ed_keys)
        add_field(6, 0, "批次大小", self.sp_batch)
        grid.addWidget(self.chk_create_target, 6, 3)
        grid.addWidget(self.chk_allow_purge, 7, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        form_body.addLayout(grid)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")
        self.btn_save.setIcon(icon("save", "#ffffff"))
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setIcon(icon("trash-red"))
        self.btn_analyze = QPushButton("分析（试运行）")
        self.btn_analyze.setIcon(icon("analyze"))
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_delete)
        btns.addWidget(self.btn_analyze)
        btns.addStretch(1)
        form_body.addLayout(btns)
        lay.addWidget(form_frame)

        report_frame, report_body, self.btn_export_report = card(
            "分析报告", "导出报告", "save")
        self._analyze_task: ArchiveTask | None = None
        self._analyze_report: AnalyzeReport | None = None
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setStyleSheet(_REPORT_STYLE)
        report_body.addWidget(self.report, 1)
        lay.addWidget(report_frame, 1)
        return w

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        frame, body, btn = card("运行历史", "刷新", "refresh")
        btn.clicked.connect(self._reload_history)
        self.tbl_hist = QTableWidget()
        self.tbl_hist.setColumnCount(7)
        self.tbl_hist.setHorizontalHeaderLabels(
            ["运行 ID", "状态", "已传输/预期", "已验证", "已删除", "开始时间", "结束时间"]
        )
        self.tbl_hist.horizontalHeader().setMinimumSectionSize(48)
        self.tbl_hist.verticalHeader().setVisible(False)
        body.addWidget(self.tbl_hist, 1)
        lay.addWidget(frame)
        return w

    def _build_schedule_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        frame, body, _ = card("调度设置")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.chk_schedule = QCheckBox("启用每日定时运行")
        self.chk_schedule.setStyleSheet("font-weight:600;")
        row.addWidget(self.chk_schedule)
        row.addSpacing(12)
        row.addWidget(QLabel("触发时间"))
        self.te_schedule = QTimeEdit()
        self.te_schedule.setDisplayFormat("HH:mm")
        self.te_schedule.setTime(QTime(2, 0))
        row.addWidget(self.te_schedule)
        row.addStretch(1)
        body.addLayout(row)
        hint = QLabel(
            "程序运行中到达指定时间时自动创建并启动运行（每日一次，不补跑）；"
            "若任务已有活动运行或连接异常，本次自动跳过并记入日志。"
            "保存任务后生效。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        body.addWidget(hint)
        lay.addWidget(frame)
        lay.addStretch(1)
        return w

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._reload_history()

    def _reload_history(self) -> None:
        runs = (self.controller.list_runs(self._editing_id)
                if self._editing_id else [])
        self.tbl_hist.setRowCount(len(runs))
        for i, r in enumerate(runs):
            vals = [
                r.run_id, status_zh(r.status.value),
                f"{r.transferred_rows:,} / {r.expected_rows:,}",
                f"{r.verified_rows:,}", f"{r.deleted_rows:,}",
                to_local(r.start_time), to_local(r.end_time),
            ]
            for j, v in enumerate(vals):
                self.tbl_hist.setItem(i, j, QTableWidgetItem(v))

    # ---- 视图刷新 ----
    def refresh(self) -> None:
        tasks = self.controller.list_tasks()
        sig = tuple((t.id, t.task_name, t.source_table, t.target_table, t.enabled)
                    for t in tasks)
        if sig == self._sig:
            return
        self._sig = sig
        self.list.blockSignals(True)
        self.list.clear()
        for t in tasks:
            item = QListWidgetItem()
            w = QFrame()
            w.setObjectName("listitem")
            w.setProperty("selected", t.id == self._editing_id)
            w.setMinimumHeight(60)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(10, 6, 10, 6)
            lay.setSpacing(4)
            top = QHBoxLayout()
            name = QLabel(t.task_name)
            name.setStyleSheet("font-weight:600;")
            top.addWidget(name)
            top.addStretch(1)
            badge = QLabel("启用" if t.enabled else "禁用")
            badge.setObjectName("badge_on" if t.enabled else "badge_off")
            top.addWidget(badge)
            lay.addLayout(top)
            lay.addWidget(QLabel(f"{t.source_table} → {t.target_table}"))
            item.setData(Qt.UserRole, t.id)
            item.setSizeHint(QSize(0, 64))
            self.list.addItem(item)
            self.list.setItemWidget(item, w)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == self._editing_id:
                self.list.setCurrentRow(i)
                break
        self.list.blockSignals(False)

    def _reload_connections(self) -> None:
        for cb in (self.cb_src_conn, self.cb_tgt_conn):
            cb.clear()
            for c in self.controller.list_connections():
                cb.addItem(f"{c.name} [{c.role.value}]", c.id)

    def _fill_combo(self, cb: QComboBox, items: list[str], current: str = "") -> None:
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(items)
        if current:
            cb.setCurrentText(current)
        cb.blockSignals(False)

    def _fill_schemas(self, side: str) -> None:
        cb_conn = self.cb_src_conn if side == "src" else self.cb_tgt_conn
        cb_schema = self.cb_src_schema if side == "src" else self.cb_tgt_schema
        conn_id = cb_conn.currentData()
        if conn_id is None:
            return
        try:
            self._fill_combo(cb_schema, self.controller.list_schemas(conn_id))
        except Exception as exc:
            self.report.setPlainText(f"获取 Schema 失败：{exc}")

    def _fill_tables(self, side: str) -> None:
        if self._loading:
            return
        self._load_tables(side)

    def _load_tables(self, side: str) -> None:
        cb_conn = self.cb_src_conn if side == "src" else self.cb_tgt_conn
        cb_schema = self.cb_src_schema if side == "src" else self.cb_tgt_schema
        cb_table = self.cb_src_table if side == "src" else self.cb_tgt_table
        conn_id = cb_conn.currentData()
        schema = cb_schema.currentText().strip()
        if conn_id is None or not schema:
            return
        try:
            self._fill_combo(cb_table, self.controller.list_tables(conn_id, schema))
        except Exception as exc:
            self.report.setPlainText(f"获取表失败：{exc}")

    def _on_src_table(self, table: str) -> None:
        if self._loading or not table.strip():
            return
        conn_id = self.cb_src_conn.currentData()
        schema = self.cb_src_schema.currentText().strip()
        if conn_id is None or not schema:
            return
        try:
            cols = self.controller.list_columns(conn_id, schema, table)
            self._fill_combo(self.cb_column, cols)
            pk = self.controller.primary_key_columns(conn_id, schema, table)
            if pk and not self.ed_keys.text().strip():
                self.ed_keys.setText(",".join(pk))
            # 自动建议目标同名表（09 Task）
            self.cb_tgt_table.blockSignals(True)
            if not self.cb_tgt_table.currentText().strip():
                self.cb_tgt_table.setCurrentText(table)
            self.cb_tgt_table.blockSignals(False)
        except Exception as exc:
            self.report.setPlainText(f"获取列失败：{exc}")

    # ---- 表单 ↔ 模型 ----
    def _collect(self) -> ArchiveTask:
        src_id = self.cb_src_conn.currentData()
        tgt_id = self.cb_tgt_conn.currentData()
        if src_id is None or tgt_id is None:
            raise ValueError("请先在“连接管理”创建连接")
        keys = [k.strip().upper() for k in self.ed_keys.text().split(",") if k.strip()]
        return ArchiveTask(
            id=self._editing_id,
            task_name=self.ed_name.text().strip() or f"{self.cb_src_table.currentText()}_归档任务",
            source_connection_id=src_id,
            source_schema=self.cb_src_schema.currentText().strip().upper(),
            source_table=self.cb_src_table.currentText().strip().upper(),
            target_connection_id=tgt_id,
            target_schema=self.cb_tgt_schema.currentText().strip().upper()
            or self.cb_src_schema.currentText().strip().upper(),
            target_table=self.cb_tgt_table.currentText().strip().upper()
            or self.cb_src_table.currentText().strip().upper(),
            archive_column=self.cb_column.currentText().strip().upper() or None,
            keep_months=self.sp_months.value(),
            extra_where=self.ed_where.text().strip() or None,
            key_columns=keys,
            batch_size=self.sp_batch.value(),
            verify_mode=VerifyMode(self.cb_verify.currentData()),
            allow_purge=self.chk_allow_purge.isChecked(),
            schedule_enabled=self.chk_schedule.isChecked(),
            schedule_time=self.te_schedule.time().toString("HH:mm"),
            create_target_if_missing=self.chk_create_target.isChecked(),
            enabled=(self.controller.tasks.get(self._editing_id).enabled
                     if self._editing_id else True),
        )

    def _on_select(self, row: int) -> None:
        item = self.list.item(row)
        if item is None:
            return
        task_id = item.data(Qt.UserRole)
        t = next((x for x in self.controller.list_tasks() if x.id == task_id), None)
        if t is None:
            return
        self._loading = True
        try:
            self._editing_id = t.id
            self.ed_name.setText(t.task_name)
            self.cb_src_conn.setCurrentIndex(self.cb_src_conn.findData(t.source_connection_id))
            self.cb_tgt_conn.setCurrentIndex(self.cb_tgt_conn.findData(t.target_connection_id))
            self._fill_schemas("src")
            self._fill_schemas("tgt")
            # 保留完整下拉列表，仅定位当前值（不收窄为单项）
            self.cb_src_schema.setCurrentText(t.source_schema)
            self.cb_tgt_schema.setCurrentText(t.target_schema)
            self._load_tables("src")
            self._load_tables("tgt")
            self.cb_src_table.setCurrentText(t.source_table)
            self.cb_tgt_table.setCurrentText(t.target_table)
            self._on_src_table(t.source_table)
            self.cb_column.setCurrentText(t.archive_column or "")
            self.sp_months.setValue(t.keep_months)
            self.ed_where.setText(t.extra_where or "")
            self.ed_keys.setText(",".join(t.key_columns))
            self.sp_batch.setValue(t.batch_size)
            self.cb_verify.setCurrentIndex(self.cb_verify.findData(t.verify_mode.value))
            self.chk_create_target.setChecked(t.create_target_if_missing)
            self.chk_allow_purge.setChecked(t.allow_purge)
            self.chk_schedule.setChecked(t.schedule_enabled)
            self.te_schedule.setTime(QTime.fromString(t.schedule_time, "HH:mm"))
            self.btn_toggle.setText("启用任务" if not t.enabled else "禁用任务")
        finally:
            self._loading = False
        self._sig = ()
        self.refresh()
        self._reload_history()

    def _on_new(self) -> None:
        self._editing_id = None
        self._loading = True
        try:
            self.list.clearSelection()
            self.ed_name.clear()
            self.ed_where.clear()
            self.ed_keys.clear()
            for cb in (self.cb_src_schema, self.cb_src_table, self.cb_tgt_schema,
                       self.cb_tgt_table, self.cb_column):
                cb.clear()
            self.sp_months.setValue(24)
            self.sp_batch.setValue(5000)
            self.chk_allow_purge.setChecked(True)
            self.chk_schedule.setChecked(False)
            self.te_schedule.setTime(QTime(2, 0))
            self.btn_toggle.setText("禁用任务")
        finally:
            self._loading = False
        # 新建时立即填充 Schema 下拉（清空后不能依赖 currentIndexChanged）
        self._fill_schemas("src")
        self._fill_schemas("tgt")
        self.cb_src_schema.setCurrentIndex(-1)
        self.cb_tgt_schema.setCurrentIndex(-1)
        self._sig = ()
        self.refresh()

    # ---- 动作 ----
    def _on_save(self) -> None:
        try:
            t = self._collect()
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        try:
            self.controller.save_task(t)
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._sig = ()
        self.refresh()

    def _on_delete(self) -> None:
        if self._editing_id is None:
            return
        if QMessageBox.question(self, "删除任务", "删除该归档任务？") != QMessageBox.Yes:
            return
        self.controller.delete_task(self._editing_id)
        self._editing_id = None
        self._sig = ()
        self.refresh()

    def _on_toggle(self) -> None:
        if self._editing_id is None:
            return
        try:
            t = self.controller.toggle_task_enabled(self._editing_id)
        except Exception as exc:
            QMessageBox.warning(self, "操作失败", str(exc))
            return
        self.btn_toggle.setText("启用任务" if not t.enabled else "禁用任务")
        self._sig = ()
        self.refresh()
        row = next((i for i, x in enumerate(self.controller.list_tasks())
                    if x.id == self._editing_id), -1)
        if row >= 0:
            self.list.setCurrentRow(row)

    def _on_analyze(self) -> None:
        try:
            t = self._collect()
        except Exception as exc:
            QMessageBox.warning(self, "分析失败", str(exc))
            return
        self.report.setPlainText("分析中…")
        self._analyze_task = t
        self._worker = _AnalyzeWorker(self.controller, t)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.start()

    def _on_analyze_done(self, rep: AnalyzeReport | None, error) -> None:
        if rep is None:
            self._analyze_report = None
            self.report.setPlainText(f"分析失败：{error}")
            return
        self._analyze_report = rep
        lines = [
            f"{self.cb_src_table.currentText()}",
            "",
            f"Source Rows        {rep.source_rows:,}",
            f"Archive Eligible   {rep.eligible_rows:,}",
            f"Cutoff             {rep.cutoff}",
            f"Condition          {rep.archive_condition}",
            f"Source Size        {_gb(rep.source_bytes)}",
            f"Index Size         {_gb(rep.index_bytes)}",
            f"Target Exists      {'YES' if rep.target_exists else 'NO'}",
            f"Schema Match       {'PASS' if rep.schema_match else 'FAIL'}",
            f"Primary Key        {', '.join(rep.primary_key) or '-'}",
            f"Unique Keys        {', '.join(rep.unique_keys) or '-'}",
            f"Estimated Batches  {rep.estimated_batches}",
            f"Estimated Time     ~{rep.estimated_seconds // 60} 分钟",
        ]
        if rep.mismatches:
            lines += ["", "结构差异："] + [f"  - {m}" for m in rep.mismatches]
        if rep.risks:
            lines += ["", "风险提醒："] + [f"  ! {r}" for r in rep.risks]
        self.report.setPlainText("\n".join(lines))

    def _on_export_report(self) -> None:
        """P1：Analyze Report 导出为 Markdown。"""
        if self._analyze_report is None or self._analyze_task is None:
            QMessageBox.information(self, "导出报告", "请先执行“分析（Dry Run）”")
            return
        from datetime import date
        from pathlib import Path

        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Analyze Report",
            f"analyze_{self._analyze_task.source_table}_{date.today().isoformat()}.md",
            "Markdown (*.md)")
        if not path:
            return
        Path(path).write_text(
            reports.analyze_report_md(self._analyze_task, self._analyze_report),
            encoding="utf-8")
        QMessageBox.information(self, "导出报告", f"已导出：{path}")
