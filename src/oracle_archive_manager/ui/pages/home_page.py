"""首页仪表盘：连接概览 + 任务列表 + 任务详情 + 当前运行五步进度，见 06 §3.1。"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ...domain.run import RunStatus
from ...domain.task import ArchiveTask
from ...utils.time import to_local
from ..icons import icon
from ..labels import level_zh, stage_zh, status_zh
from ..widgets import Stepper, apply_pill, card, kv_grid
from .task_page import _AnalyzeWorker, _gb

ROLE_COLOR = {"SOURCE": "#16a34a", "TARGET": "#2563eb", "BOTH": "#7c3aed"}
ROLE_TEXT = {"SOURCE": "生产库", "TARGET": "归档库", "BOTH": "双角色"}


def _elapsed(start: str | None, end: str | None) -> str:
    if not start:
        return "—"
    try:
        t0 = datetime.fromisoformat(start)
        t1 = datetime.fromisoformat(end) if end else datetime.now(t0.tzinfo)
        s = int((t1 - t0).total_seconds())
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"
    except Exception:
        return "—"


class HomePage(QWidget):
    def __init__(self, controller: AppController,
                 navigate: Callable[[int], None] | None = None) -> None:
        super().__init__()
        self.controller = controller
        self.navigate = navigate or (lambda _row: None)
        self._task_id: int | None = None
        self._worker: _AnalyzeWorker | None = None
        self._task_sig: tuple = ()
        self._conn_sig: tuple = ()

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---- 左列：连接 + 任务列表 ----
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._build_conn_card())
        left.addWidget(self._build_task_card(), 1)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(330)
        root.addWidget(lw)

        # ---- 右列：任务详情 + 当前运行 ----
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._build_detail_card())
        right.addWidget(self._build_run_card(), 1)
        rw = QWidget()
        rw.setLayout(right)
        root.addWidget(rw, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    # ================= 构建 =================
    def _build_conn_card(self) -> QWidget:
        frame, body, btn = card("数据库连接", "新建", "plus")
        btn.clicked.connect(lambda: self.navigate(3))
        self.conn_box = QVBoxLayout()
        self.conn_box.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setLayout(self.conn_box)
        scroll.setWidget(inner)
        body.addWidget(scroll, 1)
        return frame

    def _build_task_card(self) -> QWidget:
        frame, body, btn = card("任务列表", "新建任务", "plus")
        btn.clicked.connect(lambda: self.navigate(1))
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("搜索任务名称或表名…")
        self.ed_search.textChanged.connect(self._reload_tasks)
        body.addWidget(self.ed_search)
        self.task_list = QListWidget()
        self.task_list.setObjectName("tasklist")
        self.task_list.currentRowChanged.connect(self._on_task_pick)
        body.addWidget(self.task_list, 1)
        refresh = QPushButton("刷新")
        refresh.setIcon(icon("refresh"))
        refresh.clicked.connect(self.refresh)
        body.addWidget(refresh)
        return frame

    def _build_detail_card(self) -> QWidget:
        frame, body, _ = card()
        head = QHBoxLayout()
        self.lbl_detail_title = QLabel("任务详情")
        self.lbl_detail_title.setObjectName("card_title")
        head.addWidget(self.lbl_detail_title)
        head.addStretch(1)
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setIcon(icon("pencil"))
        self.btn_edit.clicked.connect(lambda: self.navigate(1))
        self.btn_run = QPushButton("运行任务")
        self.btn_run.setObjectName("primary")
        self.btn_run.setIcon(icon("play", "#ffffff"))
        self.btn_run.clicked.connect(self._on_run)
        head.addWidget(self.btn_edit)
        head.addWidget(self.btn_run)
        body.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(12)
        src_g, src = self._group("源表（生产库）")
        self.v_src_conn = src["add_row"]("连接")
        self.v_src_schema = src["add_row"]("模式")
        self.v_src_table = src["add_row"]("表名")
        self.v_src_col = src["add_row"]("归档日期字段")
        self.v_src_months = src["add_row"]("保留月份")
        self.v_src_cond = src["add_row"]("归档条件")
        self.v_src_keys = src["add_row"]("主键列")
        cols.addWidget(src_g, 1)

        tgt_g, tgt = self._group("目标表（归档库）")
        self.v_tgt_conn = tgt["add_row"]("连接")
        self.v_tgt_schema = tgt["add_row"]("模式")
        self.v_tgt_table = tgt["add_row"]("表名")
        self.v_tgt_create = tgt["add_row"]("目标表操作")
        self.v_tgt_batch = tgt["add_row"]("批量大小")
        self.v_tgt_verify = tgt["add_row"]("校验方式")
        cols.addWidget(tgt_g, 1)

        stat_g, st = self._group("任务统计（预估）")
        self.v_stat_rows = st["add_row"]("待归档数据", "—", "#2563eb")
        self.v_stat_rows.setStyleSheet("color:#2563eb; font-size:20px; font-weight:700;")
        self.v_stat_size = st["add_row"]("数据大小（预估）")
        self.v_stat_idx = st["add_row"]("索引大小（预估）")
        self.v_stat_batches = st["add_row"]("预计批次数")
        self.v_stat_time = st["add_row"]("预计耗时")
        self.btn_reanalyze = QPushButton("重新分析")
        self.btn_reanalyze.setIcon(icon("analyze"))
        self.btn_reanalyze.clicked.connect(self._on_reanalyze)
        st["grid"].addWidget(self.btn_reanalyze, st["row"], 0, 1, 2)
        cols.addWidget(stat_g, 1)
        body.addLayout(cols)
        return frame

    @staticmethod
    def _group(title: str):
        w = QFrame()
        w.setObjectName("group")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600; padding:10px 12px 0 12px;")
        lay.addWidget(t)
        kv, api = kv_grid()
        lay.addWidget(kv)
        return w, api

    def _build_run_card(self) -> QWidget:
        frame, body, _ = card()
        head = QHBoxLayout()
        self.lbl_run_title = QLabel("当前运行")
        self.lbl_run_title.setObjectName("card_title")
        head.addWidget(self.lbl_run_title)
        head.addStretch(1)
        head.addWidget(QLabel("状态："))
        self.lbl_pill = QLabel("无运行")
        self.lbl_pill.setObjectName("pill")
        head.addWidget(self.lbl_pill)
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setIcon(icon("pause"))
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setIcon(icon("stop"))
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self._on_stop)
        head.addWidget(self.btn_pause)
        head.addWidget(self.btn_stop)
        body.addLayout(head)

        self.stepper = Stepper()
        body.addWidget(self.stepper)

        prog = QHBoxLayout()
        prog.addWidget(QLabel("总进度"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        prog.addWidget(self.bar, 1)
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setStyleSheet("font-weight:600;")
        prog.addWidget(self.lbl_pct)
        body.addLayout(prog)

        self.metric_vals: list[QLabel] = []
        mg = QHBoxLayout()
        mg.setSpacing(8)
        for name, color in [("总行数", "#2563eb"), ("已复制", "#16a34a"),
                            ("已校验", "#16a34a"), ("已删除", ""),
                            ("失败行数", "#dc2626"), ("当前批次", ""),
                            ("批次大小", ""), ("耗时", ""), ("预计剩余", "")]:
            colw = QVBoxLayout()
            colw.setSpacing(2)
            k = QLabel(name)
            k.setObjectName("muted")
            k.setAlignment(Qt.AlignHCenter)
            v = QLabel("—")
            v.setAlignment(Qt.AlignHCenter)
            v.setStyleSheet(f"font-size:15px; font-weight:700;{f' color:{color};' if color else ''}")
            colw.addWidget(k)
            colw.addWidget(v)
            mg.addLayout(colw, 1)  # 等分拉伸：指标横跨卡片两端平均分布
            self.metric_vals.append(v)
        body.addLayout(mg)

        tables = QHBoxLayout()
        tables.setSpacing(12)
        log_g = QVBoxLayout()
        log_g.addWidget(QLabel("<b>运行日志</b>"))
        self.tbl_log = QTableWidget()
        self.tbl_log.setColumnCount(4)
        self.tbl_log.setHorizontalHeaderLabels(["时间", "级别", "阶段", "消息"])
        self.tbl_log.horizontalHeader().setStretchLastSection(True)
        self.tbl_log.horizontalHeader().setMinimumSectionSize(48)
        self.tbl_log.verticalHeader().setVisible(False)
        log_g.addWidget(self.tbl_log, 1)
        foot = QHBoxLayout()
        btn_clear = QPushButton("清空日志")
        btn_clear.clicked.connect(lambda: self.tbl_log.setRowCount(0))
        self.chk_scroll = QCheckBox("自动滚动")
        self.chk_scroll.setChecked(True)
        foot.addWidget(btn_clear)
        foot.addStretch(1)
        foot.addWidget(self.chk_scroll)
        log_g.addLayout(foot)
        logw = QWidget()
        logw.setLayout(log_g)
        tables.addWidget(logw, 1)

        bat_g = QVBoxLayout()
        bat_g.addWidget(QLabel("<b>批次列表</b>"))
        self.tbl_batch = QTableWidget()
        self.tbl_batch.setColumnCount(8)
        self.tbl_batch.setHorizontalHeaderLabels(
            ["批次号", "状态", "选择行数", "复制行数", "校验行数", "删除行数", "开始时间", "耗时"])
        self.tbl_batch.horizontalHeader().setMinimumSectionSize(48)
        self.tbl_batch.verticalHeader().setVisible(False)
        bat_g.addWidget(self.tbl_batch, 1)
        bfoot = QHBoxLayout()
        btn_b = QPushButton("刷新")
        btn_b.setIcon(icon("refresh"))
        btn_b.clicked.connect(self._reload_run)
        bfoot.addWidget(btn_b)
        bfoot.addStretch(1)
        bat_g.addLayout(bfoot)
        batw = QWidget()
        batw.setLayout(bat_g)
        tables.addWidget(batw, 1)
        body.addLayout(tables, 1)
        return frame

    # ================= 刷新 =================
    def refresh(self) -> None:
        self._reload_connections()
        self._reload_tasks()
        self._reload_detail()
        self._reload_run()

    def _reload_connections(self) -> None:
        sig = tuple((c.id, c.name, c.role.value, c.host, c.port, c.service_name, c.username)
                    for c in self.controller.list_connections())
        if sig == self._conn_sig:
            return
        self._conn_sig = sig
        while self.conn_box.count():
            item = self.conn_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in self.controller.list_connections():
            color = ROLE_COLOR.get(c.role.value, "#2563eb")
            f = QFrame()
            f.setObjectName("listitem")
            f.setStyleSheet(f"border-left:3px solid {color};")
            lay = QVBoxLayout(f)
            lay.setContentsMargins(10, 8, 10, 8)
            top = QHBoxLayout()
            name = QLabel(f"{c.name}（{ROLE_TEXT.get(c.role.value, c.role.value)}）")
            name.setStyleSheet(f"color:{color}; font-weight:600;")
            top.addWidget(name)
            top.addStretch(1)
            st = QLabel("● 已配置")
            st.setStyleSheet("color:#16a34a; font-size:12px;")
            top.addWidget(st)
            lay.addLayout(top)
            dsn = QLabel(f"{c.host}:{c.port}/{c.service_name}")
            dsn.setObjectName("muted")
            lay.addWidget(dsn)
            lay.addWidget(QLabel(c.username))
            self.conn_box.addWidget(f)
        self.conn_box.addStretch(1)

    def _reload_tasks(self) -> None:
        kw = self.ed_search.text().strip().lower()
        tasks = [t for t in self.controller.list_tasks()
                 if not kw or kw in t.task_name.lower() or kw in t.source_table.lower()]
        sig = (kw, tuple((t.id, t.task_name, t.source_table, t.target_table, t.enabled)
                         for t in tasks))
        if sig == self._task_sig:
            return
        self._task_sig = sig
        self.task_list.blockSignals(True)
        self.task_list.clear()
        for t in tasks:
            item = QListWidgetItem()
            w = QFrame()
            w.setObjectName("listitem")
            w.setProperty("selected", t.id == self._task_id)
            w.setMinimumHeight(58)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(10, 6, 10, 6)
            top = QHBoxLayout()
            n = QLabel(t.task_name)
            n.setStyleSheet("font-weight:600;")
            top.addWidget(n)
            top.addStretch(1)
            badge = QLabel("启用" if t.enabled else "禁用")
            badge.setObjectName("badge_on" if t.enabled else "badge_off")
            top.addWidget(badge)
            lay.addLayout(top)
            sub = QLabel(f"{t.source_table}  →  {t.target_table}")
            sub.setObjectName("muted")
            lay.addWidget(sub)
            item.setData(Qt.UserRole, t.id)
            item.setSizeHint(QSize(0, 66))
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, w)
        # 保持选中（屏蔽信号避免递归）
        if self._task_id is None and tasks:
            self._task_id = tasks[0].id
        for i in range(self.task_list.count()):
            if self.task_list.item(i).data(Qt.UserRole) == self._task_id:
                self.task_list.setCurrentRow(i)
                break
        self.task_list.blockSignals(False)

    def _on_task_pick(self, row: int) -> None:
        item = self.task_list.item(row)
        if item is None:
            return
        self._task_id = item.data(Qt.UserRole)
        self._task_sig = ()  # 重建列表以刷新选中高亮
        self._reload_tasks()
        self._reload_detail()
        self._reload_run()

    def _current_task(self) -> ArchiveTask | None:
        if self._task_id is None:
            return None
        return self.controller.tasks.get(self._task_id)

    def _reload_detail(self) -> None:
        t = self._current_task()
        if t is None:
            self.lbl_detail_title.setText("任务详情（暂无任务）")
            return
        self.lbl_detail_title.setText(f"任务详情 - {t.task_name}")
        conns = {c.id: c.name for c in self.controller.list_connections()}
        self.v_src_conn.setText(conns.get(t.source_connection_id, "—"))
        self.v_src_schema.setText(t.source_schema)
        self.v_src_table.setText(t.source_table)
        self.v_src_col.setText(t.archive_column or "（无，按 WHERE/全表）")
        self.v_src_months.setText(str(t.keep_months))
        self.v_src_cond.setText(t.extra_where or "—")
        self.v_src_keys.setText(",".join(t.key_columns) or "—")
        self.v_tgt_conn.setText(conns.get(t.target_connection_id, "—"))
        self.v_tgt_schema.setText(t.target_schema)
        self.v_tgt_table.setText(t.target_table)
        self.v_tgt_create.setText("如果不存在则创建" if t.create_target_if_missing else "必须已存在")
        self.v_tgt_batch.setText(f"{t.batch_size:,}")
        self.v_tgt_verify.setText(f"{t.verify_mode.value} 校验")

    def _on_reanalyze(self) -> None:
        t = self._current_task()
        if t is None:
            return
        self.btn_reanalyze.setEnabled(False)
        self._worker = _AnalyzeWorker(self.controller, t)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.start()

    def _on_analyze_done(self, rep, error) -> None:
        self.btn_reanalyze.setEnabled(True)
        if rep is None:
            self.v_stat_rows.setText("分析失败")
            return
        self.v_stat_rows.setText(f"{rep.eligible_rows:,}")
        self.v_stat_size.setText(_gb(rep.source_bytes))
        self.v_stat_idx.setText(_gb(rep.index_bytes))
        self.v_stat_batches.setText(str(rep.estimated_batches))
        self.v_stat_time.setText(f"~ {rep.estimated_seconds // 60} 分钟")

    def _reload_run(self) -> None:
        runs = self.controller.list_runs(self._task_id) if self._task_id else []
        run = runs[0] if runs else None
        if run is None:
            self.lbl_run_title.setText("当前运行（暂无）")
            self.lbl_pill.setText("无运行")
            apply_pill(self.lbl_pill, "")
            self.stepper.set_state([("pending", "")] * 5)
            self.bar.setValue(0)
            self.lbl_pct.setText("0%")
            for v in self.metric_vals:
                v.setText("—")
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.tbl_log.setRowCount(0)
            self.tbl_batch.setRowCount(0)
            return

        task = self._current_task()
        batches = self.controller.runs.list_batches(run.run_id)
        self.lbl_run_title.setText(f"当前运行 - {run.run_id}")
        done_n = run.success_batches + run.failed_batches
        self.lbl_pill.setText(f"{status_zh(run.status.value)}（批次 {done_n}/{run.total_batches}）")
        apply_pill(self.lbl_pill, run.status.value)
        self.btn_pause.setEnabled(run.status in (RunStatus.RUNNING, RunStatus.PAUSING))
        self.btn_stop.setEnabled(run.status in (RunStatus.RUNNING, RunStatus.PAUSING,
                                                RunStatus.PAUSED))

        # ---- 五步状态 ----
        copy_done = run.status in (RunStatus.VERIFIED, RunStatus.COMPLETED) or (
            run.expected_rows > 0 and run.transferred_rows >= run.expected_rows)
        verify_done = run.status in (RunStatus.VERIFIED, RunStatus.COMPLETED)
        purge_done = run.status is RunStatus.COMPLETED
        failed = run.status is RunStatus.FAILED
        active = run.status.active

        def step(done: bool, is_active: bool, sub: str) -> tuple[str, str]:
            if done:
                return "done", sub
            if failed and is_active:
                return "fail", sub
            if active and is_active:
                return "active", sub
            return "pending", "等待中" if not done else sub

        states = [
            ("done", f"完成\n{to_local(run.start_time)}"),
            step(copy_done, True, f"{run.transferred_rows:,} 行"),
            step(verify_done, not copy_done or not verify_done,
                 f"{run.verified_rows:,} 行"),
            step(purge_done, verify_done and not purge_done, ""),
            step(purge_done, False, ""),
        ]
        self.stepper.set_state(states)

        pct = int(run.transferred_rows * 100 / run.expected_rows) if run.expected_rows else 0
        self.bar.setValue(min(pct, 100))
        self.lbl_pct.setText(f"{pct}%")

        vals = [
            f"{run.expected_rows:,}", f"{run.transferred_rows:,}",
            f"{run.verified_rows:,}", f"{run.deleted_rows:,}",
            str(run.failed_batches), f"{done_n} / {run.total_batches}",
            f"{task.batch_size:,}" if task else "—",
            _elapsed(run.start_time, run.end_time), "—",
        ]
        for v, label in zip(self.metric_vals, vals):
            v.setText(label)

        # ---- 日志 ----
        logs = self.controller.run_logs(run.run_id)
        self.tbl_log.setRowCount(len(logs))
        for i, l in enumerate(reversed(logs)):
            for j, txt in enumerate([to_local(l["log_time"])[11:19],
                                     level_zh(l["level"]), stage_zh(l["stage"]), l["message"]]):
                self.tbl_log.setItem(i, j, QTableWidgetItem(txt))
        if self.chk_scroll.isChecked():
            self.tbl_log.scrollToTop()

        # ---- 批次 ----
        self.tbl_batch.setRowCount(len(batches))
        for i, b in enumerate(batches):
            vals = [str(b.batch_no), status_zh(b.status.value), f"{b.selected_rows:,}",
                    f"{b.transferred_rows:,}", f"{b.verified_rows:,}",
                    f"{b.deleted_rows:,}", to_local(b.start_time)[11:19],
                    _elapsed(b.start_time, b.end_time)]
            for j, txt in enumerate(vals):
                item = QTableWidgetItem(txt)
                if j == 1:
                    item.setForeground(_batch_color(b.status.value))
                self.tbl_batch.setItem(i, j, item)

    # ---- 动作 ----
    def _on_run(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        if self._task_id is None:
            return
        try:
            self.controller.start_run(self._task_id)
        except Exception as exc:
            QMessageBox.warning(self, "启动运行失败", str(exc))
            return
        self._reload_run()

    def _on_pause(self) -> None:
        if self._current_run_id():
            self.controller.pause_run(self._current_run_id())
            self._reload_run()

    def _on_stop(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        rid = self._current_run_id()
        if not rid:
            return
        run = self.controller.runs.get_run(rid)
        if run is None:
            return
        if run.status in (RunStatus.RUNNING, RunStatus.PAUSING):
            self.controller.pause_run(rid)
        elif run.status is RunStatus.PAUSED:
            if QMessageBox.question(self, "停止", "取消该 Run？已复制批次保留。") \
                    == QMessageBox.Yes:
                self.controller.cancel_run(rid)
        self._reload_run()

    def _current_run_id(self) -> str | None:
        runs = self.controller.list_runs(self._task_id) if self._task_id else []
        return runs[0].run_id if runs else None


def _batch_color(status: str) -> QColor:
    if status in ("COMPLETED", "VERIFIED", "COPIED"):
        return QColor("#16a34a")
    if status in ("COPYING", "VERIFYING", "PURGING"):
        return QColor("#2563eb")
    if status == "FAILED":
        return QColor("#dc2626")
    return QColor("#9aa4b2")
