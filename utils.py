"""项目通用路径与资源检查函数。"""

from __future__ import annotations

import sys
from pathlib import Path

from pet_state import PetState


def project_root() -> Path:
    """返回源码目录或 PyInstaller 解包后的资源目录。"""

    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return Path(bundle_dir)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def animation_directory(state: PetState) -> Path:
    """返回某个状态的动画目录。"""

    return project_root() / "assets" / state.value


def animation_paths(state: PetState) -> list[Path]:
    """返回状态目录下所有 GIF，文件名排序仅用于保证可预测的扫描顺序。"""

    directory = animation_directory(state)
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.glob("*.gif") if path.is_file()),
        key=lambda path: path.name.casefold(),
    )


def relative_asset_path(path: Path) -> Path:
    """把资源绝对路径转换为适合展示的项目相对路径。"""

    try:
        return path.relative_to(project_root())
    except ValueError:
        return path


def find_missing_assets() -> dict[PetState, Path]:
    """找出目录内没有任何 GIF 的状态。"""

    return {
        state: animation_directory(state)
        for state in PetState
        if not animation_paths(state)
    }
