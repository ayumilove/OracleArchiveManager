"""Oracle Client 架构预检：程序为 64 位，32 位 OCI 库无法加载，见 12 §2。

Qt6/PySide6 无 32 位 Windows 发行版，本程序只能发布 64 位；
若客户机安装的是 32 位 Oracle Client（常见于老环境），Thick Mode
会在 init 阶段报 DPI-1047。这里提前解析 oci.dll 的 PE 头判断位数，
给出明确指引，而不是让用户面对难懂的加载错误。
"""
from __future__ import annotations

import os
import platform
import struct
from pathlib import Path

_OCI_NAMES = ("oci.dll", "oraociei*.dll")


def process_bits() -> int:
    """当前进程位数（发布产物固定 64）。"""
    return 64 if platform.architecture()[0] == "64bit" else 32


def pe_bits(path: Path) -> int | None:
    """读取 PE 头 Machine 字段判断 DLL 位数；解析失败返回 None。"""
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return None
            f.seek(0x3C)
            f.seek(struct.unpack("<I", f.read(4))[0])
            if f.read(4) != b"PE\0\0":
                return None
            machine = struct.unpack("<H", f.read(2))[0]
    except OSError:
        return None
    return {0x14C: 32, 0x8664: 64}.get(machine)


def _find_in(directory: Path) -> Path | None:
    for name in _OCI_NAMES:
        hits = sorted(directory.glob(name))
        if hits:
            return hits[0]
    return None


def find_oci_dll(extra_dirs: list[str] | None = None) -> Path | None:
    """按 oracledb 的查找习惯定位 oci.dll：显式目录 → ORACLE_HOME → PATH。"""
    candidates: list[Path] = []
    for d in extra_dirs or []:
        candidates.append(Path(d))
    home = os.environ.get("ORACLE_HOME")
    if home:
        candidates.append(Path(home))
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d.strip():
            candidates.append(Path(d))
    for d in candidates:
        try:
            if d.is_dir():
                found = _find_in(d)
                if found:
                    return found
        except OSError:
            continue
    return None


def check_client_arch(lib_dir: str | None = None) -> str | None:
    """Thick Mode 前置检查：位数不匹配时返回错误说明，正常返回 None。"""
    dll = find_oci_dll([lib_dir] if lib_dir else None)
    if dll is None:
        return None  # 交给 init 阶段报“未检测到客户端”
    bits = pe_bits(dll)
    if bits is None or bits == process_bits():
        return None
    return (
        f"检测到 {bits} 位 Oracle Client（{dll}），与本程序 {process_bits()} 位不匹配。\n"
        "请安装 64 位 Oracle Instant Client（Basic 包），并在系统环境变量 PATH "
        "中优先指向 64 位客户端目录后重启程序。\n"
        "提示：Qt6 不再提供 32 位发行版，本程序无法适配 32 位客户端。"
    )
