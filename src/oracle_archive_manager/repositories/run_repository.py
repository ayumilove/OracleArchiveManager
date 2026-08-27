"""控制库 Run / Batch / Log 持久化，见 03 §3-§5。"""
from __future__ import annotations

import getpass
import json
from datetime import datetime, timedelta, timezone

from ..domain.run import ArchiveBatch, ArchiveRun, BatchStatus, RunStatus
from ..storage.sqlite import ControlDB
from ..utils.time import now_iso


def _run_of(row) -> ArchiveRun:
    return ArchiveRun(
        run_id=row["run_id"], task_id=row["task_id"],
        task_snapshot=json.loads(row["task_snapshot"]),
        cutoff_value=row["cutoff_value"], archive_condition=row["archive_condition"],
        expected_rows=row["expected_rows"], transferred_rows=row["transferred_rows"],
        verified_rows=row["verified_rows"], deleted_rows=row["deleted_rows"],
        total_batches=row["total_batches"], success_batches=row["success_batches"],
        failed_batches=row["failed_batches"], status=RunStatus(row["status"]),
        start_time=row["start_time"], copy_end_time=row["copy_end_time"],
        verify_end_time=row["verify_end_time"], purge_start_time=row["purge_start_time"],
        end_time=row["end_time"], error_message=row["error_message"],
    )


def _batch_of(row) -> ArchiveBatch:
    return ArchiveBatch(
        batch_id=row["batch_id"], run_id=row["run_id"], batch_no=row["batch_no"],
        selection_snapshot=json.loads(row["selection_snapshot"])
        if row["selection_snapshot"] else None,
        selected_rows=row["selected_rows"], transferred_rows=row["transferred_rows"],
        verified_rows=row["verified_rows"], deleted_rows=row["deleted_rows"],
        status=BatchStatus(row["status"]),
        start_time=row["start_time"], copy_end_time=row["copy_end_time"],
        verify_end_time=row["verify_end_time"], purge_end_time=row["purge_end_time"],
        end_time=row["end_time"], error_message=row["error_message"],
    )


class RunRepository:
    def __init__(self, db: ControlDB) -> None:
        self.db = db

    # ---- Run ----
    def create_run(self, run: ArchiveRun) -> None:
        conn = self.db.connect()
        try:
            conn.execute(
                """INSERT INTO archive_run
                   (run_id, task_id, task_snapshot, cutoff_value, archive_condition,
                    expected_rows, status, start_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run.run_id, run.task_id, json.dumps(run.task_snapshot, ensure_ascii=False),
                 run.cutoff_value, run.archive_condition, run.expected_rows,
                 run.status.value, run.start_time),
            )
            conn.commit()
        finally:
            conn.close()

    def get_run(self, run_id: str) -> ArchiveRun | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM archive_run WHERE run_id = ?", (run_id,)
            ).fetchone()
            return _run_of(row) if row else None
        finally:
            conn.close()

    def list_runs(self, task_id: int | None = None) -> list[ArchiveRun]:
        conn = self.db.connect()
        try:
            if task_id is None:
                rows = conn.execute(
                    "SELECT * FROM archive_run ORDER BY start_time DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM archive_run WHERE task_id = ? ORDER BY start_time DESC",
                    (task_id,),
                ).fetchall()
            return [_run_of(r) for r in rows]
        finally:
            conn.close()

    def active_run_for_task(self, task_id: int) -> ArchiveRun | None:
        """04 §9：同 Task 单活动 Run。"""
        for r in self.list_runs(task_id):
            if r.status.active:
                return r
        return None

    def update_run(self, run_id: str, **fields) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = [
            json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else
            (v.value if hasattr(v, "value") else v)
            for v in fields.values()
        ]
        conn = self.db.connect()
        try:
            conn.execute(
                f"UPDATE archive_run SET {sets} WHERE run_id = ?",
                (*vals, run_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ---- Batch ----
    def create_batch(self, b: ArchiveBatch) -> None:
        conn = self.db.connect()
        try:
            conn.execute(
                """INSERT INTO archive_batch
                   (batch_id, run_id, batch_no, status, start_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (b.batch_id, b.run_id, b.batch_no, b.status.value, b.start_time),
            )
            conn.commit()
        finally:
            conn.close()

    def list_batches(self, run_id: str) -> list[ArchiveBatch]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM archive_batch WHERE run_id = ? ORDER BY batch_no",
                (run_id,),
            ).fetchall()
            return [_batch_of(r) for r in rows]
        finally:
            conn.close()

    def last_batch(self, run_id: str) -> ArchiveBatch | None:
        batches = self.list_batches(run_id)
        return batches[-1] if batches else None

    def update_batch(self, batch_id: str, **fields) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = [
            json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else
            (v.value if hasattr(v, "value") else v)
            for v in fields.values()
        ]
        conn = self.db.connect()
        try:
            conn.execute(
                f"UPDATE archive_batch SET {sets} WHERE batch_id = ?",
                (*vals, batch_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ---- Log ----
    def append_log(
        self, run_id: str | None, batch_id: str | None,
        level: str, stage: str, message: str, detail: str | None = None,
    ) -> None:
        conn = self.db.connect()
        try:
            conn.execute(
                """INSERT INTO archive_log
                   (run_id, batch_id, operator, log_time, level, stage, message, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, batch_id, getpass.getuser(), now_iso(), level, stage, message, detail),
            )
            conn.commit()
        finally:
            conn.close()

    def prune_logs(self, older_than_days: int) -> int:
        """P1：清理超过保留天数的控制库日志，返回删除行数。"""
        before = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        conn = self.db.connect()
        try:
            cur = conn.execute("DELETE FROM archive_log WHERE log_time < ?", (before,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def logs_for_run(self, run_id: str, limit: int = 500) -> list[dict]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                """SELECT log_time, level, stage, message FROM archive_log
                   WHERE run_id = ? ORDER BY id DESC LIMIT ?""",
                (run_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    def recent_logs(self, run_id: str | None = None, level: str | None = None,
                    stage: str | None = None, limit: int = 1000) -> list[dict]:
        """全局日志查询（日志查看页），支持按 Run/级别/阶段过滤。"""
        sql = """SELECT run_id, log_time, level, stage, message FROM archive_log"""
        where, params = [], []
        if run_id:
            where.append("run_id = ?")
            params.append(run_id)
        if level:
            where.append("level = ?")
            params.append(level)
        if stage:
            where.append("stage = ?")
            params.append(stage)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        conn = self.db.connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()
