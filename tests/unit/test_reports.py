"""P1：报告 Markdown 导出 + 维护建议 + 控制库日志自动清理。"""
from datetime import datetime, timedelta, timezone

from oracle_archive_manager.app.controller import AppController
from oracle_archive_manager.domain.run import ArchiveBatch, ArchiveRun, RunStatus
from oracle_archive_manager.domain.task import ArchiveTask
from oracle_archive_manager.services import reports
from oracle_archive_manager.services.analyze_service import AnalyzeReport
from oracle_archive_manager.storage.sqlite import ControlDB
from oracle_archive_manager.utils.config import AppConfig


def _task() -> ArchiveTask:
    return ArchiveTask(
        task_name="T", source_connection_id=1, source_schema="S",
        source_table="ORDERS_HIST", target_connection_id=2,
        target_schema="S", target_table="ORDERS_HIST", key_columns=["ID"],
    )


def test_analyze_report_md_contains_advice():
    rep = AnalyzeReport(source_rows=100, eligible_rows=10, cutoff="2025-08-01")
    md = reports.analyze_report_md(_task(), rep)
    assert "Analyze Report" in md
    assert "ORDERS_HIST" in md
    assert "DBMS_STATS.GATHER_TABLE_STATS" in md
    assert "SHRINK SPACE CASCADE" in md


def test_run_report_md_sections():
    run = ArchiveRun(
        run_id="RUN_X", task_id=1, task_snapshot=_task().model_dump(mode="json"),
        cutoff_value="2025-08-01", archive_condition="C < :cutoff",
        expected_rows=10, status=RunStatus.COMPLETED, start_time="t0")
    b = ArchiveBatch(batch_id="B1", run_id="RUN_X", batch_no=1, selected_rows=10,
                     transferred_rows=10, verified_rows=10, status="VERIFIED")
    md = reports.run_report_md(run, [b], [], _task())
    assert "RUN_X" in md
    assert "批次明细" in md
    assert "维护建议" in md


def test_prune_logs_removes_only_old(tmp_path):
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    ctrl = AppController(db, AppConfig(tmp_path / "s.json"))
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    conn = db.connect()
    conn.execute(
        "INSERT INTO archive_log (run_id, batch_id, operator, log_time, level, stage, message, detail)"
        " VALUES (NULL, NULL, 't', ?, 'INFO', 'RUN', 'old', NULL)", (old,))
    conn.commit()
    conn.close()
    ctrl.runs.append_log("RUN_A", None, "INFO", "RUN", "new")
    assert ctrl.runs.prune_logs(90) == 1
    logs = ctrl.runs.recent_logs()
    assert len(logs) == 1
    assert logs[0]["message"] == "new"
