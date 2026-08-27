"""统一时间工具。

控制库所有 TEXT 时间字段统一使用秒级 ISO-8601 UTC 字符串。
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def now_iso() -> str:
    """当前 UTC 时间，如 2026-08-27T07:51:14+00:00。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_local(ts: str | None) -> str:
    """控制库 UTC ISO 时间 → 本地时区展示，如 2026-08-27 11:40:16。

    存储层统一 UTC（见模块注释），仅展示层转换；解析失败时原样返回。
    """
    if not ts:
        return ""
    try:
        return (datetime.fromisoformat(ts).astimezone()
                .strftime("%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return ts


def compute_cutoff(now: date, keep_months: int) -> date:
    """归档边界：(now - keep_months 个月) 所在月的月初一日，见 04 §6。

    例：2026-08-27、keep_months=24 → 2024-08-01。
    """
    month_index = now.year * 12 + (now.month - 1) - keep_months
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)
