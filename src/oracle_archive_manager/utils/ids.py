"""Run / Batch ID 生成。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_run_id() -> str:
    """形如 RUN_20260827_A1B2C3D4。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RUN_{stamp}_{uuid.uuid4().hex[:8].upper()}"


def new_batch_id(run_id: str, batch_no: int) -> str:
    """形如 RUN_20260827_A1B2C3D4_B0001。"""
    return f"{run_id}_B{batch_no:04d}"
