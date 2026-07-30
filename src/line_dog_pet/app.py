"""线条小狗桌宠程序入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .controller import PetController
from .resources import find_missing_assets


def report_missing_assets() -> None:
    """启动时在控制台列出缺失资源；窗口仍会正常使用占位内容。"""

    missing = find_missing_assets()
    if not missing:
        return

    print(
        "[桌宠资源提示] 以下状态目录没有 GIF，将使用占位显示：",
        file=sys.stderr,
    )
    for state, path in missing.items():
        print(f"  - {state.value}: {path}", file=sys.stderr)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("线条小狗桌宠")
    app.setOrganizationName("LineDogPet")
    app.setQuitOnLastWindowClosed(False)

    report_missing_assets()
    controller = PetController(app)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
