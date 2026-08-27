"""界面文案中文化映射：仅展示层翻译，领域枚举值保持英文不变。"""
from __future__ import annotations

STATUS_ZH = {
    # Run 状态
    "RUNNING": "运行中", "PAUSING": "暂停中", "PAUSED": "已暂停",
    "COPY_COMPLETED": "复制完成", "VERIFIED": "已验证", "FAILED": "失败",
    "CANCELED": "已取消", "COMPLETED": "已完成",
    # Batch 状态
    "PENDING": "待处理", "COPYING": "复制中", "COPIED": "已复制",
    "VERIFYING": "验证中", "PURGING": "清理中",
}

LEVEL_ZH = {"INFO": "信息", "WARN": "警告", "ERROR": "错误", "DEBUG": "调试"}

STAGE_ZH = {
    "RUN": "运行", "COPY": "复制", "VERIFY": "验证",
    "PURGE": "清理", "PREPARE": "准备", "SCHED": "调度",
}

VERIFY_ZH = {"COUNT": "计数校验", "PK": "主键校验", "HASH": "哈希校验"}


def status_zh(value: str) -> str:
    return STATUS_ZH.get(value, value)


def level_zh(value: str) -> str:
    return LEVEL_ZH.get(value, value)


def stage_zh(value: str) -> str:
    return STAGE_ZH.get(value, value)
