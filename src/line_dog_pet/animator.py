"""GIF 动画加载、播放与占位显示。"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBitmap, QImage, QImageReader, QMovie, QPixmap, QRegion
from PySide6.QtWidgets import QLabel

from .resources import (
    animation_directory,
    animation_paths,
    relative_asset_path,
)
from .state import PetState


def fit_size(source_size: QSize, bounds: QSize) -> QSize:
    """Return the largest proportional size that fits inside bounds."""

    if source_size.isEmpty() or bounds.isEmpty():
        return QSize()
    return source_size.scaled(bounds, Qt.AspectRatioMode.KeepAspectRatio)


def pixmap_hit_region(pixmap: QPixmap, canvas_size: QSize) -> QRegion:
    """Build a click region from the pixmap's non-transparent pixels."""

    if pixmap.isNull():
        return QRegion()

    image = pixmap.toImage().convertToFormat(
        QImage.Format.Format_ARGB32_Premultiplied
    )
    mask_image = image.createMaskFromColor(0, Qt.MaskMode.MaskInColor)
    region = QRegion(QBitmap.fromImage(mask_image))

    offset_x = (canvas_size.width() - image.width()) // 2
    offset_y = canvas_size.height() - image.height()
    return region.translated(offset_x, offset_y)


class PetAnimator(QObject):
    """负责把不同状态的 GIF 或占位内容显示在 QLabel 中。"""

    hit_region_changed = Signal(object)

    def __init__(
        self,
        label: QLabel,
        canvas_size: QSize,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._canvas_size = QSize(canvas_size)
        self._movie: QMovie | None = None
        self._active_state = PetState.XIAOBAI
        self._active_path: Path | None = None
        self._last_path_by_state: dict[PetState, Path] = {}
        self._failed_paths: set[Path] = set()
        self._source_size = QSize()
        self._render_size = QSize()
        self._paused = False
        self._label.setFixedSize(self._canvas_size)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )

    @property
    def current_animation_path(self) -> Path | None:
        return self._active_path

    @property
    def current_render_size(self) -> QSize:
        return QSize(self._render_size)

    def set_state(self, state: PetState) -> None:
        """从指定状态目录随机加载一个可用 GIF。"""

        self._stop_movie()
        self._active_state = state
        directory = animation_directory(state)
        paths = [
            path
            for path in animation_paths(state)
            if path not in self._failed_paths
        ]
        if not paths:
            self._show_placeholder(state, directory, "目录中没有可用 GIF")
            return

        last_path = self._last_path_by_state.get(state)
        random.shuffle(paths)
        if len(paths) > 1 and last_path in paths:
            paths.remove(last_path)
            paths.append(last_path)

        for path in paths:
            source_size = QImageReader(str(path)).size()
            render_size = fit_size(source_size, self._canvas_size)
            if render_size.isEmpty():
                print(f"[桌宠资源提示] GIF 尺寸无效: {path}", file=sys.stderr)
                self._failed_paths.add(path)
                continue

            movie = QMovie(str(path))
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            if movie.isValid():
                self._start_movie(
                    state,
                    path,
                    movie,
                    source_size,
                    render_size,
                )
                return

            print(f"[桌宠资源提示] GIF 无法读取: {path}", file=sys.stderr)
            self._failed_paths.add(path)
            movie.deleteLater()

        self._show_placeholder(state, directory, "目录中没有可读取的 GIF")

    def set_canvas_size(self, canvas_size: QSize) -> None:
        """Resize the canvas and current animation without changing its GIF."""

        canvas_size = QSize(canvas_size)
        if canvas_size.isEmpty() or canvas_size == self._canvas_size:
            return

        self._canvas_size = canvas_size
        self._label.setFixedSize(canvas_size)
        if (
            self._movie is None
            or self._active_path is None
            or self._source_size.isEmpty()
        ):
            self._render_size = QSize(canvas_size)
            self.hit_region_changed.emit(
                QRegion(QRect(0, 0, canvas_size.width(), canvas_size.height()))
            )
            return

        render_size = fit_size(self._source_size, canvas_size)
        frame_number = max(0, self._movie.currentFrameNumber())
        state = self._active_state
        path = self._active_path
        source_size = QSize(self._source_size)
        replacement = QMovie(str(path))
        replacement.setCacheMode(QMovie.CacheMode.CacheAll)
        if not replacement.isValid():
            replacement.deleteLater()
            return

        self._stop_movie()
        self._start_movie(
            state,
            path,
            replacement,
            source_size,
            render_size,
        )
        replacement.jumpToFrame(frame_number)
        self._on_frame_changed(frame_number)

    def _start_movie(
        self,
        state: PetState,
        path: Path,
        movie: QMovie,
        source_size: QSize,
        render_size: QSize,
    ) -> None:
        self._movie = movie
        self._active_path = path
        self._last_path_by_state[state] = path
        self._source_size = QSize(source_size)
        self._render_size = QSize(render_size)
        self._label.clear()
        self._label.setStyleSheet("")
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )
        movie.setScaledSize(render_size)
        self._label.setMovie(movie)
        movie.frameChanged.connect(self._on_frame_changed)
        movie.error.connect(self._on_movie_error)
        movie.start()
        movie.setPaused(self._paused)

    def stop(self) -> None:
        """停止当前动画。"""

        self._stop_movie()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        if self._movie is not None:
            self._movie.setPaused(self._paused)

    def _stop_movie(self) -> None:
        if self._movie is None:
            return

        self._movie.stop()
        try:
            self._movie.frameChanged.disconnect(self._on_frame_changed)
            self._movie.error.disconnect(self._on_movie_error)
        except (RuntimeError, TypeError):
            pass
        self._label.clear()
        self._movie.deleteLater()
        self._movie = None
        self._active_path = None
        self._source_size = QSize()
        self._render_size = QSize()

    def _on_frame_changed(self, _frame_number: int) -> None:
        if self._movie is None:
            return
        region = pixmap_hit_region(
            self._movie.currentPixmap(),
            self._canvas_size,
        )
        self.hit_region_changed.emit(region)

    def _on_movie_error(self, _error: object) -> None:
        if self._movie is None:
            return

        error_message = self._movie.lastErrorString()
        failed_path = self._active_path
        state = self._active_state
        if failed_path is not None:
            self._failed_paths.add(failed_path)
        self._stop_movie()
        detail = f": {error_message}" if error_message else ""
        print(
            f"[桌宠资源提示] GIF 播放失败{detail}: {failed_path}",
            file=sys.stderr,
        )
        self.set_state(state)

    def _show_placeholder(
        self,
        state: PetState,
        path: Path,
        reason: str,
    ) -> None:
        display_path = relative_asset_path(path).as_posix()
        print(f"[桌宠资源提示] {reason}: {path}", file=sys.stderr)

        self._label.clear()
        self._label.setText(
            f"{state.display_name}\n\n"
            f"{reason}\n"
            f"{display_path}/*.gif"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            """
            QLabel {
                color: #3b3836;
                background-color: rgba(255, 252, 245, 225);
                border: 2px solid #56504b;
                border-radius: 24px;
                padding: 14px;
                font-family: "Microsoft YaHei UI";
                font-size: 14px;
            }
            """
        )
        self._render_size = QSize(self._canvas_size)
        self.hit_region_changed.emit(
            QRegion(QRect(0, 0, self._canvas_size.width(), self._canvas_size.height()))
        )
