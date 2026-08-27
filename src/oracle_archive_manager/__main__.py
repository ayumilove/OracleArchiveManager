"""包入口：供 `python -m oracle_archive_manager` 与 Nuitka 发布编译使用。

Nuitka 直接编译 main.py 会按顶层脚本处理，导致包内相对导入失败；
编译包目录 + --python-flag=-m 则保留包上下文（__package__）。
"""
import os
import sys


def _ensure_std_handles() -> None:
    """GUI 子系统无控制台时标准句柄无效，重定向到 NUL，避免早期写入崩溃。"""
    for name in ("stdin", "stdout", "stderr"):
        f = getattr(sys, name, None)
        ok = f is not None
        if ok:
            try:
                f.fileno()
            except (OSError, ValueError, AttributeError):
                ok = False
        if not ok:
            setattr(sys, name, open(os.devnull, "w"))


_ensure_std_handles()

from .main import main  # noqa: E402  必须在句柄修复后导入（依赖库会触碰 stderr）

if __name__ == "__main__":
    sys.exit(main())
