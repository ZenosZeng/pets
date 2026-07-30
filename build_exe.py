"""使用手动输入的三段版本号构建带版本前缀的 Windows EXE。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import PyInstaller.__main__

PROJECT_ROOT = Path(__file__).resolve().parent


def non_negative_integer(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("版本号不能为负数")
    return number


def versioned_executable_name(major: int, minor: int, patch: int) -> str:
    """返回不带扩展名的版本化 EXE 名称。"""

    return f"v{major}.{minor}.{patch}-LineDogPet"


def pyinstaller_arguments(executable_name: str) -> list[str]:
    """生成 PyInstaller 参数，便于独立测试且不触发实际打包。"""

    return [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        executable_name,
        "--add-data",
        f"{PROJECT_ROOT / 'assets'}{os.pathsep}assets",
        str(PROJECT_ROOT / "main.py"),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="构建带三段版本号前缀的线条小狗桌宠 EXE",
    )
    parser.add_argument("major", type=non_negative_integer)
    parser.add_argument("minor", type=non_negative_integer)
    parser.add_argument("patch", type=non_negative_integer)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    executable_name = versioned_executable_name(
        args.major,
        args.minor,
        args.patch,
    )
    os.chdir(PROJECT_ROOT)
    print(f"Building dist/{executable_name}.exe")
    PyInstaller.__main__.run(pyinstaller_arguments(executable_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
