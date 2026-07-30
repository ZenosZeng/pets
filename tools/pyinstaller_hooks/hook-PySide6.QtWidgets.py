"""Keep the native-looking Windows widget style without other Qt extras."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import pyside6_library_info


binaries = [
    (source, destination)
    for source, destination in pyside6_library_info.collect_plugins("styles")
    if Path(source).name.casefold() == "qmodernwindowsstyle.dll"
]
hiddenimports = ["PySide6.QtCore", "PySide6.QtGui"]
datas = []
