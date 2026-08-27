"""控制库连接表 CRUD。"""
from __future__ import annotations

from ..domain.connection import ArchiveConnection, ConnectionRole
from ..storage.sqlite import ControlDB
from ..utils.time import now_iso


def _row_to_model(row) -> ArchiveConnection:
    return ArchiveConnection(
        id=row["id"],
        name=row["name"],
        role=ConnectionRole(row["role"]),
        host=row["host"],
        port=row["port"],
        service_name=row["service_name"],
        username=row["username"],
        credential_ref=row["credential_ref"],
        oracle_version=row["oracle_version"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ConnectionRepository:
    def __init__(self, db: ControlDB) -> None:
        self.db = db

    def list_all(self) -> list[ArchiveConnection]:
        conn = self.db.connect()
        try:
            rows = conn.execute("SELECT * FROM archive_connection ORDER BY id").fetchall()
            return [_row_to_model(r) for r in rows]
        finally:
            conn.close()

    def get(self, connection_id: int) -> ArchiveConnection | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM archive_connection WHERE id = ?", (connection_id,)
            ).fetchone()
            return _row_to_model(row) if row else None
        finally:
            conn.close()

    def create(self, c: ArchiveConnection) -> ArchiveConnection:
        now = now_iso()
        conn = self.db.connect()
        try:
            cur = conn.execute(
                """INSERT INTO archive_connection
                   (name, role, host, port, service_name, username,
                    credential_ref, oracle_version, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    c.name, c.role.value, c.host, c.port, c.service_name,
                    c.username, c.credential_ref, c.oracle_version,
                    int(c.enabled), now, now,
                ),
            )
            conn.commit()
            return c.model_copy(update={"id": cur.lastrowid, "created_at": now, "updated_at": now})
        finally:
            conn.close()

    def update(self, c: ArchiveConnection) -> None:
        now = now_iso()
        conn = self.db.connect()
        try:
            conn.execute(
                """UPDATE archive_connection
                   SET name=?, role=?, host=?, port=?, service_name=?, username=?,
                       credential_ref=?, oracle_version=?, enabled=?, updated_at=?
                   WHERE id=?""",
                (
                    c.name, c.role.value, c.host, c.port, c.service_name,
                    c.username, c.credential_ref, c.oracle_version,
                    int(c.enabled), now, c.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, connection_id: int) -> None:
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM archive_connection WHERE id = ?", (connection_id,))
            conn.commit()
        finally:
            conn.close()
