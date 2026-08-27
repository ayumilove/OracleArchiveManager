"""Oracle Client 架构预检测试：伪造 PE 头验证位数判定与指引文案。"""
import struct

import pytest

from oracle_archive_manager.oracle.client_arch import (
    check_client_arch,
    find_oci_dll,
    pe_bits,
    process_bits,
)


def _fake_pe(machine: int) -> bytes:
    """构造最小 PE：MZ 头 + 0x3C 处偏移 + PE 签名 + Machine 字段。"""
    buf = bytearray(b"MZ" + b"\0" * (0x3C - 2))
    buf += struct.pack("<I", 0x40)
    buf += b"PE\0\0" + struct.pack("<H", machine)
    return bytes(buf)


@pytest.fixture()
def client_dirs(tmp_path):
    x86 = tmp_path / "client32"
    x64 = tmp_path / "client64"
    x86.mkdir()
    x64.mkdir()
    (x86 / "oci.dll").write_bytes(_fake_pe(0x14C))
    (x64 / "oci.dll").write_bytes(_fake_pe(0x8664))
    return x86, x64


def test_pe_bits(client_dirs):
    x86, x64 = client_dirs
    assert pe_bits(x86 / "oci.dll") == 32
    assert pe_bits(x64 / "oci.dll") == 64


def test_pe_bits_invalid(tmp_path):
    bad = tmp_path / "notpe.dll"
    bad.write_bytes(b"hello world")
    assert pe_bits(bad) is None


def test_find_oci_dll_via_path(client_dirs, monkeypatch):
    x86, _ = client_dirs
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setenv("PATH", str(x86))
    assert find_oci_dll() == x86 / "oci.dll"


def test_check_client_arch_mismatch(client_dirs, monkeypatch):
    """PATH 指向 32 位客户端时，64 位进程应得到明确指引。"""
    x86, _ = client_dirs
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setenv("PATH", str(x86))
    if process_bits() == 64:
        msg = check_client_arch()
        assert msg is not None
        assert "32" in msg and "64 位" in msg
    else:
        assert check_client_arch() is None


def test_check_client_arch_match(client_dirs, monkeypatch):
    _, x64 = client_dirs
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setenv("PATH", str(x64))
    if process_bits() == 64:
        assert check_client_arch() is None


def test_check_client_arch_missing(monkeypatch, tmp_path):
    """找不到客户端时不拦截，交给 init 阶段报“未检测到”。"""
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert check_client_arch() is None
