from oracle_archive_manager.storage.sqlite import ControlDB


def test_migrate_creates_schema(tmp_path):
    db = ControlDB(tmp_path / "ctrl.db")
    db.migrate()
    db.migrate()  # 重复 migration 必须幂等
    conn = db.connect()
    try:
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "archive_connection", "archive_task", "archive_run",
            "archive_batch", "archive_log", "schema_migrations",
        } <= tables

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(archive_log)")}
        assert "operator" in cols

        indexes = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        assert {"idx_run_task", "idx_batch_status", "idx_log_run"} <= indexes
    finally:
        conn.close()


def test_wal_mode(tmp_path):
    db = ControlDB(tmp_path / "ctrl.db")
    conn = db.connect()
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
    finally:
        conn.close()
