"""SQLite 控制库连接与 migration 管理，见 03_DATA_MODEL.md。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..utils.time import now_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class ControlDB:
    """控制库（连接 / 任务 / Run / Batch / Log），控制面与数据面分离。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        # 多 Worker 线程并发读写控制库，见 03 §6 决策
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def migrate(self) -> None:
        """按文件名顺序执行未应用的 migration，重复调用幂等。"""
        conn = self.connect()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if sql_file.name in applied:
                    continue
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (sql_file.name, now_iso()),
                )
            conn.commit()
        finally:
            conn.close()
