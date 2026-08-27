"""更新检查与 OTA 支持：对照 GitHub Releases 最新版本，见 12_RELEASE_DEPLOYMENT.md §9。

设计要点：
- 仅用标准库（urllib），不引入新依赖；网络失败静默降级，不影响主流程；
- 源码运行时只做版本提示，只有打包后的 exe（frozen）才允许就地替换（OTA）；
- OTA 采用「下载新版到临时目录 + 生成更新脚本」方式，规避运行中文件被占用。
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Callable

GITHUB_REPO = "ayumilove/OracleArchiveManager"
API_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
HTTP_TIMEOUT = 8
_CHUNK = 64 * 1024


@dataclass(frozen=True)
class UpdateInfo:
    """GitHub 最新 Release 的摘要。"""

    latest: str      # 最新版本号（已去掉 v 前缀）
    html_url: str    # Release 页面（引导手动下载）
    notes: str       # 发布说明
    asset_url: str   # exe 产物直链（缺失时为空）
    asset_name: str = ""


def parse_version(text: str) -> tuple[int, ...] | None:
    """解析 `v0.2.0` / `0.2.0.1` 为数字元组；无法解析返回 None。"""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", (text or "").strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def has_update(current: str, latest: str) -> bool:
    """latest 严格高于 current 时返回 True（按位补零比较）。"""
    cur, new = parse_version(current), parse_version(latest)
    if cur is None or new is None:
        return False
    n = max(len(cur), len(new))
    return cur + (0,) * (n - len(cur)) < new + (0,) * (n - len(new))


def fetch_latest_release(timeout: float = HTTP_TIMEOUT) -> UpdateInfo | None:
    """查询 GitHub Releases 最新版；网络失败或无发布时返回 None。"""
    req = urllib.request.Request(
        API_LATEST_URL,
        headers={"User-Agent": GITHUB_REPO, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    latest = parse_version(data.get("tag_name", ""))
    if latest is None:
        return None
    asset_url, asset_name = "", ""
    for asset in data.get("assets") or []:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            asset_url, asset_name = asset.get("browser_download_url", ""), name
            break
    return UpdateInfo(
        latest=".".join(str(p) for p in latest),
        html_url=data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases",
        notes=(data.get("body") or "").strip(),
        asset_url=asset_url,
        asset_name=asset_name,
    )


def is_frozen() -> bool:
    """Nuitka 打包后的 exe 才允许就地替换；源码运行只引导手动下载。"""
    return bool(getattr(sys, "frozen", False)) and os.path.isfile(sys.executable)


def download_asset(info: UpdateInfo,
                   progress: Callable[[int, int], None] | None = None) -> str:
    """下载新版 exe 到临时目录，返回下载路径；失败抛出异常。"""
    if not info.asset_url:
        raise RuntimeError("新版本没有可下载的构建产物")
    dest_dir = os.path.join(tempfile.gettempdir(), "OracleArchiveManagerUpdate")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, info.asset_name or "OracleArchiveManager.exe")
    tmp = dest + ".part"
    req = urllib.request.Request(info.asset_url, headers={"User-Agent": GITHUB_REPO})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(_CHUNK)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(tmp, dest)
    return dest


def build_updater_script(new_exe: str) -> str:
    """生成更新脚本：等主程序退出 → 覆盖旧 exe → 重启。返回脚本路径。

    运行中的 exe 被系统占用无法直接覆盖，必须退出后由外部脚本替换。
    """
    bat = os.path.join(os.path.dirname(new_exe), "update_oam.bat")
    script = f"""@echo off
setlocal
set "SRC={new_exe}"
set "DST={sys.executable}"
set "PID={os.getpid()}"
:wait_loop
timeout /t 1 /nobreak >nul
tasklist /FI "PID eq %PID%" /NH 2>nul | find "%PID%" >nul
if not errorlevel 1 goto wait_loop
copy /Y "%SRC%" "%DST%" >nul 2>&1
if errorlevel 1 goto fail
del "%SRC%" >nul 2>&1
start "" "%DST%"
goto end
:fail
echo Update failed: could not replace the executable. Please download manually.
pause
:end
del "%~f0"
"""
    # cmd 按系统 ANSI 代码页解析脚本；非 Windows（仅测试）退回 utf-8
    enc = "mbcs" if sys.platform == "win32" else "utf-8"
    with open(bat, "w", encoding=enc, errors="replace", newline="\r\n") as f:
        f.write(script)
    return bat
