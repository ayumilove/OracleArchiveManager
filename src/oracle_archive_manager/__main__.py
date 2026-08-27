"""包入口：供 `python -m oracle_archive_manager` 与 Nuitka 发布编译使用。

Nuitka 直接编译 main.py 会按顶层脚本处理，导致包内相对导入失败；
编译包内 __main__.py 则保留包上下文（__package__），相对导入正常。
"""
import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
