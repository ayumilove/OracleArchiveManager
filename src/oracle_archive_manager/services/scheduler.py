"""应用内调度器：任务每日定点自动创建并启动 Run（P2 调度任务）。

设计：QTimer 周期 tick；HH:MM 匹配且当日未触发才点火；
任务禁用/已有活动 Run 时跳过并记审计日志（不补跑，避免白天意外启动）。
"""
from __future__ import annotations

from datetime import datetime

from loguru import logger
from PySide6.QtCore import QObject, QTimer

from ..domain.task import ArchiveTask


def due_tasks(tasks: list[ArchiveTask], now: datetime,
              last_fire: dict[int, str]) -> list[ArchiveTask]:
    """纯函数：此刻应触发的任务（启用 + 时间匹配 + 当日未触发）。"""
    hhmm = now.strftime("%H:%M")
    today = now.date().isoformat()
    return [t for t in tasks
            if t.enabled and t.schedule_enabled and t.schedule_time == hhmm
            and last_fire.get(t.id or -1) != today]


class Scheduler(QObject):
    def __init__(self, controller, interval_ms: int = 20_000, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._last_fire: dict[int, str] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = datetime.now()
        for t in due_tasks(self.controller.list_tasks(), now, self._last_fire):
            self._last_fire[t.id or -1] = now.date().isoformat()
            try:
                run_id = self.controller.start_run(t.id)
            except Exception as exc:
                # 已有活动 Run / 连接失败等：跳过本次，不影响其他任务
                logger.warning(f"调度跳过任务 {t.task_name}：{exc}")
                self.controller.runs.append_log(
                    None, None, "WARN", "SCHED",
                    f"调度跳过任务 {t.task_name}（{t.schedule_time}）：{exc}")
                continue
            self.controller.runs.append_log(
                run_id, None, "INFO", "SCHED",
                f"调度触发：每日 {t.schedule_time} 自动启动 {run_id}")
            logger.info(f"调度触发任务 {t.task_name} → {run_id}")
