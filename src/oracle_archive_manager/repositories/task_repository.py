"""控制库任务表 CRUD。"""
from __future__ import annotations

import json

from ..domain.task import ArchiveTask, PurgeMode, VerifyMode
from ..storage.sqlite import ControlDB
from ..utils.time import now_iso


def _row_to_model(row) -> ArchiveTask:
    return ArchiveTask(
        id=row["id"],
        task_name=row["task_name"],
        source_connection_id=row["source_connection_id"],
        source_schema=row["source_schema"],
        source_table=row["source_table"],
        target_connection_id=row["target_connection_id"],
        target_schema=row["target_schema"],
        target_table=row["target_table"],
        archive_column=row["archive_column"] or None,
        keep_months=row["keep_months"],
        extra_where=row["extra_where"],
        key_columns=json.loads(row["key_columns"]),
        batch_size=row["batch_size"],
        max_rows_per_run=row["max_rows_per_run"],
        verify_mode=VerifyMode(row["verify_mode"]),
        purge_mode=PurgeMode(row["purge_mode"]),
        allow_purge=bool(row["allow_purge"]),
        schedule_enabled=bool(row["schedule_enabled"]),
        schedule_time=row["schedule_time"],
        create_target_if_missing=bool(row["create_target_if_missing"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class TaskRepository:
    def __init__(self, db: ControlDB) -> None:
        self.db = db

    def list_all(self) -> list[ArchiveTask]:
        conn = self.db.connect()
        try:
            rows = conn.execute("SELECT * FROM archive_task ORDER BY id").fetchall()
            return [_row_to_model(r) for r in rows]
        finally:
            conn.close()

    def get(self, task_id: int) -> ArchiveTask | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM archive_task WHERE id = ?", (task_id,)).fetchone()
            return _row_to_model(row) if row else None
        finally:
            conn.close()

    def create(self, t: ArchiveTask) -> ArchiveTask:
        now = now_iso()
        conn = self.db.connect()
        try:
            cur = conn.execute(
                """INSERT INTO archive_task
                   (task_name, source_connection_id, source_schema, source_table,
                    target_connection_id, target_schema, target_table,
                    archive_column, keep_months, extra_where, key_columns,
                    batch_size, max_rows_per_run, verify_mode, purge_mode,
                    allow_purge, schedule_enabled, schedule_time, create_target_if_missing,
                    enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    t.task_name, t.source_connection_id, t.source_schema, t.source_table,
                    t.target_connection_id, t.target_schema, t.target_table,
                    t.archive_column or "", t.keep_months, t.extra_where,
                    json.dumps(t.key_columns), t.batch_size, t.max_rows_per_run,
                    t.verify_mode.value, t.purge_mode.value,
                    int(t.allow_purge), int(t.schedule_enabled), t.schedule_time,
                    int(t.create_target_if_missing),
                    int(t.enabled), now, now,
                ),
            )
            conn.commit()
            return t.model_copy(update={"id": cur.lastrowid, "created_at": now, "updated_at": now})
        finally:
            conn.close()

    def update(self, t: ArchiveTask) -> None:
        now = now_iso()
        conn = self.db.connect()
        try:
            conn.execute(
                """UPDATE archive_task SET
                   task_name=?, source_connection_id=?, source_schema=?, source_table=?,
                   target_connection_id=?, target_schema=?, target_table=?,
                   archive_column=?, keep_months=?, extra_where=?, key_columns=?,
                   batch_size=?, max_rows_per_run=?, verify_mode=?, purge_mode=?,
                   allow_purge=?, schedule_enabled=?, schedule_time=?, create_target_if_missing=?,
                   enabled=?, updated_at=?
                   WHERE id=?""",
                (
                    t.task_name, t.source_connection_id, t.source_schema, t.source_table,
                    t.target_connection_id, t.target_schema, t.target_table,
                    t.archive_column or "", t.keep_months, t.extra_where,
                    json.dumps(t.key_columns), t.batch_size, t.max_rows_per_run,
                    t.verify_mode.value, t.purge_mode.value,
                    int(t.allow_purge), int(t.schedule_enabled), t.schedule_time,
                    int(t.create_target_if_missing),
                    int(t.enabled), now, t.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, task_id: int) -> None:
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM archive_task WHERE id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()
