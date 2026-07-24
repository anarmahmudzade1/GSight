"""Modal dialogs: first-run API key onboarding, post-capture chat selector, and settings."""

from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
)

from services.gemini_api import clean_api_key, is_valid_key_format, validate_api_key_live
from services.storage import complete_onboarding, list_threads

AI_STUDIO_URL = "https://aistudio.google.com/apikey"
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"

# Light, "clean glass" palette (inverted from the earlier dark theme): dark
# text on bright/white surfaces, faint dark hairlines instead of faint light
# ones. All three dialogs (onboarding, chat selector, settings) render as
# fully opaque solid-white cards - see SOLID_DIALOG_STYLE below.
DIALOG_STYLE = """
QDialog { background-color: rgba(255, 255, 255, 235); border-radius: 14px; }
QLabel { color: #202124; background: transparent; font-size: 15px; }
QLineEdit {
    background-color: rgba(0, 0, 0, 12); color: #202124;
    border: 1px solid rgba(0, 0, 0, 30); border-radius: 8px;
    padding: 10px 14px; font-size: 15px;
}
QPushButton {
    background-color: #1A73E8; color: white; border: none;
    border-radius: 8px; padding: 10px 14px; font-size: 15px;
}
QPushButton:hover { background-color: #4285F4; }
QPushButton:disabled { background-color: #E0E0E0; color: #9AA0A6; }
QPushButton#linkButton, QPushButton#flatButton {
    background: transparent; color: #1A73E8; text-decoration: underline;
    padding: 0; text-align: left;
}
QPushButton#linkButton:hover, QPushButton#flatButton:hover { color: #4285F4; }
QListWidget {
    background-color: rgba(0, 0, 0, 6); color: #202124;
    border: 1px solid rgba(0, 0, 0, 18); border-radius: 8px; font-size: 15px;
}
QListWidget::item { padding: 10px; border-radius: 8px; }
QListWidget::item:selected { background-color: rgba(66, 133, 244, 45); color: #1A73E8; }
QListWidget::item:hover { background-color: rgba(0, 0, 0, 8); }
"""

# Fully-opaque, rectangular override for every dialog: a solid "standard
# window" background, no see-through interior, no rounded desktop cutouts.
# Used by the onboarding dialog, the chat selector, AND the Settings dialog,
# each paired with WA_TranslucentBackground turned OFF (see each __init__).
#
# #apiKeyInput uses fully-opaque (non-rgba) colors on purpose: a previous
# semi-transparent QLineEdit sitting on a semi-transparent QDialog caused a
# compositing ghosting bug where each keystroke's repaint blended with the
# previous frame instead of fully replacing it, making typed text look like it
# was stacking/overlapping. Solid colors end-to-end fix that at the root.
SOLID_DIALOG_STYLE = """
QDialog { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 0px; }
QLineEdit#apiKeyInput {
    background-color: #F1F3F4;
    color: #202124;
    border: 2px solid #1A73E8;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: bold;
    selection-background-color: #A8C7FA;
}
QLineEdit#apiKeyInput:focus { border: 2px solid #4285F4; }
QLineEdit#apiKeyInput:read-only {
    border: 2px solid #34A853;
    color: #5f6368;
    background-color: #E6F4EA;
}
"""

# Dark, fully-opaque stylesheet for the post-screenshot chat picker, applied
# via setStyleSheet() directly (replacing DIALOG_STYLE, not appended on top of
# it) so nothing here can be shadowed by an inherited alpha-blended rule.
# Every background colour is fully opaque - no rgba() with alpha below 255
# anywhere. QAbstractScrollArea scrolls its viewport by blitting, which is
# only correct over an opaque background; the previous rgba(..., 10) list
# background and rgba(..., 64) selection colour are what let old text pixels
# survive a scroll instead of being erased, producing the ghosting/smearing.
#
# No :hover rule anywhere, by design - hover feedback is deliberately absent
# per product decision, which also means there is no hover state left to get
# stuck.
CHAT_PICKER_STYLE = """
QDialog {
    background-color: #1A1A1E;
}
QLabel {
    background-color: transparent;
    color: #E8EAED;
    font-size: 16px;
    font-weight: bold;
}
QListWidget {
    background-color: #202024;
    color: #E8EAED;
    border: 1px solid #34343A;
    border-radius: 8px;
    outline: none;
    font-size: 14px;
}
QListWidget::item {
    background-color: #202024;
    color: #E8EAED;
    padding: 10px 12px;
    border: none;
}
QListWidget::item:selected {
    background-color: #2E2E35;
    color: #FFFFFF;
}
QListWidget::item:focus {
    background-color: #2E2E35;
    color: #FFFFFF;
}
QScrollBar:vertical {
    background-color: #202024;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #4A4A52;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background-color: #202024;
}
QPushButton {
    background-color: #2E2E35;
    color: #E8EAED;
    border: 1px solid #43434B;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
}
QPushButton:pressed {
    background-color: #3A3A42;
}
"""


