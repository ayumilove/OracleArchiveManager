"""任务领域模型，对应 ARCHIVE_TASK，见 03_DATA_MODEL.md §2。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class VerifyMode(str, Enum):
    COUNT = "COUNT"
    PK = "PK"
    HASH = "HASH"


class PurgeMode(str, Enum):
    MANUAL = "MANUAL"


class ArchiveTask(BaseModel):
    id: int | None = None
    task_name: str
    source_connection_id: int
    source_schema: str
    source_table: str
    target_connection_id: int
    target_schema: str
    target_table: str
    archive_column: str | None = None
    keep_months: int = 24
    extra_where: str | None = None
    key_columns: list[str] = Field(default_factory=list)
    batch_size: int = 5000
    max_rows_per_run: int | None = None
    verify_mode: VerifyMode = VerifyMode.PK
    purge_mode: PurgeMode = PurgeMode.MANUAL
    allow_purge: bool = True
    schedule_enabled: bool = False
    schedule_time: str = "02:00"  # 每日 HH:MM（本地时间）
    create_target_if_missing: bool = False
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None
