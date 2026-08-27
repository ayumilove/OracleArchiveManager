"""P2 调度任务：due_tasks 触发口径（启用 + 时间匹配 + 当日未触发）。"""
from datetime import datetime

from oracle_archive_manager.domain.task import ArchiveTask
from oracle_archive_manager.services.scheduler import due_tasks


def _task(**kw) -> ArchiveTask:
    base = dict(task_name="T", source_connection_id=1, source_schema="S",
                source_table="T1", target_connection_id=2, target_schema="S",
                target_table="T1", key_columns=["ID"], id=1)
    base.update(kw)
    return ArchiveTask(**base)


def test_due_when_time_matches_and_not_fired_today():
    now = datetime(2026, 8, 27, 2, 0, 30)
    t = _task(schedule_enabled=True, schedule_time="02:00")
    assert due_tasks([t], now, {}) == [t]


def test_not_due_after_fired_today():
    now = datetime(2026, 8, 27, 2, 0, 30)
    t = _task(schedule_enabled=True, schedule_time="02:00")
    assert due_tasks([t], now, {1: "2026-08-27"}) == []
    # 次日同时间再次触发
    tomorrow = datetime(2026, 8, 28, 2, 0, 10)
    assert due_tasks([t], tomorrow, {1: "2026-08-27"}) == [t]


def test_not_due_when_time_mismatch_or_disabled():
    now = datetime(2026, 8, 27, 3, 0, 0)
    t = _task(schedule_enabled=True, schedule_time="02:00")
    assert due_tasks([t], now, {}) == []
    now2 = datetime(2026, 8, 27, 2, 0, 0)
    assert due_tasks([_task(schedule_enabled=False)], now2, {}) == []
    assert due_tasks([_task(enabled=False, schedule_enabled=True)], now2, {}) == []
