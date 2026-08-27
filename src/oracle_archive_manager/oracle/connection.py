"""Oracle 连接层：连接测试与版本获取，见 05_ORACLE_STRATEGY.md §1。"""
from __future__ import annotations

import oracledb

_thick_ready = False


def build_dsn(host: str, port: int, service_name: str) -> str:
    return f"{host}:{port}/{service_name}"


def ensure_thick_mode() -> bool:
    """Oracle 11g 需 Thick Mode + 兼容 Oracle Client；初始化失败返回 False。"""
    global _thick_ready
    if _thick_ready:
        return True
    try:
        oracledb.init_oracle_client()
        _thick_ready = True
        return True
    except oracledb.ProgrammingError:
        # 已在其他模式初始化过
        return True
    except Exception:
        return False


def test_connection(
    *,
    host: str,
    port: int,
    service_name: str,
    username: str,
    password: str,
    thick: bool = False,
):
    """测试连接并返回 Oracle 版本号；失败抛异常。"""
    with connect(
        host=host, port=port, service_name=service_name,
        username=username, password=password, thick=thick,
    ) as conn:
        return conn.version


def connect(
    *,
    host: str,
    port: int,
    service_name: str,
    username: str,
    password: str,
    thick: bool = False,
):
    """建立连接（调用方负责 close）。"""
    if thick and not ensure_thick_mode():
        raise RuntimeError("Thick Mode 初始化失败：未检测到 Oracle Client 库（Oracle 11g 必需）")
    return oracledb.connect(
        user=username, password=password, dsn=build_dsn(host, port, service_name)
    )