class _FramelessDialog(QDialog):
    """Base for GSight's frameless, draggable, branded popup dialogs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DIALOG_STYLE)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self._drag_offset: QPoint | None = None

    def _make_opaque(self, extra_style: str = SOLID_DIALOG_STYLE):
        """Opt this dialog instance out of glass entirely: solid opaque card,
        no rounded desktop cutouts. Call after super().__init__(). Defaults to
        the shared solid-white card. ChatSelectorDialog doesn't use this - it
        sets WA_TranslucentBackground/autofill directly and applies its own
        complete CHAT_PICKER_STYLE (see its __init__)."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(self.styleSheet() + extra_style)

    def _header(self, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        if ICON_PATH.exists():
            icon_label = QLabel()
            icon_label.setPixmap(QPixmap(str(ICON_PATH)).scaled(
                22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
            row.addWidget(icon_label)
        title = QLabel(text)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        row.addWidget(title)
        row.addStretch()
        return row

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class ApiKeyValidationWorker(QThread):
    finished_validation = pyqtSignal(bool, str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        ok, message = validate_api_key_live(self.api_key)
        self.finished_validation.emit(ok, message)


class ApiKeyOnboardingDialog(_FramelessDialog):
    """First-run gatekeeper: blocks all app features until a working Gemini API key is stored."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._make_opaque()
        self.setFixedSize(700, 800)
        self._worker: ApiKeyValidationWorker | None = None
        self._verified = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(18)

        layout.addLayout(self._header("Connect your Gemini API key"))

        body = QLabel(
            "GSight needs a Gemini API key to analyze your screen captures. "
            "Keys are stored locally in config.json and are only ever sent to Google's Gemini API."
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        link_btn = QPushButton("Get a free API key from Google AI Studio →")
        link_btn.setObjectName("linkButton")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Not the Enter-key target: without this, Qt can silently promote the
        # first push button in the dialog to "default", so pressing Enter in
        # key_input would open the browser instead of validating.
        link_btn.setAutoDefault(False)
        link_btn.setDefault(False)
        link_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(AI_STUDIO_URL)))
        layout.addWidget(link_btn)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("apiKeyInput")
        self.key_input.setPlaceholderText("AIza...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.key_input.textChanged.connect(self._on_text_changed)
        self.key_input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.key_input)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #D93025; font-size: 13px;")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        layout.addStretch()

        button_row = QHBoxLayout()
        self.quit_btn = QPushButton("Quit")
        self.quit_btn.setAutoDefault(False)
        self.quit_btn.clicked.connect(self.reject)

        # Single dynamic button carries the whole flow: "Verify Key" ->
        # "Checking Key..." -> "Continue". No separate Validate/Continue
        # QPushButton instances are ever created.
        self.action_btn = QPushButton("Verify Key")
        self.action_btn.setEnabled(False)
        self.action_btn.setAutoDefault(True)
        self.action_btn.setDefault(True)
        self.action_btn.clicked.connect(self._on_action_clicked)

        button_row.addWidget(self.quit_btn)
        button_row.addStretch()
        button_row.addWidget(self.action_btn)
        layout.addLayout(button_row)

    def _set_status(self, text: str, color: str, bold: bool = False):
        """The single mutation point for status_label: always replaces both the
        text and style together (never leaves a stale color/weight from a
        previous state), and forces an immediate re-layout via adjustSize() so
        a shorter/longer message can never visually overlap the last one."""
        weight = "font-weight: bold;" if bold else ""
        self.status_label.setStyleSheet(f"color: {color}; font-size: 13px; {weight}")
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))
        self.status_label.adjustSize()

    def _on_text_changed(self, text: str):
        # Any edit invalidates a prior "Verified" result. Gate is purely on
        # non-empty text - actual format/liveness is checked when clicked.
        clean_key = text.strip()
        self.action_btn.setEnabled(len(clean_key) > 0)
        self._set_status("", "#202124")

    def _on_return_pressed(self):
        if self.action_btn.isEnabled():
            self._on_action_clicked()

    def _on_action_clicked(self):
        if self._verified:
            self._on_continue()
        else:
            self._start_validation()

    def _start_validation(self):
        clean_key = self.key_input.text().strip()
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Checking Key...")
        self._set_status("Checking Key...", "#5f6368")

        self._worker = ApiKeyValidationWorker(clean_key)
        self._worker.finished_validation.connect(self._on_validated)
        self._worker.start()

    def _on_validated(self, ok: bool, message: str):
        if ok:
            self._verified = True
            # The "Checking Key..." status is fully replaced (never overlaid) by
            # this single setText/setStyleSheet call on the same status_label.
            self._set_status("✓ Verification Complete", "#34A853", bold=True)
            self.key_input.setReadOnly(True)
            self.action_btn.setText("Continue")
            self.action_btn.setEnabled(True)
            self.action_btn.raise_()
        else:
            self._verified = False
            self.action_btn.setText("Verify Key")
            self.action_btn.setEnabled(True)
            self._set_status("✗ Invalid API Key. Please check your key in Google AI Studio.", "#D93025")

    def _on_continue(self):
        # clean_api_key strips leading/trailing/embedded whitespace (spaces, tabs,
        # stray newlines) that copy-pasting can smuggle into the field. One atomic
        # write persists the key and the one-time onboarding_completed flag together.
        # Telemetry defaults on (see SettingsDialog's privacy notice); there is no
        # opt-out step in onboarding itself.
        complete_onboarding(clean_api_key(self.key_input.text()), True)
        self.accept()


class ChatSelectorDialog(_FramelessDialog):
    """'Select Chat to Continue' popup shown after a quick capture."""

    NEW_CHAT = "__new_chat__"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 420)
        self._chosen_thread_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addLayout(self._header("Select Chat to Continue"))

        # No Cancel/Continue buttons: a single click on any row instantly
        # chooses it and closes the dialog. Escape still rejects (QDialog's
        # default behavior, unchanged). There is deliberately no :hover rule
        # in CHAT_PICKER_STYLE - hovering a row produces zero visual change,
        # which structurally rules out the stuck-highlight bug this list used
        # to have.
        self.list_widget = QListWidget()
        new_chat_item = QListWidgetItem("+ New Chat")
        new_chat_item.setData(Qt.ItemDataRole.UserRole, self.NEW_CHAT)
        self.list_widget.addItem(new_chat_item)

        for thread in reversed(list_threads()):
            item = QListWidgetItem(f"{thread['name']}  ({len(thread['messages'])} msgs)")
            item.setData(Qt.ItemDataRole.UserRole, thread["id"])
            self.list_widget.addItem(item)

        self.list_widget.setCurrentRow(-1)  # nothing pre-selected
        self.list_widget.itemClicked.connect(self._on_choose)
        layout.addWidget(self.list_widget)

        # This dialog must NOT inherit or set translucency. QAbstractScrollArea
        # scrolls its viewport by blitting, which is only valid over an opaque
        # background - a transparent viewport is what smears old text across the
        # list when you drag the scrollbar.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)

        # Belt and braces: force the list's own viewport opaque too. The QSS
        # below sets the colour; this guarantees Qt treats it as fill-worthy
        # rather than composite-through.
        self.list_widget.viewport().setAutoFillBackground(True)
        self.list_widget.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        # Per-pixel scrolling plus an explicit full-viewport repaint on every
        # scrollbar move. This costs almost nothing on a list of this size and
        # removes any remaining dependence on the blit fast path being correct.
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.verticalScrollBar().valueChanged.connect(
            self.list_widget.viewport().update
        )

        self.setStyleSheet(CHAT_PICKER_STYLE)

    def _on_choose(self, item):
        if item is None:
            return
        self._chosen_thread_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def is_new_chat(self) -> bool:
        return self._chosen_thread_id == self.NEW_CHAT

    def selected_thread_id(self) -> str | None:
        return None if self.is_new_chat() else self._chosen_thread_id


class SettingsDialog(_FramelessDialog):
    """App info panel, reachable from the tray menu.

    Telemetry is on by default with no in-onboarding opt-out; this dialog is
    where that data collection is disclosed to the user.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._make_opaque()
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        layout.addLayout(self._header("Settings"))

        note = QLabel(
            "GSight never sends prompt text, image pixels, or your API key. "
            "See the Privacy & Data Collection section of the README for the full event schema. "
            "Telemetry can be disabled by editing config.json directly."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #5f6368; font-size: 13px;")
        layout.addWidget(note)

        privacy_note = QLabel(
            "Analytics Notice: Anonymous usage data is recorded strictly for product "
            "improvement and performance analytics. Your private chat content, captures, "
            "and personal data are never stored or analyzed."
        )
        privacy_note.setWordWrap(True)
        privacy_note.setStyleSheet("color: #5f6368; font-size: 12px; font-style: italic;")
        layout.addWidget(privacy_note)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
