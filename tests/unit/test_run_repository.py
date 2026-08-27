from oracle_archive_manager.domain.run import ArchiveBatch, ArchiveRun, BatchStatus, RunStatus
from oracle_archive_manager.repositories.run_repository import RunRepository
from oracle_archive_manager.storage.sqlite import ControlDB


def _repo(tmp_path) -> RunRepository:
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    return RunRepository(db)


def _run(run_id="RUN_X", task_id=1) -> ArchiveRun:
    return ArchiveRun(
        run_id=run_id, task_id=task_id, task_snapshot={"task_name": "T"},
        cutoff_value="2024-08-01", archive_condition="CREATION_DATE < :cutoff",
        expected_rows=100, status=RunStatus.RUNNING, start_time="t0",
    )


def test_run_crud_and_active(tmp_path):
    repo = _repo(tmp_path)
    repo.create_run(_run())
    got = repo.get_run("RUN_X")
    assert got.status is RunStatus.RUNNING
    assert got.task_snapshot["task_name"] == "T"
    assert repo.active_run_for_task(1).run_id == "RUN_X"

    repo.update_run("RUN_X", status=RunStatus.VERIFIED, transferred_rows=50)
    got2 = repo.get_run("RUN_X")
    assert got2.status is RunStatus.VERIFIED
    assert got2.transferred_rows == 50
    # VERIFIED 仍属活动（等待人工 Purge），COMPLETED 才释放
    assert repo.active_run_for_task(1) is not None
    repo.update_run("RUN_X", status=RunStatus.COMPLETED)
    assert repo.active_run_for_task(1) is None


def test_batch_and_log(tmp_path):
    repo = _repo(tmp_path)
    repo.create_run(_run())
    repo.create_batch(ArchiveBatch(batch_id="RUN_X_B0001", run_id="RUN_X", batch_no=1,
                                   status=BatchStatus.PENDING, start_time="t1"))
    repo.update_batch("RUN_X_B0001", selection_snapshot={"prev_keys": None, "last_keys": [7]},
                      selected_rows=7, status=BatchStatus.VERIFIED)
    b = repo.list_batches("RUN_X")[0]
    assert b.selection_snapshot["last_keys"] == [7]
    assert b.status is BatchStatus.VERIFIED
    assert repo.last_batch("RUN_X").batch_no == 1

    repo.append_log("RUN_X", "RUN_X_B0001", "INFO", "COPY", "ok")
    logs = repo.logs_for_run("RUN_X")
    assert any(l["message"] == "ok" for l in logs)
    assert all(l["stage"] for l in logs)
