"""连接领域模型，对应 ARCHIVE_CONNECTION，见 03_DATA_MODEL.md §1。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ConnectionRole(str, Enum):
    SOURCE = "SOURCE"
    TARGET = "TARGET"
    BOTH = "BOTH"


class ArchiveConnection(BaseModel):
    id: int | None = None
    name: str
    role: ConnectionRole = ConnectionRole.SOURCE
    host: str
    port: int = 1521
    service_name: str
    username: str
    credential_ref: str | None = None
    oracle_version: str | None = None
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None
