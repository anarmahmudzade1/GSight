"""Application entry point: tray icon lifecycle and dual-mode hotkey/shortcut routing."""

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from pynput import keyboard

from ui.snipper import SnipperOverlay
from ui.window import MainWindow
from ui.dialogs import ApiKeyOnboardingDialog, ChatSelectorDialog, SettingsDialog
from services.storage import ensure_captures_dir, get_api_key, is_onboarding_completed, list_threads
from services.gemini_api import is_valid_key_format
from services.telemetry import telemetry

ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.png"

# Mode A: floating chat interface directly. Mode B: drag-to-crop snipper directly.
HOTKEY_CHAT = "<ctrl>+<shift>+a"
HOTKEY_CAPTURE = "<ctrl>+<shift>+s"


class HotkeyBridge(QObject):
    """Relays both global hotkeys from the pynput listener thread to the Qt main thread."""

    chat_activated = pyqtSignal()
    capture_activated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._listener = keyboard.GlobalHotKeys(
            {
                HOTKEY_CHAT: self.chat_activated.emit,
                HOTKEY_CAPTURE: self.capture_activated.emit,
            }
        )

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()


class GSightApp:
    def __init__(self, initial_mode: str):
        ensure_captures_dir()

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        if ICON_PATH.exists():
            self.app.setWindowIcon(QIcon(str(ICON_PATH)))

        if not self._pass_api_key_gate():
            sys.exit(0)

        self._pending_capture_from_shortcut = False

        self.snipper = SnipperOverlay()
        self.snipper.captured.connect(self._on_capture)

        self.window = MainWindow()
        self.window.capture_requested.connect(lambda: self._show_snipper(triggered_by_shortcut=False))

        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.chat_activated.connect(self._on_chat_hotkey)
        self.hotkey_bridge.capture_activated.connect(self._on_capture_hotkey)
        self.hotkey_bridge.start()

        self.tray_icon = self._build_tray_icon()

        telemetry.capture("app_launched", {"mode": initial_mode})

        if initial_mode == "capture":
            self._on_capture_hotkey()
        else:
            self._on_chat_hotkey()

    def _pass_api_key_gate(self) -> bool:
        """One-time gate: skips straight to the main app only once onboarding has
        actually been completed AND a syntactically-valid key is on file."""
        if is_onboarding_completed() and is_valid_key_format(get_api_key()):
            return True
        return bool(ApiKeyOnboardingDialog().exec())

    def _build_tray_icon(self) -> QSystemTrayIcon:
        icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()
        tray = QSystemTrayIcon(icon, self.app)
        tray.setToolTip("GSight")

        menu = QMenu()

        chat_action = QAction("Open Chat (Ctrl+Shift+A)", self.app)
        chat_action.triggered.connect(self._on_chat_hotkey)
        menu.addAction(chat_action)

        capture_action = QAction("Quick Capture (Ctrl+Shift+S)", self.app)
        capture_action.triggered.connect(self._on_capture_hotkey)
        menu.addAction(capture_action)

        menu.addSeparator()

        settings_action = QAction("Settings...", self.app)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_chat_hotkey()

    # ---- Mode A: chat -------------------------------------------------

    def _on_chat_hotkey(self):
        telemetry.capture("shortcut_triggered", {"mode": "chat"})
        self._pending_capture_from_shortcut = False
        if self.window.current_thread_id is None:
            threads = list_threads()
            self.window.load_thread(threads[-1]["id"]) if threads else self.window.start_new_thread()
        self._show_window()

    # ---- Mode B: quick capture -------------------------------------------------

    def _on_capture_hotkey(self):
        telemetry.capture("shortcut_triggered", {"mode": "capture"})
        self._show_snipper(triggered_by_shortcut=True)

    def _show_snipper(self, triggered_by_shortcut: bool):
        self._pending_capture_from_shortcut = triggered_by_shortcut
        self.window.hide()
        self.snipper.show()

    def _on_capture(self, pixmap):
        telemetry.capture("crop_captured")
        threads = list_threads()
        needs_selector = self._pending_capture_from_shortcut or len(threads) > 1

        if needs_selector:
            dialog = ChatSelectorDialog()
            if not dialog.exec():
                return
            self.window.start_new_thread() if dialog.is_new_chat() else self.window.load_thread(
                dialog.selected_thread_id()
            )
        elif threads:
            self.window.load_thread(threads[0]["id"])
        else:
            self.window.start_new_thread()

        self.window.add_attachment(pixmap)
        self._show_window()

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        self.window.focus_composer()

    def _open_settings(self):
        SettingsDialog().exec()

    def quit(self):
        self.hotkey_bridge.stop()
        telemetry.shutdown()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec()


def parse_args():
    parser = argparse.ArgumentParser(description="GSight - translucent desktop AI vision utility")
    parser.add_argument(
        "--mode",
        choices=["chat", "capture"],
        default="chat",
        help="'chat' opens the floating chat directly (Mode A); "
        "'capture' opens the snipper directly (Mode B). Used by the two desktop shortcuts.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    gsight = GSightApp(initial_mode=args.mode)
    sys.exit(gsight.run())


if __name__ == "__main__":
    main()
