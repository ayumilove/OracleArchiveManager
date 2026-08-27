"""Run / Batch 领域模型与状态机，见 03 §3/§4 与 04。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    COPY_COMPLETED = "COPY_COMPLETED"  # 达 max_rows_per_run 的部分完成
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    COMPLETED = "COMPLETED"

    @property
    def active(self) -> bool:
        """活动 Run：非终态（04 §9 并发互斥口径）。"""
        return self not in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED)


class BatchStatus(str, Enum):
    PENDING = "PENDING"
    COPYING = "COPYING"
    COPIED = "COPIED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    PURGING = "PURGING"
    COMPLETED = "COMPLETED"


class ArchiveRun(BaseModel):
    run_id: str
    task_id: int
    task_snapshot: dict
    cutoff_value: str
    archive_condition: str
    expected_rows: int = 0
    transferred_rows: int = 0
    verified_rows: int = 0
    deleted_rows: int = 0
    total_batches: int = 0
    success_batches: int = 0
    failed_batches: int = 0
    status: RunStatus = RunStatus.RUNNING
    start_time: str | None = None
    copy_end_time: str | None = None
    verify_end_time: str | None = None
    purge_start_time: str | None = None
    end_time: str | None = None
    error_message: str | None = None


class ArchiveBatch(BaseModel):
    batch_id: str
    run_id: str
    batch_no: int
    selection_snapshot: dict | None = None
    selected_rows: int = 0
    transferred_rows: int = 0
    verified_rows: int = 0
    deleted_rows: int = 0
    status: BatchStatus = BatchStatus.PENDING
    start_time: str | None = None
    copy_end_time: str | None = None
    verify_end_time: str | None = None
    purge_end_time: str | None = None
    end_time: str | None = None
    error_message: str | None = None
