"""凭据安全保存：Windows Credential Manager（keyring），见 07_SECURITY_SAFETY.md §7。

SQLite 仅保存 credential_ref，明文密码永不落盘。
"""
from __future__ import annotations

import uuid

import keyring

SERVICE = "OracleArchiveManager"


def new_credential_ref(name: str) -> str:
    return f"conn/{name}/{uuid.uuid4().hex[:8]}"


def store_credential(ref: str, password: str) -> None:
    keyring.set_password(SERVICE, ref, password)


def load_credential(ref: str) -> str | None:
    return keyring.get_password(SERVICE, ref)


def delete_credential(ref: str) -> None:
    try:
        keyring.delete_password(SERVICE, ref)
    except keyring.errors.PasswordDeleteError:
        pass
