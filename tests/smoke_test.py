"""快速离屏测试：验证窗口、状态与多 GIF 随机选择。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import (  # noqa: E402
    QPoint,
    QRect,
    QSettings,
    QSize,
    QTemporaryDir,
)
from PySide6.QtGui import QColor, QImageReader, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from line_dog_pet.animator import fit_size, pixmap_hit_region  # noqa: E402
from line_dog_pet.controller import PetController  # noqa: E402
from line_dog_pet.resources import animation_paths  # noqa: E402
from line_dog_pet.scheduler import (  # noqa: E402
    REMINDER_MESSAGES,
    PetScheduler,
)
from line_dog_pet.state import PetState  # noqa: E402
from line_dog_pet.window import PetWindow  # noqa: E402
from tools.build_exe import (  # noqa: E402
    PYINSTALLER_HOOKS,
    UNUSED_QT_MODULES,
    pyinstaller_arguments,
    versioned_executable_name,
)


def main() -> int:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    executable_name = versioned_executable_name(0, 1, 1)
    assert executable_name == "v0.1.1-LineDogPet"
    build_arguments = pyinstaller_arguments(executable_name)
    assert build_arguments[build_arguments.index("--name") + 1] == executable_name
    source_path = Path(build_arguments[build_arguments.index("--paths") + 1])
    assert source_path == PROJECT_ROOT / "src"
    hooks_path = Path(
        build_arguments[build_arguments.index("--additional-hooks-dir") + 1]
    )
    assert hooks_path == PYINSTALLER_HOOKS
    assert build_arguments[build_arguments.index("--optimize") + 1] == "2"
    for module_name in UNUSED_QT_MODULES:
        assert module_name in build_arguments
    assert build_arguments[-1].endswith("main.py")

    pixmap = QPixmap(20, 20)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.fillRect(5, 6, 7, 8, QColor(255, 255, 255, 255))
    painter.end()
    hit_region = pixmap_hit_region(pixmap, QSize(30, 30))
    assert hit_region.boundingRect() == QRect(10, 16, 7, 8)
    assert hit_region.contains(QPoint(10, 16))
    assert not hit_region.contains(QPoint(9, 16))

    scheduler = PetScheduler(
        idle_min_ms=1_000,
        idle_max_ms=1_000,
        reminder_tick_ms=1_000,
    )
    reminders: list[str] = []
    scheduler.reminder_due.connect(reminders.append)
    for _ in range(4):
        scheduler._on_reminder_timeout()
    assert reminders == [
        REMINDER_MESSAGES[0],
        REMINDER_MESSAGES[1],
        REMINDER_MESSAGES[0],
        REMINDER_MESSAGES[1],
    ]

    window = PetWindow()
    window.show()
    app.processEvents()

    canvas_size = PetWindow.CANVAS_SIZE
    assert canvas_size == QSize(154, 154)
    assert window.size() == canvas_size
    assert window._label.size() == canvas_size
    assert window.scale_percent == PetWindow.DEFAULT_SCALE_PERCENT
    assert PetWindow.normalize_scale_percent("113") == 110
    assert PetWindow.normalize_scale_percent("invalid") == 100
    context_menu = window._create_context_menu()
    top_level_actions = {
        action.text(): action for action in context_menu.actions()
    }
    for text in ("放大 10%", "缩小 10%", "恢复默认大小"):
        assert text in top_level_actions
        assert top_level_actions[text].menu() is None
    assert "宠物大小" not in top_level_actions
    context_menu.deleteLater()

    square_fit = fit_size(QSize(240, 240), canvas_size)
    portrait_fit = fit_size(QSize(143, 170), canvas_size)
    assert square_fit == canvas_size
    assert portrait_fit.width() <= canvas_size.width()
    assert portrait_fit.height() <= canvas_size.height()
    assert (
        portrait_fit.width() == canvas_size.width()
        or portrait_fit.height() == canvas_size.height()
    )

    window.move(320, 240)
    app.processEvents()
    fixed_position = window.pos()
    fixed_size = window.size()
    assert not window._pending_hit_region.isEmpty()

    scale_changes: list[int] = []
    window.scale_changed.connect(scale_changes.append)
    animation_before_scale = window.current_animation_path
    bottom_center = QPoint(
        window.x() + window.width() // 2,
        window.y() + window.height(),
    )
    window.increase_scale()
    app.processEvents()
    enlarged_size = PetWindow.canvas_size_for_scale(110)
    assert window.scale_percent == 110
    assert window.size() == enlarged_size
    assert window._label.size() == enlarged_size
    assert window.current_animation_path == animation_before_scale
    assert QPoint(
        window.x() + window.width() // 2,
        window.y() + window.height(),
    ) == bottom_center
    assert window._animator._movie is not None
    assert (
        window._animator._movie.currentPixmap().size()
        == window._animator.current_render_size
    )
    assert window._animator.current_render_size.width() <= window.width()
    assert window._animator.current_render_size.height() <= window.height()

    window.decrease_scale()
    app.processEvents()
    assert window.scale_percent == 100
    assert window.size() == fixed_size
    assert window.pos() == fixed_position
    assert scale_changes == [110, 100]

    window.set_scale_percent(1)
    assert window.scale_percent == PetWindow.MIN_SCALE_PERCENT
    window.decrease_scale()
    assert window.scale_percent == PetWindow.MIN_SCALE_PERCENT
    window.set_scale_percent(999)
    assert window.scale_percent == PetWindow.MAX_SCALE_PERCENT
    window.increase_scale()
    assert window.scale_percent == PetWindow.MAX_SCALE_PERCENT
    window.reset_scale()
    app.processEvents()
    assert window.scale_percent == PetWindow.DEFAULT_SCALE_PERCENT
    assert window.size() == fixed_size
    assert window.pos() == fixed_position

    window.set_paused(True)
    assert window.is_paused
    window.set_paused(False)
    assert not window.is_paused

    requested_reminders: list[str] = []
    window.reminder_requested.connect(requested_reminders.append)
    window.request_activity_reminder()
    window.request_water_reminder()
    assert requested_reminders == list(REMINDER_MESSAGES)

    for state in PetState:
        available = set(animation_paths(state))
        assert available, f"{state.value} 没有 GIF"
        for path in available:
            reader = QImageReader(str(path))
            assert reader.canRead(), f"{path.name} 无法读取"
            assert not reader.size().isEmpty(), f"{path.name} 尺寸无效"

        previous = None
        attempts = max(4, len(available) * 3)
        for _ in range(attempts):
            window.switch_state(state)
            app.processEvents()
            selected = window.current_animation_path

            assert selected in available
            assert window.pos() == fixed_position
            assert window.size() == fixed_size
            render_size = window._animator.current_render_size
            assert not render_size.isEmpty()
            assert render_size.width() <= canvas_size.width()
            assert render_size.height() <= canvas_size.height()
            assert (
                render_size.width() == canvas_size.width()
                or render_size.height() == canvas_size.height()
            )
            if len(available) > 1:
                assert selected != previous
            previous = selected

        previous = window.current_animation_path
        window.switch_animation()
        app.processEvents()
        if len(available) > 1:
            assert window.current_animation_path != previous

    previous_state = window.current_state
    for _ in range(20):
        window.switch_to_random_state()
        app.processEvents()
        assert window.current_state != previous_state
        assert window.current_animation_path in set(
            animation_paths(window.current_state)
        )
        previous_state = window.current_state

    window.close()

    temporary_directory = QTemporaryDir()
    assert temporary_directory.isValid()
    settings_path = Path(temporary_directory.path()) / "settings.ini"
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    controller = PetController(app, settings=settings, tray_enabled=False)
    controller.start()
    controller.window.set_scale_percent(130)
    controller.window.move(410, 310)

    controller.window.switch_state(PetState.XIAOBAI)
    controller.window.request_activity_reminder()
    app.processEvents()
    bubble = controller._reminder_bubble
    assert bubble.isVisible()
    assert bubble.message == f"小白提醒你：{REMINDER_MESSAGES[0]}"
    assert bubble.y() < controller.window.y()
    first_bubble_position = bubble.pos()

    controller.window.move(430, 330)
    app.processEvents()
    assert bubble.pos() != first_bubble_position
    controller.window.switch_state(PetState.XIAOJIMAO)
    controller.window.request_water_reminder()
    app.processEvents()
    assert bubble.message == f"小鸡毛提醒你：{REMINDER_MESSAGES[1]}"

    controller.window.switch_state(PetState.TOGETHER)
    controller.window.request_activity_reminder()
    app.processEvents()
    assert bubble.message == (
        f"小白和小鸡毛一起提醒你：{REMINDER_MESSAGES[0]}"
    )
    controller.window.move(410, 310)
    controller.scheduler.set_reminders_enabled(False)
    controller.shutdown()
    assert not bubble.isVisible()
    controller.window.close()

    restored_settings = QSettings(
        str(settings_path),
        QSettings.Format.IniFormat,
    )
    restored = PetController(
        app,
        settings=restored_settings,
        tray_enabled=False,
    )
    restored.start()
    app.processEvents()
    assert restored.window.current_state == PetState.TOGETHER
    assert restored.window.pos() == QPoint(410, 310)
    assert restored.window.scale_percent == 130
    assert restored.window.size() == PetWindow.canvas_size_for_scale(130)
    assert not restored.scheduler.reminders_enabled
    restored.shutdown()
    restored.window.close()

    print("desktop pet smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
