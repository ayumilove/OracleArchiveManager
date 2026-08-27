"""update_checker 版本比对与更新脚本测试。"""
import os

from oracle_archive_manager.services.update_checker import (
    build_updater_script,
    has_update,
    parse_version,
)


def test_parse_version():
    assert parse_version("v0.2.0") == (0, 2, 0)
    assert parse_version("0.2.0.1") == (0, 2, 0, 1)
    assert parse_version("  v10.3 ") == (10, 3)
    assert parse_version("") is None
    assert parse_version("nightly") is None
    assert parse_version(None) is None  # type: ignore[arg-type]


def test_has_update_true():
    assert has_update("0.1.0", "0.2.0")
    assert has_update("0.1.0", "v0.1.1")
    assert has_update("0.1", "0.1.1")  # 位数不齐按位补零
    assert has_update("0.9.9", "1.0.0")


def test_has_update_false():
    assert not has_update("0.2.0", "0.2.0")
    assert not has_update("0.2.0", "v0.2")  # 相等（补零后）
    assert not has_update("1.0.0", "0.9.9")
    assert not has_update("abc", "1.0.0")  # 无法解析视为无更新
    assert not has_update("1.0.0", "abc")


def test_build_updater_script(tmp_path):
    new_exe = str(tmp_path / "OracleArchiveManager.exe")
    bat = build_updater_script(new_exe)
    assert os.path.dirname(bat) == str(tmp_path)
    assert bat.endswith("update_oam.bat")
    content = open(bat, encoding="mbcs" if os.name == "nt" else "utf-8").read()
    assert "SRC=" + new_exe in content
    assert "copy /Y" in content
    assert ":wait_loop" in content  # 必须先等主程序退出再替换
