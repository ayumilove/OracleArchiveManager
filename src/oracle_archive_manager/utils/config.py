"""本地配置（JSON），落 %APPDATA%/OracleArchiveManager/config/，见 12 §3。"""
from __future__ import annotations

import json
from pathlib import Path

from .logging import app_data_dir

DEFAULTS = {
    # Oracle 11g 不支持 Thin Mode，默认 Thick（需本机 Oracle Client）
    "thick_mode": True,
    "log_retention_days": 30,
    # P1：控制库 archive_log 自动清理保留天数
    "db_log_retention_days": 90,
}


class AppConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / "config" / "settings.json")
        self.values = dict(DEFAULTS)
        if self.path.exists():
            try:
                self.values.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass

    def get(self, key: str):
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self.values[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8"
        )
