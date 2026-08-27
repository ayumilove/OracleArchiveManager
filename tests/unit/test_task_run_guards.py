"""禁用任务、Safe Stop 与全局日志过滤的行为把关。"""
import pytest

from oracle_archive_manager.app.controller import AppController
from oracle_archive_manager.domain.run import ArchiveRun, RunStatus
from oracle_archive_manager.domain.task import ArchiveTask
from oracle_archive_manager.storage.sqlite import ControlDB
from oracle_archive_manager.utils.config import AppConfig


def _ctrl(tmp_path) -> AppController:
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    return AppController(db, AppConfig(tmp_path / "settings.json"))


def _seed_task(ctrl: AppController) -> ArchiveTask:
    return ctrl.tasks.create(ArchiveTask(
        task_name="T", source_connection_id=1, source_schema="S",
        source_table="T1", target_connection_id=2,
        target_schema="S", target_table="T1", key_columns=["ID"],
    ))


def _seed_run(ctrl: AppController, task_id: int, status: RunStatus) -> str:
    ctrl.runs.create_run(ArchiveRun(
        run_id="RUN_G", task_id=task_id, task_snapshot={},
        cutoff_value="", archive_condition="", expected_rows=1,
        status=status, start_time="t0",
    ))
    return "RUN_G"


def test_disabled_task_cannot_create_run(tmp_path):
    ctrl = _ctrl(tmp_path)
    t = _seed_task(ctrl)
    ctrl.toggle_task_enabled(t.id)
    assert ctrl.tasks.get(t.id).enabled is False
    with pytest.raises(RuntimeError):
        ctrl.create_run(t.id)
    ctrl.toggle_task_enabled(t.id)
    assert ctrl.tasks.get(t.id).enabled is True


def test_cancel_run_requires_paused(tmp_path):
    ctrl = _ctrl(tmp_path)
    t = _seed_task(ctrl)
    _seed_run(ctrl, t.id, RunStatus.RUNNING)
    # 有存活执行线程的 RUNNING：Safe Stop 必须先暂停
    ctrl._workers["RUN_G"] = object()
    with pytest.raises(RuntimeError):
        ctrl.cancel_run("RUN_G")
    # 孤儿 RUNNING（无存活线程，如进程被关）：可直接安全取消
    ctrl._workers.pop("RUN_G")
    ctrl.cancel_run("RUN_G")
    assert ctrl.runs.get_run("RUN_G").status is RunStatus.CANCELED
    # PAUSED → CANCELED，已复制批次保留（重新造一个 PAUSED Run）
    ctrl.runs.update_run("RUN_G", status=RunStatus.PAUSED)
    ctrl.cancel_run("RUN_G")
    assert ctrl.runs.get_run("RUN_G").status is RunStatus.CANCELED


def test_recent_logs_filter(tmp_path):
    ctrl = _ctrl(tmp_path)
    t = _seed_task(ctrl)
    _seed_run(ctrl, t.id, RunStatus.RUNNING)
    ctrl.runs.append_log("RUN_G", None, "INFO", "RUN", "m1")
    ctrl.runs.append_log("RUN_G", None, "ERROR", "PURGE", "m2")
    assert len(ctrl.recent_logs()) == 2
    assert len(ctrl.recent_logs(stage="PURGE")) == 1
    assert len(ctrl.recent_logs(level="ERROR", stage="PURGE")) == 1
    assert len(ctrl.recent_logs(run_id="OTHER")) == 0
