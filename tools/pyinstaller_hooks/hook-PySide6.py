"""Keep only the PySide6 runtime support used by the desktop pet."""

from PyInstaller.utils.hooks import check_requirement
from PyInstaller.utils.hooks.qt import ensure_single_qt_bindings_package

ensure_single_qt_bindings_package("PySide6")

hiddenimports = ["shiboken6", "inspect"]
if check_requirement("PySide6 >= 6.4.0"):
    hiddenimports.append("PySide6.support.deprecated")

# PySide6 imports QtNetwork only to initialize optional OpenSSL support.
excludedimports = ["PySide6.QtNetwork"]

# The default hook adds the 20 MB software OpenGL fallback. This application
# renders QLabel/QMovie widgets and does not use OpenGL.
binaries = []
