"""应用服务层：GUI 只调用 controller，禁止在按钮事件中写 SQL，见 02 §2.1。"""
from __future__ import annotations

from ..domain.connection import ArchiveConnection
from ..domain.run import ArchiveRun, RunStatus
from ..domain.task import ArchiveTask
from ..oracle import connection as oracle_conn
from ..oracle import metadata as oracle_meta
from ..repositories.control_repository import ConnectionRepository
from ..repositories.run_repository import RunRepository
from ..repositories.task_repository import TaskRepository
from ..security import credential
from ..services import analyze_service
from ..services.analyze_service import AnalyzeReport, build_condition
from ..services.purge_worker import PURGE_ELIGIBLE, PurgeWorker
from ..services.run_worker import RunWorker
from ..storage.sqlite import ControlDB
from ..utils.config import AppConfig
from ..utils.ids import new_run_id
from ..utils.time import compute_cutoff, now_iso

from datetime import date


class AppController:
    def __init__(self, db: ControlDB, config: AppConfig | None = None) -> None:
        self.db = db
        self.config = config or AppConfig()
        self.connections = ConnectionRepository(db)
        self.tasks = TaskRepository(db)
        self.runs = RunRepository(db)
        self._workers: dict[str, RunWorker] = {}

    # ---- 连接管理 ----
    def list_connections(self) -> list[ArchiveConnection]:
        return self.connections.list_all()

    def save_connection(self, c: ArchiveConnection, password: str | None = None) -> ArchiveConnection:
        """保存连接；提供密码时写入凭据库，SQLite 仅存 credential_ref。"""
        if password:
            ref = c.credential_ref or credential.new_credential_ref(c.name)
            credential.store_credential(ref, password)
            c = c.model_copy(update={"credential_ref": ref})
        if c.id is None:
            return self.connections.create(c)
        self.connections.update(c)
        return c

    def delete_connection(self, connection_id: int) -> None:
        c = self.connections.get(connection_id)
        if c and c.credential_ref:
            credential.delete_credential(c.credential_ref)
        self.connections.delete(connection_id)

    def get_password(self, c: ArchiveConnection) -> str | None:
        if not c.credential_ref:
            return None
        return credential.load_credential(c.credential_ref)

    def test_connection(self, c: ArchiveConnection, password: str | None = None, thick: bool | None = None) -> str:
        """测试连接；成功时把版本号回写控制库。默认 Thick 与否取系统设置。"""
        if thick is None:
            thick = bool(self.config.get("thick_mode"))
        pwd = password if password is not None else self.get_password(c)
        if pwd is None:
            raise ValueError("无可用凭据")
        version = oracle_conn.test_connection(
            host=c.host,
            port=c.port,
            service_name=c.service_name,
            username=c.username,
            password=pwd,
            thick=thick,
        )
        if c.id is not None:
            stored = self.connections.get(c.id)
            if stored is not None:
                self.connections.update(stored.model_copy(update={"oracle_version": version}))
        return version

    # ---- Metadata（只读，Phase 1）----
    def _open(self, connection_id: int):
        c = self.connections.get(connection_id)
        if c is None:
            raise ValueError(f"连接不存在：id={connection_id}")
        pwd = self.get_password(c)
        if pwd is None:
            raise ValueError(f"连接 {c.name} 无可用凭据")
        return oracle_conn.connect(
            host=c.host, port=c.port, service_name=c.service_name,
            username=c.username, password=pwd,
            thick=bool(self.config.get("thick_mode")),
        )

    def list_schemas(self, connection_id: int) -> list[str]:
        with self._open(connection_id) as conn:
            return oracle_meta.list_schemas(conn)

    def list_tables(self, connection_id: int, schema: str) -> list[str]:
        with self._open(connection_id) as conn:
            return oracle_meta.list_tables(conn, schema)

    def list_columns(self, connection_id: int, schema: str, table: str) -> list[str]:
        with self._open(connection_id) as conn:
            return [c.name for c in oracle_meta.get_columns(conn, schema, table)]

    def primary_key_columns(self, connection_id: int, schema: str, table: str) -> list[str]:
        with self._open(connection_id) as conn:
            return oracle_meta.get_primary_key(conn, schema, table)

    # ---- 任务管理 ----
    def list_tasks(self) -> list[ArchiveTask]:
        return self.tasks.list_all()

    def save_task(self, t: ArchiveTask) -> ArchiveTask:
        if t.id is None:
            return self.tasks.create(t)
        self.tasks.update(t)
        return t

    def delete_task(self, task_id: int) -> None:
        self.tasks.delete(task_id)

    def toggle_task_enabled(self, task_id: int) -> ArchiveTask:
        """启用/禁用任务；禁用后不可创建 Run。"""
        t = self.tasks.get(task_id)
        if t is None:
            raise ValueError(f"任务不存在：id={task_id}")
        t.enabled = not t.enabled
        self.tasks.update(t)
        return t

    # ---- Analyze / Dry Run ----
    def analyze_task(self, t: ArchiveTask) -> AnalyzeReport:
        with self._open(t.source_connection_id) as src, self._open(t.target_connection_id) as tgt:
            return analyze_service.analyze(t, src, tgt)

    # ---- Run（Phase 2）----
    def create_run(self, task_id: int) -> str:
        """创建 Run 并冻结 cutoff/condition（04 §6）；同 Task 单活动 Run（04 §9）。"""
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError(f"任务不存在：id={task_id}")
        if not task.enabled:
            raise RuntimeError("任务已禁用，无法创建 Run")
        if self.runs.active_run_for_task(task_id) is not None:
            raise RuntimeError("该任务已存在活动 Run，同一时刻仅允许一个（04 §9）")
        cutoff = compute_cutoff(date.today(), task.keep_months) if task.archive_column else None
        cond, params = build_condition(task, cutoff)
        with self._open(task.source_connection_id) as src:
            expected = oracle_meta.count_rows(
                src, task.source_schema, task.source_table, cond, params
            )
        run = ArchiveRun(
            run_id=new_run_id(), task_id=task_id,
            task_snapshot=task.model_dump(mode="json"),
            cutoff_value=cutoff.isoformat() if cutoff else "",
            archive_condition=cond or "",
            expected_rows=expected, status=RunStatus.RUNNING, start_time=now_iso(),
        )
        self.runs.create_run(run)
        self.runs.append_log(run.run_id, None, "INFO", "RUN",
                             f"运行创建；截止时间={run.cutoff_value or '无'}；条件={cond or '全表'}")
        return run.run_id

    def start_run(self, task_id: int) -> str:
        run_id = self.create_run(task_id)
        self._spawn(run_id, resume=False)
        return run_id

    def _spawn(self, run_id: str, resume: bool) -> None:
        w = RunWorker(self.runs, self._open, run_id, resume=resume)
        w.done.connect(lambda rid, _st: self._workers.pop(rid, None))
        self._workers[run_id] = w
        w.start()

    def has_worker(self, run_id: str) -> bool:
        """该 Run 是否仍有存活执行线程（区分孤儿 PAUSING 与真实暂停中）。"""
        return run_id in self._workers

    def pause_run(self, run_id: str) -> None:
        """04 §7：PAUSING → 当前批次结束后 PAUSED。"""
        run = self.runs.get_run(run_id)
        if run is not None and run.status is RunStatus.RUNNING:
            self.runs.update_run(run_id, status=RunStatus.PAUSING)
        w = self._workers.get(run_id)
        if w is not None:
            w.request_pause()

    def resume_run(self, run_id: str) -> None:
        run = self.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        if run.status in (RunStatus.PAUSING, RunStatus.RUNNING) \
                and run_id not in self._workers:
            pass  # 孤儿状态（如执行中进程被关），按中断处理可 Resume 续跑/补拷
        elif run.status not in (RunStatus.PAUSED, RunStatus.FAILED):
            raise RuntimeError("仅已暂停/失败状态的运行可继续（04 §5）")
        self._spawn(run_id, resume=True)

    def cancel_run(self, run_id: str) -> None:
        """Safe Stop（V1）：先暂停、待 PAUSED 后显式取消；已完成批次与目标数据保留。"""
        run = self.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        if run.status in (RunStatus.PAUSING, RunStatus.RUNNING) \
                and run_id not in self._workers:
            pass  # 孤儿状态可安全取消（无存活线程）
        elif run.status not in (RunStatus.PAUSED, RunStatus.FAILED):
            raise RuntimeError("请先点“暂停”，待状态变为已暂停后再安全停止")
        self.runs.update_run(run_id, status=RunStatus.CANCELED, end_time=now_iso())
        self.runs.append_log(run_id, None, "INFO", "RUN", "安全停止：运行已取消，已复制批次保留")

    def list_runs(self, task_id: int | None = None):
        return self.runs.list_runs(task_id)

    def run_detail(self, run_id: str):
        return self.runs.get_run(run_id), self.runs.list_batches(run_id)

    def run_logs(self, run_id: str):
        return self.runs.logs_for_run(run_id)

    def recent_logs(self, run_id: str | None = None, level: str | None = None,
                    stage: str | None = None, limit: int = 1000):
        return self.runs.recent_logs(run_id, level, stage, limit)

    # ---- Purge（Phase 3，Destruction is explicit）----
    def complete_run(self, run_id: str) -> None:
        """无需 Purge：人工将 VERIFIED Run 直接完结，释放任务活动名额（04 §9）。"""
        run = self.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        if run.status is not RunStatus.VERIFIED:
            raise RuntimeError("仅已验证状态的运行可标记完结")
        self.runs.update_run(run_id, status=RunStatus.COMPLETED.value,
                             end_time=now_iso())
        self.runs.append_log(run_id, None, "INFO", "RUN", "人工标记完结（无需清理）")

    def purge_preview(self, run_id: str) -> dict:
        """Purge Preview：仅列出可删批次（VERIFIED / 中断的 PURGING）。"""
        run = self.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        task = ArchiveTask(**run.task_snapshot)
        if not task.allow_purge:
            raise RuntimeError("该任务配置为禁止清理源数据，不允许执行清理")
        batches = [b for b in self.runs.list_batches(run_id) if b.status in PURGE_ELIGIBLE]
        return {
            "run": run,
            "task": task,
            "batches": batches,
            "total_rows": sum(b.verified_rows for b in batches),
        }

    def start_purge(self, run_id: str, confirm_table: str) -> None:
        """04 §4：仅 VERIFIED Run 可 Purge；表名手输二次确认。"""
        run = self.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        if run.status is not RunStatus.VERIFIED:
            raise RuntimeError("仅已验证状态的运行可执行清理（04 §4）")
        task = ArchiveTask(**run.task_snapshot)
        if not task.allow_purge:
            raise RuntimeError("该任务配置为禁止清理源数据，不允许执行清理")
        if confirm_table.strip().upper() != task.source_table.upper():
            raise ValueError(f"输入表名与源表 {task.source_table} 不一致，确认失败")
        w = PurgeWorker(self.runs, self._open, run_id)
        w.done.connect(lambda rid, _st: self._workers.pop(rid, None))
        self._workers[run_id] = w
        w.start()
