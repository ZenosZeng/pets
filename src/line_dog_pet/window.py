"""透明桌宠窗口与鼠标交互。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QContextMenuEvent,
    QHideEvent,
    QMouseEvent,
    QMoveEvent,
    QRegion,
    QShowEvent,
)
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

from .animator import PetAnimator
from .scheduler import REMINDER_MESSAGES
from .state import PetState, random_switch_state


class PetWindow(QWidget):
    """无边框、透明、置顶的桌宠主窗口。"""

    state_changed = Signal(object)
    paused_changed = Signal(bool)
    visibility_changed = Signal(bool)
    position_changed = Signal(QPoint)
    scale_changed = Signal(int)
    user_interacted = Signal()
    reminder_requested = Signal(str)

    CANVAS_SIZE = QSize(154, 154)
    DEFAULT_SCALE_PERCENT = 100
    MIN_SCALE_PERCENT = 50
    MAX_SCALE_PERCENT = 200
    SCALE_STEP_PERCENT = 10
    SCREEN_MARGIN = 24

    def __init__(
        self,
        initial_state: PetState = PetState.XIAOBAI,
        initial_scale_percent: int = DEFAULT_SCALE_PERCENT,
    ) -> None:
        super().__init__()
        self._current_state = initial_state
        self._scale_percent = self.normalize_scale_percent(
            initial_scale_percent
        )
        self._canvas_size = self.canvas_size_for_scale(self._scale_percent)
        self._press_global_position: QPoint | None = None
        self._window_position_at_press = QPoint()
        self._dragged = False
        self._user_paused = False
        self._pending_hit_region = QRegion()
        self._initial_position_applied = False

        self.setWindowTitle("线条小狗桌宠")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(self._canvas_size)

        self._label = QLabel(self)
        self._label.setFixedSize(self._canvas_size)
        # 鼠标事件交给父窗口，保证图片区域可拖动、可点击。
        self._label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._label)

        self._animator = PetAnimator(self._label, self._canvas_size, self)
        self._animator.hit_region_changed.connect(self._set_hit_region)
        self.switch_state(self._current_state)

    @classmethod
    def normalize_scale_percent(cls, value: object) -> int:
        """Clamp a saved scale to a supported 10% step."""

        try:
            percent = int(value)
        except (TypeError, ValueError):
            percent = cls.DEFAULT_SCALE_PERCENT
        step = cls.SCALE_STEP_PERCENT
        percent = ((percent + step // 2) // step) * step
        return min(cls.MAX_SCALE_PERCENT, max(cls.MIN_SCALE_PERCENT, percent))

    @classmethod
    def canvas_size_for_scale(cls, scale_percent: int) -> QSize:
        """Return the pixel canvas for a normalized percentage."""

        scale_percent = cls.normalize_scale_percent(scale_percent)
        width = (cls.CANVAS_SIZE.width() * scale_percent + 50) // 100
        height = (cls.CANVAS_SIZE.height() * scale_percent + 50) // 100
        return QSize(width, height)

    @property
    def current_state(self) -> PetState:
        return self._current_state

    @property
    def current_animation_path(self) -> Path | None:
        return self._animator.current_animation_path

    @property
    def is_paused(self) -> bool:
        return self._user_paused

    @property
    def scale_percent(self) -> int:
        return self._scale_percent

    @property
    def canvas_size(self) -> QSize:
        return QSize(self._canvas_size)

    def switch_state(self, state: PetState) -> None:
        """立即切换到指定状态。"""

        self._current_state = state
        self._animator.set_state(state)
        self.setToolTip(state.display_name)
        self.state_changed.emit(state)

    def switch_animation(self) -> None:
        """保持当前角色状态，只随机换一个动作。"""

        self._animator.set_state(self._current_state)

    def switch_to_random_state(self) -> None:
        """随机切换状态，并避免连续显示同一个状态。"""

        self.switch_state(random_switch_state(self._current_state))

    def set_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if paused == self._user_paused:
            return
        self._user_paused = paused
        self._update_animation_playback()
        self.paused_changed.emit(paused)

    def set_scale_percent(self, scale_percent: int) -> None:
        """Resize around the pet's bottom center and keep it on-screen."""

        scale_percent = self.normalize_scale_percent(scale_percent)
        if scale_percent == self._scale_percent:
            return

        old_size = self.size()
        anchor = QPoint(
            self.x() + old_size.width() // 2,
            self.y() + old_size.height(),
        )
        new_size = self.canvas_size_for_scale(scale_percent)
        target = QPoint(
            anchor.x() - new_size.width() // 2,
            anchor.y() - new_size.height(),
        )

        self.clearMask()
        self._scale_percent = scale_percent
        self._canvas_size = QSize(new_size)
        self.setFixedSize(new_size)
        self._animator.set_canvas_size(new_size)
        self.move(self._clamp_position_to_screen(target, new_size, anchor))
        self.scale_changed.emit(scale_percent)

    def increase_scale(self) -> None:
        self.set_scale_percent(
            self._scale_percent + self.SCALE_STEP_PERCENT
        )

    def decrease_scale(self) -> None:
        self.set_scale_percent(
            self._scale_percent - self.SCALE_STEP_PERCENT
        )

    def reset_scale(self) -> None:
        self.set_scale_percent(self.DEFAULT_SCALE_PERCENT)

    def request_activity_reminder(self) -> None:
        self.reminder_requested.emit(REMINDER_MESSAGES[0])

    def request_water_reminder(self) -> None:
        self.reminder_requested.emit(REMINDER_MESSAGES[1])

    def restore_position(self, position: QPoint) -> bool:
        """恢复仍位于任一可用屏幕内的位置。"""

        target = QRect(position, self.size())
        screens = QApplication.screens()
        if not any(screen.availableGeometry().intersects(target) for screen in screens):
            return False
        self.move(position)
        self._initial_position_applied = True
        return True

    def move_to_bottom_right(self) -> None:
        """将桌宠移动到当前屏幕工作区的右下角附近。"""

        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        x = area.x() + area.width() - self.width() - self.SCREEN_MARGIN
        y = area.y() + area.height() - self.height() - self.SCREEN_MARGIN
        self.move(max(area.x(), x), max(area.y(), y))

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._schedule_initial_position()
        self._update_animation_playback()
        self.visibility_changed.emit(True)

    def hideEvent(self, event: QHideEvent) -> None:
        self._animator.set_paused(True)
        self.visibility_changed.emit(False)
        super().hideEvent(event)

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.position_changed.emit(self.pos())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global_position = event.globalPosition().toPoint()
            self._window_position_at_press = self.pos()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._press_global_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = event.globalPosition().toPoint() - self._press_global_position
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._dragged = True
            if self._dragged:
                self.move(self._window_position_at_press + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_global_position is not None
        ):
            if not self._dragged:
                self.switch_to_random_state()
            self.user_interacted.emit()
            self._press_global_position = None
            self._dragged = False
            self._apply_hit_region()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self._create_context_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()
        event.accept()

    def _create_context_menu(self) -> QMenu:
        """Build the flat pet menu; separated for quick integration tests."""

        menu = QMenu(self)
        state_actions = (
            ("切换到小白", PetState.XIAOBAI),
            ("切换到小鸡毛", PetState.XIAOJIMAO),
            ("切换到一起", PetState.TOGETHER),
        )

        for text, state in state_actions:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(state == self._current_state)
            action.triggered.connect(
                lambda _checked=False, target=state: self.switch_state(target)
            )

        menu.addSeparator()
        animation_action = menu.addAction("换个动作")
        animation_action.triggered.connect(self.switch_animation)
        pause_action = menu.addAction("暂停动画")
        pause_action.setCheckable(True)
        pause_action.setChecked(self._user_paused)
        pause_action.triggered.connect(self.set_paused)
        menu.addSeparator()
        increase_action = menu.addAction("放大 10%")
        increase_action.setEnabled(
            self._scale_percent < self.MAX_SCALE_PERCENT
        )
        increase_action.triggered.connect(self.increase_scale)
        decrease_action = menu.addAction("缩小 10%")
        decrease_action.setEnabled(
            self._scale_percent > self.MIN_SCALE_PERCENT
        )
        decrease_action.triggered.connect(self.decrease_scale)
        reset_action = menu.addAction("恢复默认大小")
        reset_action.setEnabled(
            self._scale_percent != self.DEFAULT_SCALE_PERCENT
        )
        reset_action.triggered.connect(self.reset_scale)
        menu.addSeparator()
        activity_action = menu.addAction("测试活动提醒")
        activity_action.triggered.connect(self.request_activity_reminder)
        water_action = menu.addAction("测试喝水提醒")
        water_action.triggered.connect(self.request_water_reminder)
        menu.addSeparator()
        move_action = menu.addAction("回到右下角")
        move_action.triggered.connect(self.move_to_bottom_right)
        menu.addSeparator()
        quit_action = menu.addAction("退出程序")
        quit_action.triggered.connect(QApplication.quit)

        return menu

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)

    def stop(self) -> None:
        self._animator.stop()

    def _set_hit_region(self, region: QRegion) -> None:
        self._pending_hit_region = QRegion(region)
        if self._press_global_position is None:
            self._apply_hit_region()

    def _apply_hit_region(self) -> None:
        if QApplication.platformName() == "offscreen":
            return
        self.setMask(self._pending_hit_region)

    def _update_animation_playback(self) -> None:
        self._animator.set_paused(
            self._user_paused or not self.isVisible()
        )

    def _clamp_position_to_screen(
        self,
        position: QPoint,
        size: QSize,
        anchor: QPoint,
    ) -> QPoint:
        screen = QApplication.screenAt(anchor) or self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return position

        area = screen.availableGeometry()
        max_x = max(area.x(), area.right() - size.width() + 1)
        max_y = max(area.y(), area.bottom() - size.height() + 1)
        return QPoint(
            min(max(position.x(), area.x()), max_x),
            min(max(position.y(), area.y()), max_y),
        )

    def _schedule_initial_position(self) -> None:
        if self._initial_position_applied:
            return
        self._initial_position_applied = True
        QTimer.singleShot(0, self.move_to_bottom_right)
