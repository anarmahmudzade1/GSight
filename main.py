"""Application entry point & tray icon lifecycle."""

import sys

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QColor, QAction
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from pynput import keyboard

from ui.snipper import SnipperOverlay
from ui.window import MainWindow
from services.storage import ensure_captures_dir

HOTKEY = "<ctrl>+<shift>+a"


class HotkeyBridge(QObject):
    """Relays the global hotkey from the pynput listener thread to the Qt main thread."""

    activated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._listener = keyboard.GlobalHotKeys({HOTKEY: self.activated.emit})

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()


class GSightApp:
    def __init__(self):
        ensure_captures_dir()

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.snipper = SnipperOverlay()
        self.snipper.captured.connect(self._on_capture)

        self.window = MainWindow()

        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.activated.connect(self._show_snipper)
        self.hotkey_bridge.start()

        self.tray_icon = self._build_tray_icon()

    def _build_tray_icon(self) -> QSystemTrayIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(61, 126, 255))
        icon = QIcon(pixmap)

        tray = QSystemTrayIcon(icon, self.app)
        tray.setToolTip("GSight")

        menu = QMenu()
        snip_action = QAction("New Snip (Ctrl+Shift+A)", self.app)
        snip_action.triggered.connect(self._show_snipper)
        menu.addAction(snip_action)

        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_snipper()

    def _show_snipper(self):
        self.snipper.show()

    def _on_capture(self, pixmap):
        self.window.set_capture(pixmap)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def quit(self):
        self.hotkey_bridge.stop()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec()


def main():
    gsight = GSightApp()
    sys.exit(gsight.run())


if __name__ == "__main__":
    main()
