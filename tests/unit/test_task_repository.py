from oracle_archive_manager.domain.task import ArchiveTask, VerifyMode
from oracle_archive_manager.repositories.task_repository import TaskRepository
from oracle_archive_manager.storage.sqlite import ControlDB


def _make() -> ArchiveTask:
    return ArchiveTask(
        task_name="T1",
        source_connection_id=1,
        source_schema="PROD",
        source_table="ORDERS_HIST",
        target_connection_id=2,
        target_schema="ARCH",
        target_table="ORDERS_HIST",
        archive_column="CREATION_DATE",
        keep_months=24,
        key_columns=["ID"],
    )


def test_task_crud(tmp_path):
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    repo = TaskRepository(db)

    created = repo.create(_make())
    assert created.id is not None

    got = repo.get(created.id)
    assert got.key_columns == ["ID"]
    assert got.verify_mode is VerifyMode.PK

    repo.update(got.model_copy(update={"batch_size": 10000, "key_columns": ["ID", "NO"]}))
    got2 = repo.get(created.id)
    assert got2.batch_size == 10000
    assert got2.key_columns == ["ID", "NO"]

    assert len(repo.list_all()) == 1
    repo.delete(created.id)
    assert repo.list_all() == []
