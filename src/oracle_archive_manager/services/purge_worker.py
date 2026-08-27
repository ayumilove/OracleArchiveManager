"""Purge 引擎：仅 VERIFIED 批次可删源，分批 DELETE/COMMIT，审计留痕，见 04 §4。

Destruction is explicit：入口必须经 Purge Preview + 表名手输二次确认（controller 把关）。
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QThread, Signal

from ..domain.run import BatchStatus, RunStatus
from ..domain.task import ArchiveTask
from ..oracle import copy as oc
from ..repositories.run_repository import RunRepository
from ..utils.time import now_iso
from .run_worker import with_retry

# PURGING 视为可续跑（DELETE 按 key 区间幂等）
PURGE_ELIGIBLE = (BatchStatus.VERIFIED, BatchStatus.PURGING)


class PurgeWorker(QThread):
    changed = Signal(str)
    done = Signal(str, str)

    def __init__(self, repo: RunRepository, open_conn, run_id: str, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.open_conn = open_conn
        self.run_id = run_id

    def _log(self, message: str, level: str = "INFO", batch_id: str | None = None) -> None:
        self.repo.append_log(self.run_id, batch_id, level, "PURGE", message)

    def run(self) -> None:
        repo = self.repo
        run = repo.get_run(self.run_id)
        if run is None:
            return
        task = ArchiveTask(**run.task_snapshot)
        cutoff = date.fromisoformat(run.cutoff_value) if run.cutoff_value and task.archive_column else None
        cond_params: dict = {"cutoff": cutoff} if cutoff is not None else {}
        repo.update_run(self.run_id, purge_start_time=now_iso())
        self._log(f"Purge 开始：{task.source_schema}.{task.source_table}")
        self.changed.emit(self.run_id)

        src = None
        deleted_total = run.deleted_rows
        try:
            src = self.open_conn(task.source_connection_id)
            for b in repo.list_batches(self.run_id):
                if b.status not in PURGE_ELIGIBLE:
                    continue
                snap = b.selection_snapshot or {}
                prev, last = snap.get("prev_keys"), snap.get("last_keys")
                if last is None:
                    continue
                repo.update_batch(b.batch_id, status=BatchStatus.PURGING)

                def do_delete(prev=prev, last=last):
                    n = oc.delete_range(
                        src, task.source_schema, task.source_table,
                        task.key_columns, prev, last,
                        run.archive_condition or None, cond_params,
                    )
                    src.commit()  # 05 §9：分批提交
                    return n

                try:
                    n = with_retry(do_delete,
                                   log=lambda m: self._log(m, "WARN", b.batch_id))
                except Exception as exc:
                    repo.update_batch(b.batch_id, status=BatchStatus.FAILED,
                                      error_message=f"Purge 失败：{exc}",
                                      end_time=now_iso())
                    self._log(f"批次 {b.batch_no} Purge 失败：{exc}", "ERROR", b.batch_id)
                    repo.update_run(self.run_id, status=RunStatus.FAILED,
                                    error_message=f"Purge 批次 {b.batch_no} 失败",
                                    end_time=now_iso())
                    return

                deleted_total += n
                repo.update_batch(b.batch_id, status=BatchStatus.COMPLETED,
                                  deleted_rows=n, purge_end_time=now_iso(),
                                  end_time=now_iso())
                repo.update_run(self.run_id, deleted_rows=deleted_total)
                self._log(f"批次 {b.batch_no} 已删除源数据 {n} 行", batch_id=b.batch_id)
                self.changed.emit(self.run_id)

            repo.update_run(self.run_id, status=RunStatus.COMPLETED, end_time=now_iso())
            self._log(f"Purge 完成，累计删除 {deleted_total} 行；Run=COMPLETED")
        except Exception as exc:
            repo.update_run(self.run_id, status=RunStatus.FAILED,
                            error_message=str(exc), end_time=now_iso())
            self._log(f"Purge 失败：{exc}", "ERROR")
        finally:
            if src is not None:
                try:
                    src.close()
                except Exception:
                    pass
        self.changed.emit(self.run_id)
        final = repo.get_run(self.run_id)
        self.done.emit(self.run_id, final.status.value if final else "UNKNOWN")
