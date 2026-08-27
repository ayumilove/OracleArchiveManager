"""Oracle 连接层：连接测试与版本获取，见 05_ORACLE_STRATEGY.md §1。"""
from __future__ import annotations

import oracledb

from .client_arch import check_client_arch

_thick_ready = False

_ARCH_HINT = (
    "常见原因：Oracle Client 为 32 位，与本程序（64 位）不匹配。"
    "请安装 64 位 Oracle Instant Client 并确保其目录在 PATH 中。"
)


def build_dsn(host: str, port: int, service_name: str) -> str:
    return f"{host}:{port}/{service_name}"


def ensure_thick_mode() -> bool:
    """Oracle 11g 需 Thick Mode + 兼容 Oracle Client；初始化失败返回 False。"""
    global _thick_ready
    if _thick_ready:
        return True
    arch_err = check_client_arch()
    if arch_err:
        raise RuntimeError(arch_err)
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
    if thick:
        try:
            ok = ensure_thick_mode()
        except RuntimeError as e:
            raise RuntimeError(str(e)) from None
        if not ok:
            raise RuntimeError(
                "Thick Mode 初始化失败：未检测到可用的 Oracle Client 库（Oracle 11g 必需）。" + _ARCH_HINT
            )
    return oracledb.connect(
        user=username, password=password, dsn=build_dsn(host, port, service_name)
    )
