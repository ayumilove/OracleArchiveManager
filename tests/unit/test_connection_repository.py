from oracle_archive_manager.domain.connection import ArchiveConnection, ConnectionRole
from oracle_archive_manager.repositories.control_repository import ConnectionRepository
from oracle_archive_manager.storage.sqlite import ControlDB


def _make(name="PROD") -> ArchiveConnection:
    return ArchiveConnection(
        name=name, role=ConnectionRole.SOURCE, host="h", service_name="svc", username="u"
    )


def test_crud(tmp_path):
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    repo = ConnectionRepository(db)

    created = repo.create(_make())
    assert created.id is not None
    assert created.created_at

    got = repo.get(created.id)
    assert got is not None
    assert got.name == "PROD"
    assert got.role is ConnectionRole.SOURCE

    repo.update(got.model_copy(update={"host": "h2"}))
    assert repo.get(created.id).host == "h2"

    assert len(repo.list_all()) == 1
    repo.delete(created.id)
    assert repo.list_all() == []
