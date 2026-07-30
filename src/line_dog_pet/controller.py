"""应用级控制：托盘、设置保存、待机动作与提醒。"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QSettings, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)

from .reminder_bubble import ReminderBubble
from .resources import animation_paths
from .scheduler import PetScheduler
from .state import PetState
from .window import PetWindow


class PetController(QObject):
    """协调桌宠窗口与长期运行所需的应用功能。"""

    def __init__(
        self,
        app: QApplication,
        *,
        settings: QSettings | None = None,
        tray_enabled: bool = True,
        scheduler: PetScheduler | None = None,
    ) -> None:
        super().__init__(app)
        self._app = app
        self._settings = settings if settings is not None else QSettings()
        self._shutting_down = False
        self._tray: QSystemTrayIcon | None = None
        self._state_actions: dict[PetState, QAction] = {}
        self._increase_scale_action: QAction | None = None
        self._decrease_scale_action: QAction | None = None
        self._reset_scale_action: QAction | None = None

        self.window = PetWindow(
            initial_state=self._load_state(),
            initial_scale_percent=self._load_scale_percent(),
        )
        self._restore_position()
        self._reminder_bubble = ReminderBubble()

        self.scheduler = (
            scheduler if scheduler is not None else PetScheduler(parent=self)
        )
        self.scheduler.idle_due.connect(self.window.switch_animation)
        self.scheduler.reminder_due.connect(self._show_reminder)

        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.setInterval(500)
        self._position_save_timer.timeout.connect(self._save_position)

        self.window.state_changed.connect(self._on_state_changed)
        self.window.paused_changed.connect(self._on_paused_changed)
        self.window.visibility_changed.connect(self._on_visibility_changed)
        self.window.position_changed.connect(self._on_position_changed)
        self.window.scale_changed.connect(self._on_scale_changed)
        self.window.user_interacted.connect(self.scheduler.reset_idle_countdown)
        self.window.reminder_requested.connect(self._show_reminder)

        reminders_enabled = self._settings.value(
            "reminders/enabled",
            True,
            type=bool,
        )
        self.scheduler.set_reminders_enabled(reminders_enabled)

        if tray_enabled and QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray()
        elif tray_enabled:
            self._app.setQuitOnLastWindowClosed(True)

        self._app.aboutToQuit.connect(self.shutdown)

    def start(self) -> None:
        self.window.show()
        if self._tray is not None:
            self._tray.show()
        self.scheduler.start()
        self._update_idle_enabled()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self.scheduler.stop()
        self._save_position()
        self._settings.setValue("pet/state", self.window.current_state.value)
        self._settings.setValue(
            "window/scale_percent",
            self.window.scale_percent,
        )
        self._settings.setValue(
            "reminders/enabled",
            self.scheduler.reminders_enabled,
        )
        self._settings.sync()
        if self._tray is not None:
            self._tray.hide()
        self._reminder_bubble.stop()
        self.window.stop()

    def toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()

    def _load_state(self) -> PetState:
        value = self._settings.value("pet/state", PetState.XIAOBAI.value)
        try:
            return PetState(str(value))
        except ValueError:
            return PetState.XIAOBAI

    def _load_scale_percent(self) -> int:
        value = self._settings.value(
            "window/scale_percent",
            PetWindow.DEFAULT_SCALE_PERCENT,
        )
        return PetWindow.normalize_scale_percent(value)

    def _restore_position(self) -> None:
        position = self._settings.value("window/position")
        if isinstance(position, QPoint):
            self.window.restore_position(position)

    def _create_tray(self) -> None:
        icon = self._create_icon()
        self._app.setWindowIcon(icon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("线条小狗桌宠")

        menu = QMenu()
        self._show_action = menu.addAction("隐藏桌宠")
        self._show_action.triggered.connect(self.toggle_window)

        self._pause_action = menu.addAction("暂停动画")
        self._pause_action.setCheckable(True)
        self._pause_action.triggered.connect(self.window.set_paused)

        change_action = menu.addAction("换个动作")
        change_action.triggered.connect(self.window.switch_animation)

        state_menu = menu.addMenu("切换角色")
        for state in PetState:
            action = state_menu.addAction(state.display_name)
            action.setCheckable(True)
            action.setChecked(state == self.window.current_state)
            action.triggered.connect(
                lambda _checked=False, target=state: self.window.switch_state(
                    target
                )
            )
            self._state_actions[state] = action

        menu.addSeparator()
        self._increase_scale_action = menu.addAction("放大 10%")
        self._increase_scale_action.triggered.connect(
            self.window.increase_scale
        )
        self._decrease_scale_action = menu.addAction("缩小 10%")
        self._decrease_scale_action.triggered.connect(
            self.window.decrease_scale
        )
        self._reset_scale_action = menu.addAction("恢复默认大小")
        self._reset_scale_action.triggered.connect(self.window.reset_scale)
        self._update_scale_actions()

        menu.addSeparator()
        self._reminder_action = menu.addAction("定时活动/喝水提醒")
        self._reminder_action.setCheckable(True)
        self._reminder_action.setChecked(self.scheduler.reminders_enabled)
        self._reminder_action.triggered.connect(
            self._set_reminders_enabled
        )

        activity_action = menu.addAction("测试活动提醒")
        activity_action.triggered.connect(
            self.window.request_activity_reminder
        )
        water_action = menu.addAction("测试喝水提醒")
        water_action.triggered.connect(self.window.request_water_reminder)

        move_action = menu.addAction("回到右下角")
        move_action.triggered.connect(self.window.move_to_bottom_right)

        menu.addSeparator()
        quit_action = menu.addAction("退出程序")
        quit_action.triggered.connect(self._app.quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        self._tray_menu = menu
        self._tray = tray

    def _create_icon(self) -> QIcon:
        for path in animation_paths(PetState.XIAOBAI):
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return QIcon(pixmap)
        return self._app.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )

    def _on_tray_activated(
        self,
        reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_window()

    def _on_state_changed(self, state: PetState) -> None:
        self._settings.setValue("pet/state", state.value)
        self.scheduler.reset_idle_countdown()
        for target, action in self._state_actions.items():
            action.setChecked(target == state)

    def _on_paused_changed(self, paused: bool) -> None:
        if self._tray is not None:
            self._pause_action.setChecked(paused)
        self._update_idle_enabled()

    def _on_visibility_changed(self, visible: bool) -> None:
        if self._tray is not None:
            self._show_action.setText("隐藏桌宠" if visible else "显示桌宠")
        if not visible:
            self._reminder_bubble.hide()
        self._update_idle_enabled()

    def _on_scale_changed(self, scale_percent: int) -> None:
        self._settings.setValue("window/scale_percent", scale_percent)
        self._reminder_bubble.reposition()
        self._update_scale_actions()

    def _update_scale_actions(self) -> None:
        if self._increase_scale_action is None:
            return
        scale_percent = self.window.scale_percent
        self._increase_scale_action.setEnabled(
            scale_percent < PetWindow.MAX_SCALE_PERCENT
        )
        self._decrease_scale_action.setEnabled(
            scale_percent > PetWindow.MIN_SCALE_PERCENT
        )
        self._reset_scale_action.setEnabled(
            scale_percent != PetWindow.DEFAULT_SCALE_PERCENT
        )

    def _update_idle_enabled(self) -> None:
        self.scheduler.set_idle_enabled(
            self.window.isVisible() and not self.window.is_paused
        )

    def _set_reminders_enabled(self, enabled: bool) -> None:
        self.scheduler.set_reminders_enabled(enabled)
        self._settings.setValue("reminders/enabled", enabled)

    def _show_reminder(self, message: str) -> None:
        subject = self.window.current_state.reminder_subject
        self._reminder_bubble.show_message(self.window, subject, message)

    def _on_position_changed(self, _position: QPoint) -> None:
        self._position_save_timer.start()
        if self._reminder_bubble.isVisible():
            self._reminder_bubble.reposition()

    def _save_position(self) -> None:
        self._settings.setValue("window/position", self.window.pos())
