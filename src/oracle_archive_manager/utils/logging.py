"""统一日志（loguru）：文件日志按天滚动，见 12_RELEASE_DEPLOYMENT.md §5。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger


def app_data_dir() -> Path:
    """控制数据根目录：可用 OAM_DATA_DIR 覆盖，默认 %APPDATA%/OracleArchiveManager。"""
    override = os.environ.get("OAM_DATA_DIR")
    if override:
        return Path(override)
    return Path(os.environ["APPDATA"]) / "OracleArchiveManager"


def setup_logging(retention_days: int = 30) -> Path:
    """初始化控制台 + 文件日志，返回日志目录。"""
    log_dir = app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
    logger.add(
        log_dir / "oracle_archive_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention=f"{retention_days} days",
        compression="gz",  # P1：轮转后的日志自动 gzip 压缩
        encoding="utf-8",
        level="DEBUG",
        enqueue=True,
    )
    return log_dir
