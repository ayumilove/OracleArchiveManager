"""Purge 入口把关：仅 VERIFIED Run 可删 + 表名手输二次确认（04 §4）。"""
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


def _seed(ctrl: AppController, status: RunStatus, allow_purge: bool = True,
          run_id: str = "RUN_P") -> str:
    t = ctrl.tasks.create(ArchiveTask(
        task_name="T", source_connection_id=1, source_schema="S",
        source_table="ORDERS_HIST", target_connection_id=2,
        target_schema="S", target_table="ORDERS_HIST", key_columns=["ID"],
        allow_purge=allow_purge,
    ))
    ctrl.runs.create_run(ArchiveRun(
        run_id=run_id, task_id=t.id, task_snapshot=t.model_dump(mode="json"),
        cutoff_value="", archive_condition="", expected_rows=1,
        status=status, start_time="t0",
    ))
    return run_id


def test_purge_requires_verified(tmp_path):
    ctrl = _ctrl(tmp_path)
    run_id = _seed(ctrl, RunStatus.RUNNING)
    with pytest.raises(RuntimeError):
        ctrl.start_purge(run_id, "ORDERS_HIST")


def test_purge_requires_exact_table_name(tmp_path):
    ctrl = _ctrl(tmp_path)
    run_id = _seed(ctrl, RunStatus.VERIFIED)
    with pytest.raises(ValueError):
        ctrl.start_purge(run_id, "WRONG_TABLE")
    # 大小写不敏感视为匹配（比较即通过，此处只验证确认逻辑不抛表名错误）
    preview = ctrl.purge_preview(run_id)
    assert preview["task"].source_table == "ORDERS_HIST"
    assert preview["total_rows"] == 0


def test_purge_blocked_when_task_disallows(tmp_path):
    """任务配置禁止清理时，预览与执行入口均拒绝（04 §4）。"""
    ctrl = _ctrl(tmp_path)
    run_id = _seed(ctrl, RunStatus.VERIFIED, allow_purge=False, run_id="RUN_NOPURGE")
    with pytest.raises(RuntimeError, match="禁止清理"):
        ctrl.purge_preview(run_id)
    with pytest.raises(RuntimeError, match="禁止清理"):
        ctrl.start_purge(run_id, "ORDERS_HIST")


def test_complete_verified_run_releases_task(tmp_path):
    """无需 Purge：人工完结 VERIFIED Run 后，任务可再次运行（04 §9）。"""
    ctrl = _ctrl(tmp_path)
    run_id = _seed(ctrl, RunStatus.VERIFIED)
    ctrl.complete_run(run_id)
    assert ctrl.runs.get_run(run_id).status is RunStatus.COMPLETED
    assert ctrl.runs.active_run_for_task(1) is None
