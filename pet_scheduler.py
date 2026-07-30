"""桌宠待机动作与定时提醒调度。"""

from __future__ import annotations

import random

from PySide6.QtCore import QObject, QTimer, Signal

IDLE_MIN_MS = 20_000
IDLE_MAX_MS = 60_000
REMINDER_TICK_MS = 20 * 60 * 1000
REMINDER_MESSAGES = (
    "记得站起来活动活动哦",
    "记得喝水",
)


class PetScheduler(QObject):
    """调度随机待机动作，以及每 20 分钟交替出现的两个提醒。"""

    idle_due = Signal()
    reminder_due = Signal(str)

    def __init__(
        self,
        *,
        idle_min_ms: int = IDLE_MIN_MS,
        idle_max_ms: int = IDLE_MAX_MS,
        reminder_tick_ms: int = REMINDER_TICK_MS,
        rng: random.Random | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if idle_min_ms <= 0 or idle_max_ms < idle_min_ms:
            raise ValueError("待机动画时间范围无效")
        if reminder_tick_ms <= 0:
            raise ValueError("提醒间隔必须为正数")

        self._idle_min_ms = idle_min_ms
        self._idle_max_ms = idle_max_ms
        self._reminder_tick_ms = reminder_tick_ms
        self._rng = rng or random.Random()
        self._started = False
        self._idle_enabled = True
        self._reminders_enabled = True
        self._reminder_index = 0

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(self._reminder_tick_ms)
        self._reminder_timer.timeout.connect(self._on_reminder_timeout)

    @property
    def reminders_enabled(self) -> bool:
        return self._reminders_enabled

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.reset_idle_countdown()
        if self._reminders_enabled:
            self._reminder_timer.start()

    def stop(self) -> None:
        self._started = False
        self._idle_timer.stop()
        self._reminder_timer.stop()

    def set_idle_enabled(self, enabled: bool) -> None:
        self._idle_enabled = enabled
        if enabled:
            self.reset_idle_countdown()
        else:
            self._idle_timer.stop()

    def set_reminders_enabled(self, enabled: bool) -> None:
        if enabled == self._reminders_enabled:
            return
        self._reminders_enabled = enabled
        self._reminder_timer.stop()
        if self._started and enabled:
            self._reminder_timer.start()

    def reset_idle_countdown(self) -> None:
        self._idle_timer.stop()
        if not self._started or not self._idle_enabled:
            return
        interval = self._rng.randint(self._idle_min_ms, self._idle_max_ms)
        self._idle_timer.start(interval)

    def _on_idle_timeout(self) -> None:
        self.idle_due.emit()
        self.reset_idle_countdown()

    def _on_reminder_timeout(self) -> None:
        message = REMINDER_MESSAGES[self._reminder_index % len(REMINDER_MESSAGES)]
        self._reminder_index += 1
        self.reminder_due.emit(message)
