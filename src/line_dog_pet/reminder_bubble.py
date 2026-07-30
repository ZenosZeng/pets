"""Lightweight reminder bubble displayed above the desktop pet."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QLabel, QWidget


class ReminderBubble(QWidget):
    """A non-activating speech bubble that follows the pet window."""

    DISPLAY_MS = 8_000
    MAX_TEXT_WIDTH = 250
    HORIZONTAL_PADDING = 16
    VERTICAL_PADDING = 12
    TAIL_HEIGHT = 13
    SCREEN_MARGIN = 8

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._anchor: QWidget | None = None
        self._tail_x = 0
        self._message = ""

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        font = QFont("Microsoft YaHei UI", 10)
        font.setWeight(QFont.Weight.Medium)
        self._label.setFont(font)
        self._label.setStyleSheet("color: #3b3836; background: transparent;")

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    @property
    def message(self) -> str:
        return self._message

    def show_message(
        self,
        anchor: QWidget,
        subject: str,
        message: str,
        duration_ms: int = DISPLAY_MS,
    ) -> None:
        """Show a character-specific reminder and restart the hide timer."""

        self._anchor = anchor
        self._message = f"{subject}提醒你：{message}"
        self._label.setText(self._message)
        self._resize_to_text()
        self.reposition()
        self.show()
        self.raise_()
        self._hide_timer.start(max(1, int(duration_ms)))

    def reposition(self) -> None:
        """Keep the bubble above the current pet position."""

        if self._anchor is None:
            return

        target = self._anchor.mapToGlobal(
            QPoint(self._anchor.width() // 2, 0)
        )
        screen = self._anchor.screen() or QApplication.screenAt(target)
        if screen is None:
            screen = QApplication.primaryScreen()

        x = target.x() - self.width() // 2
        y = target.y() - self.height() - 8
        if screen is not None:
            area = screen.availableGeometry()
            min_x = area.x() + self.SCREEN_MARGIN
            max_x = max(
                min_x,
                area.right() - self.width() - self.SCREEN_MARGIN + 1,
            )
            min_y = area.y() + self.SCREEN_MARGIN
            max_y = max(
                min_y,
                area.bottom() - self.height() - self.SCREEN_MARGIN + 1,
            )
            x = min(max(x, min_x), max_x)
            y = min(max(y, min_y), max_y)

        self._tail_x = min(
            self.width() - 18,
            max(18, target.x() - x),
        )
        self.move(x, y)
        self.update()

    def stop(self) -> None:
        self._hide_timer.stop()
        self.hide()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill = QColor(255, 252, 245, 245)
        outline = QPen(QColor(86, 80, 75, 220), 2)
        body = QRectF(
            1,
            1,
            self.width() - 2,
            self.height() - self.TAIL_HEIGHT - 2,
        )
        painter.setPen(outline)
        painter.setBrush(fill)
        painter.drawRoundedRect(body, 14, 14)

        base_y = body.bottom() - 1
        tip_y = self.height() - 1
        tail_left = QPoint(self._tail_x - 8, int(base_y))
        tail_tip = QPoint(self._tail_x, tip_y)
        tail_right = QPoint(self._tail_x + 8, int(base_y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPolygon([tail_left, tail_tip, tail_right])
        painter.setPen(outline)
        painter.drawLine(tail_left, tail_tip)
        painter.drawLine(tail_tip, tail_right)

    def _resize_to_text(self) -> None:
        flags = (
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )
        text_rect = self._label.fontMetrics().boundingRect(
            QRect(0, 0, self.MAX_TEXT_WIDTH, 1_000),
            int(flags),
            self._message,
        )
        text_width = min(
            self.MAX_TEXT_WIDTH,
            max(120, text_rect.width() + 2),
        )
        text_height = max(24, text_rect.height() + 2)
        width = text_width + self.HORIZONTAL_PADDING * 2
        height = (
            text_height
            + self.VERTICAL_PADDING * 2
            + self.TAIL_HEIGHT
        )
        self.setFixedSize(width, height)
        self._label.setGeometry(
            self.HORIZONTAL_PADDING,
            self.VERTICAL_PADDING,
            text_width,
            text_height,
        )
