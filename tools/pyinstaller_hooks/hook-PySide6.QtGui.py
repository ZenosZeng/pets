"""Bundle only the Windows and GIF plugins required by the desktop pet."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import pyside6_library_info


def _selected_plugins(plugin_type: str, filenames: set[str]):
    return [
        (source, destination)
        for source, destination in pyside6_library_info.collect_plugins(
            plugin_type
        )
        if Path(source).name.casefold() in filenames
    ]


hiddenimports = ["PySide6.QtCore"]
binaries = [
    *_selected_plugins("platforms", {"qwindows.dll"}),
    *_selected_plugins("imageformats", {"qgif.dll"}),
]
datas = []
