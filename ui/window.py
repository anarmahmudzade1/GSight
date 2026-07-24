"""Main translucent glass chat window: frameless, resizable, Gemini-web-style sidebar and bubbles."""

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QThread, QTimer, QPoint, pyqtSignal, QBuffer, QIODeviceBase
from PyQt6.QtGui import QPixmap, QIcon, QColor, QPalette
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QSizeGrip,
    QGraphicsDropShadowEffect,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QApplication,
)

from services.gemini_api import GeminiService
from services.storage import (
    create_thread,
    get_thread,
    add_message,
    list_threads,
    rename_thread,
    CAPTURES_DIR,
    ensure_captures_dir,
)
from services.telemetry import telemetry
from ui.chat_bubble import MessageBubble, DEFAULT_BUBBLE_MAX_WIDTH
from ui.dialogs import SettingsDialog

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"

MAX_ATTACHMENTS = 5

# Sleek dark glass theme: translucent near-black panels, light text, faint
# light hairlines. A real background *blur* (acrylic/Mica) needs
# platform-specific DWM calls on Windows; this approximates the look with
# translucency + a soft drop shadow.
GLASS_STYLE = """
QFrame#glassContainer {
    background-color: rgba(18, 18, 22, 158);
    border: 1px solid rgba(255, 255, 255, 22);
    border-radius: 16px;
}
QLabel#titleLabel { color: #E8EAED; font-weight: bold; font-size: 20px; background: transparent; }
QLabel { color: #E8EAED; background: transparent; font-size: 15px; }
QScrollArea { background: transparent; border: none; }
QScrollArea#chatScroll > QWidget > QWidget#chatBody {
    background-color: rgba(18, 18, 22, 30);
    border-radius: 10px;
}
QFrame#sidebar {
    background-color: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 25);
    border-radius: 16px;
}
QPushButton#newChatButton {
    background-color: #1A73E8;
    color: white;
    border: none;
    border-radius: 22px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: bold;
    text-align: left;
}
QPushButton#newChatButton:hover { background-color: #4285F4; }
QListWidget#sidebarList, QListWidget#sidebarList::viewport {
    background-color: #121212;
    border: none;
    outline: none;
}

QListWidget#sidebarList::item {
    padding: 10px 8px;
    background-color: #121212;
    color: #E3E3E3;
    border: none;
}

QListWidget#sidebarList::item:hover {
    background-color: #1E1E1E;
    color: #FFFFFF;
}

QListWidget#sidebarList::item:selected {
    background-color: #2D3748;
    color: #FFFFFF;
}

/* Restore normal, clean scrollbar styling for the sidebar list */
QListWidget#sidebarList QScrollBar:vertical {
    background: #1E1E1E;
    width: 8px;
    margin: 0px;
}

QListWidget#sidebarList QScrollBar::handle:vertical {
    background: #4A5568;
    min-height: 20px;
    border-radius: 4px;
}

QListWidget#sidebarList QScrollBar::add-line:vertical,
QListWidget#sidebarList QScrollBar::sub-line:vertical {
    height: 0px;
}
QFrame#promptInputContainer {
    background-color: #F1F3F4;
    border: 1px solid rgba(0, 0, 0, 30);
    border-radius: 20px;
}
QTextEdit#promptInput {
    background: transparent;
    color: #000000;
    border: none;
    padding: 2px 6px;
    font-size: 15px;
}
QPushButton#sendButton {
    background-color: #1A73E8;
    color: white;
    border: none;
    border-radius: 20px;
    padding: 10px 22px;
    font-size: 15px;
}
QPushButton#sendButton:hover { background-color: #4285F4; }
QPushButton#composerIconButton {
    background-color: rgba(255, 255, 255, 18);
    border: none;
    border-radius: 20px;
    color: #C4C7C5;
    font-size: 16px;
}
QPushButton#composerIconButton:hover { background-color: rgba(255, 255, 255, 30); color: #E8EAED; }
QPushButton#iconButton {
    background: transparent;
    border: none;
    color: #C4C7C5;
    font-size: 17px;
    padding: 4px 8px;
}
QPushButton#iconButton:hover { color: #E8EAED; }
"""


def _qpixmap_to_pil(pixmap: QPixmap) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODeviceBase.OpenModeFlag.ReadWrite)
    pixmap.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return Image.open(BytesIO(data)).convert("RGB")


class GeminiStreamWorker(QThread):
    """Runs a (possibly multi-image) Gemini stream off the UI thread."""

    chunk_received = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, service: GeminiService, prompt: str, images: list | None = None):
        super().__init__()
        self.service = service
        self.prompt = prompt
        self.images = images or []

    def run(self):
        full_text = ""
        try:
            stream = (
                self.service.send_prompt_stream(self.images, self.prompt)
                if self.images
                else self.service.send_text_stream(self.prompt)
            )
            for chunk in stream:
                full_text += chunk
                self.chunk_received.emit(full_text)
            self.finished_ok.emit(full_text)
        except Exception as exc:  # noqa: BLE001 - surfaced to the chat bubble, not swallowed
            self.failed.emit(str(exc))


class TitleWorker(QThread):
    """Summarizes a thread's first message into a short title, off the UI thread."""

    title_ready = pyqtSignal(str)
    failed = pyqtSignal()

    def __init__(self, service: GeminiService, first_message: str):
        super().__init__()
        self.service = service
        self.first_message = first_message

    def run(self):
        try:
            title = self.service.generate_title(self.first_message)
            if title:
                self.title_ready.emit(title)
            else:
                self.failed.emit()
        except Exception:  # noqa: BLE001 - auto-titling is best-effort, never fatal
            self.failed.emit()


class _TitleBar(QWidget):
    """Drag handle for the frameless window."""

    def __init__(self, target: QWidget, parent=None):
        super().__init__(parent)
        self._target = target
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._target.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._target.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class _ComposerInput(QTextEdit):
    """Auto-expanding chat input: plain Enter sends, Shift+Enter inserts a newline.

    Deliberately flat/borderless (no background, no border-radius, no frame of
    its own) - _ComposerInputContainer supplies the rounded pill visuals. A
    QTextEdit's internal viewport/scrollbar don't reliably respect a
    border-radius applied directly to the QTextEdit itself, which let text and
    the scrollbar bleed past the rounded corners; styling the *outer* QFrame
    instead and keeping this widget purely rectangular avoids that entirely.

    This widget MEASURES its content but never resizes itself - see
    _ComposerInputContainer, which owns the height of both widgets.
    """

    submitted = pyqtSignal()
    contentHeightChanged = pyqtSignal(int)

    MIN_HEIGHT = 40
    MAX_HEIGHT = 120
    # QSS `padding: 2px 6px` on #promptInput, plus 4px of slack. Named so the
    # arithmetic in _adjust_height is auditable instead of a magic "+ 8".
    _CHROME = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("promptInput")
        self.setPlaceholderText("Ask Gemini about this capture...")
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(self.MIN_HEIGHT)

        self._reported_height = self.MIN_HEIGHT
        self._adjust_pending = False

        # documentSizeChanged rather than textChanged: it also fires when the
        # text re-wraps because the window was resized, which textChanged
        # misses (that's why the composer used to keep a stale height until you
        # typed again).
        self.document().documentLayout().documentSizeChanged.connect(self._schedule_adjust)

        # Solid black, thicker caret: the QSS `color` alone isn't reliably
        # honored for the blinking text cursor on every Qt style, so the
        # palette's Text role is set explicitly as well.
        self.setCursorWidth(2)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        self.setPalette(palette)

    # ---- Enter sends, Shift+Enter newlines --------------------------------
    # This MUST live on the QTextEdit, not on the container QFrame: the frame
    # has NoFocus and never sees key events, and QTextEdit accepts Return
    # itself so the event never propagates up either.
    def keyPressEvent(self, event):
        is_return = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if is_return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)

    # ---- Auto-grow ---------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_adjust()

    def _schedule_adjust(self, *_):
        """Coalesce height recalculation onto the next event-loop turn.

        documentSizeChanged and resizeEvent both fire while Qt is *inside* a
        layout pass. Mutating widget geometry from there re-enters the layout
        engine and lets the backing store's size disagree with the rect handed
        to UpdateLayeredWindowIndirect. Deferring guarantees the resize happens
        between events, against a settled layout, and still lands before the
        next paint - so growth reads as immediate.
        """
        if self._adjust_pending:
            return
        self._adjust_pending = True
        QTimer.singleShot(0, self._adjust_height)

    def _adjust_height(self):
        self._adjust_pending = False
        document = self.document()

        # document().size() is only meaningful once the wrap width matches the
        # real viewport; before the first show() it is still the default, which
        # is how a nonsense height used to reach setFixedHeight().
        viewport_width = max(1, self.viewport().width())
        if abs(document.textWidth() - viewport_width) > 0.5:
            document.setTextWidth(viewport_width)

        content = document.size().height() + self._CHROME + 2 * self.frameWidth()
        new_height = int(max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, round(content))))
        if new_height == self._reported_height:
            return
        self._reported_height = new_height
        self.contentHeightChanged.emit(new_height)


class _ComposerInputContainer(QFrame):
    """Owns the rounded pill background AND the height of both itself and the
    inner QTextEdit. A single writer for both geometries means there is never a
    frame in which the child is taller than the frame that clips it - which is
    what used to hand the top-level layered window a dirty rect it could not
    validate."""

    MARGIN = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("promptInputContainer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        layout.setSpacing(0)

        self.text_edit = _ComposerInput()
        self.text_edit.contentHeightChanged.connect(self._apply_height)
        layout.addWidget(self.text_edit)

        self._apply_height(self.text_edit.MIN_HEIGHT)

    def _apply_height(self, text_edit_height: int):
        frame_height = text_edit_height + self.MARGIN * 2
        # Compare against minimumHeight(), not height(): setFixedHeight() is an
        # exact record of the last value we applied, whereas height() lags
        # until the layout actually runs.
        if (frame_height == self.minimumHeight()
                and text_edit_height == self.text_edit.minimumHeight()):
            return

        # Parent first, then child: the clip region is always >= the widget it
        # clips, never the other way round.
        self.setFixedHeight(frame_height)
        self.text_edit.setFixedHeight(text_edit_height)
        self.updateGeometry()

        # Deliberately NO parent.layout().activate() here. Forcing a synchronous
        # relayout of the composer row from inside a text-layout/resize callback
        # is a direct trigger for "UpdateLayeredWindowIndirect failed ... The
        # parameter is incorrect." Qt lays this row out on the next event-loop
        # turn, before the next paint, which is visually indistinguishable.


class _AttachmentThumb(QWidget):
    """A staged-attachment preview with an overlay 'x' delete button in its top-right corner."""

    removed = pyqtSignal(object)

    SIZE = 56

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE + 4)

        self.image_label = QLabel(self)
        self.image_label.setGeometry(0, 4, self.SIZE, self.SIZE - 4)
        self.image_label.setScaledContents(True)
        self.image_label.setPixmap(pixmap)
        self.image_label.setStyleSheet("border-radius: 8px;")

        self.remove_btn = QPushButton("×", self)
        self.remove_btn.setGeometry(self.SIZE - 18, 0, 18, 18)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setStyleSheet(
            "QPushButton { background-color: #D93025; color: white; border: none; "
            "border-radius: 9px; font-size: 12px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background-color: #B3261E; }"
        )
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))


class MainWindow(QWidget):
    """Translucent, frameless, resizable chat overlay with streaming Gemini replies."""

    capture_requested = pyqtSignal()

    def __init__(self, gemini_service: GeminiService | None = None):
        super().__init__()
        self.setWindowTitle("GSight")
        # Stays pinned above other apps and never auto-hides on focus loss: no
        # focusOutEvent/changeEvent override exists on this class, and none should
        # be added - closing/hiding only happens via the explicit "x" button,
        # the tray menu, or main.py hiding it while the snipper is active.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(700, 800)
        self.setMinimumSize(600, 700)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.gemini_service = gemini_service or GeminiService()
        self.current_thread_id: str | None = None
        self._pending_images: list[QPixmap] = []
        self._attachment_thumbs: list[_AttachmentThumb] = []
        self._stream_worker: GeminiStreamWorker | None = None
        self._title_worker: TitleWorker | None = None
        self._gemini_bubble: MessageBubble | None = None
        self._needs_title = False
        # In-memory mirror of the persisted threads, keyed by session/thread id,
        # so the sidebar can render without re-reading config.json on every click.
        self.sessions: dict[str, list] = {}

        self._build_ui()
        self._refresh_sidebar()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        # The drop shadow below is painted OUTSIDE self.container's own rect.
        # QGraphicsDropShadowEffect.boundingRectFor() expands by
        # blurRadius * 3/2 and then unites with the offset copy, so these
        # margins MUST be >= that expansion. If they aren't, the effect's
        # dirty rect lands outside this (layered, WA_TranslucentBackground)
        # top-level window and Win32 rejects the update with
        # "UpdateLayeredWindowIndirect failed ... The parameter is incorrect."
        # blur 16 -> 24px expansion; offset (0, 4) -> 28px needed at the bottom.
        root.setContentsMargins(28, 26, 28, 30)
        root.setSpacing(0)

        # The chat pane is the ONLY widget in the layout - it always fills the
        # full window width. The sidebar is built separately below and floats
        # on top of it as an absolutely-positioned overlay (see
        # _position_sidebar_overlay), so opening/closing it never resizes or
        # displaces the chat view.
        self.container = QFrame(self)
        self.container.setObjectName("glassContainer")
        self.container.setStyleSheet(GLASS_STYLE)
        root.addWidget(self.container)

        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(16)                 # 16 * 3/2 = 24 <= margins above
        shadow.setOffset(0, 4)                   # 24 + 4 = 28 <= bottom margin (30)
        shadow.setColor(QColor(0, 0, 0, 110))    # denser, to offset the smaller blur
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(10)

        self.title_bar = self._build_title_bar()
        layout.addWidget(self.title_bar)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_body = QWidget()
        self.chat_body.setObjectName("chatBody")
        self.chat_layout = QVBoxLayout(self.chat_body)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_body)
        layout.addWidget(self.chat_scroll, stretch=1)

        layout.addLayout(self._build_composer())

        grip_row = QHBoxLayout()
        grip_row.addStretch()
        grip_row.addWidget(QSizeGrip(self.container))
        layout.addLayout(grip_row)

        # Overlay drawer: parented to the glass container (not the layout), so
        # it floats above the chat content instead of taking up layout space.
        #
        # Deliberately NOT given a QGraphicsDropShadowEffect or its own
        # WA_TranslucentBackground: stacking a second layered/composited
        # surface on a child of an already-translucent top-level window is
        # what triggers Windows' "UpdateLayeredWindowIndirect failed" error
        # when the overlay is repositioned/raised. WA_TranslucentBackground
        # must only ever be set on `self` (the top-level MainWindow); the
        # solid QSS background below is what gives it definition instead.
        self.sidebar = self._build_sidebar()
        self.sidebar.setParent(self.container)
        self.sidebar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.sidebar.hide()

        self._position_sidebar_overlay()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(GLASS_STYLE)
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        new_chat_btn = QPushButton("✚  New Chat")
        new_chat_btn.setObjectName("newChatButton")
        new_chat_btn.setFixedHeight(44)
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.clicked.connect(self._on_new_chat_clicked)
        layout.addWidget(new_chat_btn)

        self.sidebar_list = QListWidget()
        self.sidebar_list.setObjectName("sidebarList")
        self.sidebar_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sidebar_list.setAutoFillBackground(True)
        self.sidebar_list.viewport().setAutoFillBackground(True)
        self.sidebar_list.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.sidebar_list.currentItemChanged.connect(self._on_sidebar_item_changed)
        self.sidebar_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sidebar_list.customContextMenuRequested.connect(self._on_sidebar_context_menu)
        self.sidebar_list.itemChanged.connect(self._on_sidebar_item_renamed)
        # Repaint the viewport background fully on every update instead of
        # caching/compositing over the previous frame - that accumulation is
        # what let translucent hover rects stack into a solid grey block.
        self.sidebar_list.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.sidebar_list.setMouseTracking(True)
        layout.addWidget(self.sidebar_list, stretch=1)

        return sidebar

    def _build_title_bar(self) -> QWidget:
        bar = _TitleBar(self)
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)

        sidebar_toggle_btn = QPushButton("☰")
        sidebar_toggle_btn.setObjectName("iconButton")
        sidebar_toggle_btn.setToolTip("Toggle chat history")
        sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        row.addWidget(sidebar_toggle_btn)

        icon_label = QLabel()
        if ICON_PATH.exists():
            icon_label.setPixmap(
                QPixmap(str(ICON_PATH)).scaled(
                    20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
        row.addWidget(icon_label)

        title = QLabel("GSight")
        title.setObjectName("titleLabel")
        row.addWidget(title)
        row.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("iconButton")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._open_settings)
        row.addWidget(settings_btn)

        # Only these two buttons ever hide/minimize the window - no click-outside
        # or focus-loss handler exists (see the comment in __init__).
        minimize_btn = QPushButton("—")
        minimize_btn.setObjectName("iconButton")
        minimize_btn.setToolTip("Minimize")
        minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minimize_btn.clicked.connect(self.showMinimized)
        row.addWidget(minimize_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("iconButton")
        close_btn.setToolTip("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        row.addWidget(close_btn)

        return bar

    def _build_composer(self) -> QVBoxLayout:
        col = QVBoxLayout()

        self.attachment_row_widget = QWidget()
        self.attachment_row = QHBoxLayout(self.attachment_row_widget)
        self.attachment_row.setContentsMargins(0, 0, 0, 0)
        self.attachment_row.setSpacing(6)
        self.attachment_row.addStretch()
        self.attachment_row_widget.setVisible(False)
        col.addWidget(self.attachment_row_widget)

        input_row = QHBoxLayout()
        input_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self.prompt_input_container = _ComposerInputContainer()
        self.prompt_input = self.prompt_input_container.text_edit
        self.prompt_input.submitted.connect(self._on_submit)
        input_row.addWidget(self.prompt_input_container, stretch=1)

        # Camera/screenshot button lives here, standard action size, right next
        # to Send - not in the title bar.
        capture_btn = QPushButton("📷")
        capture_btn.setObjectName("composerIconButton")
        capture_btn.setToolTip("New capture (Ctrl+Shift+S)")
        capture_btn.setFixedSize(40, 40)
        capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        capture_btn.clicked.connect(self.capture_requested.emit)
        input_row.addWidget(capture_btn)

        send_btn = QPushButton("Send")
        send_btn.setObjectName("sendButton")
        send_btn.setFixedHeight(40)
        send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(send_btn)

        col.addLayout(input_row)
        return col

    # ---- Thread management -------------------------------------------------

    def load_thread(self, thread_id: str):
        thread = get_thread(thread_id)
        if thread is None:
            return
        self.current_thread_id = thread_id
        self._needs_title = False
        self._clear_chat_body()
        for message in thread["messages"]:
            image_paths = message.get("images") or []
            pixmaps = [QPixmap(p) for p in image_paths if p and Path(p).exists()]
            self._append_bubble(message["role"], message["text"], pixmaps)
        self._scroll_to_bottom()
        self._refresh_sidebar()

    def start_new_thread(self, name: str | None = None) -> str:
        thread = create_thread(name)
        self.current_thread_id = thread["id"]
        # Auto-title kicks in after this thread's first user message, unless it
        # was given an explicit name up front (e.g. future callers that pass one).
        self._needs_title = name is None
        self._clear_chat_body()
        telemetry.capture("chat_created")
        self._refresh_sidebar()
        return thread["id"]

    def _clear_chat_body(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ---- Sidebar -------------------------------------------------

    def _toggle_sidebar(self):
        # Position BEFORE showing/raising: raise_()-ing a widget whose geometry
        # is still stale (or hasn't been computed yet) is what can push the
        # Win32 layered-window update outside the top-level window's actual
        # bounds and trigger "UpdateLayeredWindowIndirect failed".
        now_visible = not self.sidebar.isVisible()
        if now_visible:
            self._position_sidebar_overlay()
        self.sidebar.setVisible(now_visible)
        if now_visible:
            self.sidebar.raise_()

    def _position_sidebar_overlay(self):
        """Keeps the drawer floating over the chat area, below the title bar (so
        the ☰ toggle button - which never moves - stays reachable while it's
        open), without ever touching the chat pane's own layout/geometry."""
        if not hasattr(self, "sidebar") or not hasattr(self, "title_bar"):
            return
        margin = 8
        top = self.title_bar.geometry().bottom() + margin
        height = self.container.height() - top - margin
        # Guard against degenerate geometry during the earliest layout pass
        # (container not yet sized) - never hand Qt/Win32 a bogus rect.
        if height <= 0 or self.container.width() <= 0:
            return
        self.sidebar.setGeometry(margin, top, self.sidebar.width(), max(120, height))

    def _refresh_sidebar(self):
        threads = list_threads()
        self.sessions = {thread["id"]: thread["messages"] for thread in threads}

        self.sidebar_list.blockSignals(True)
        self.sidebar_list.clear()
        for thread in reversed(threads):
            item = QListWidgetItem(thread["name"])
            item.setData(Qt.ItemDataRole.UserRole, thread["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.sidebar_list.addItem(item)
            if thread["id"] == self.current_thread_id:
                self.sidebar_list.setCurrentItem(item)
        self.sidebar_list.blockSignals(False)

    def _on_new_chat_clicked(self):
        self.start_new_thread()

    def _on_sidebar_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        if current is None:
            return
        thread_id = current.data(Qt.ItemDataRole.UserRole)
        if thread_id and thread_id != self.current_thread_id:
            self.load_thread(thread_id)

    def _on_sidebar_context_menu(self, pos):
        item = self.sidebar_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        chosen = menu.exec(self.sidebar_list.mapToGlobal(pos))
        if chosen == rename_action:
            self.sidebar_list.editItem(item)

    def _on_sidebar_item_renamed(self, item: QListWidgetItem):
        thread_id = item.data(Qt.ItemDataRole.UserRole)
        new_name = item.text().strip()
        if not thread_id or not new_name:
            return
        rename_thread(thread_id, new_name)
        self._refresh_sidebar()

    def _maybe_auto_title(self, thread_id: str, first_message: str):
        if not self._needs_title:
            return
        self._needs_title = False
        self._title_worker = TitleWorker(self.gemini_service, first_message)
        self._title_worker.title_ready.connect(lambda title: self._on_title_ready(thread_id, title))
        self._title_worker.start()

    def _on_title_ready(self, thread_id: str, title: str):
        rename_thread(thread_id, title)
        self._refresh_sidebar()

    # ---- Attachments -------------------------------------------------

    def add_attachment(self, pixmap: QPixmap):
        if len(self._pending_images) >= MAX_ATTACHMENTS:
            return
        self._pending_images.append(pixmap)
        thumb = _AttachmentThumb(pixmap)
        thumb.removed.connect(self._remove_attachment)
        self._attachment_thumbs.append(thumb)
        self.attachment_row.insertWidget(self.attachment_row.count() - 1, thumb)
        self.attachment_row_widget.setVisible(True)

    def _remove_attachment(self, thumb: _AttachmentThumb):
        if thumb in self._attachment_thumbs:
            index = self._attachment_thumbs.index(thumb)
            self._attachment_thumbs.pop(index)
            self._pending_images.pop(index)
        thumb.setParent(None)
        thumb.deleteLater()
        self.attachment_row_widget.setVisible(len(self._pending_images) > 0)

    def _clear_attachments(self):
        self._pending_images = []
        for thumb in self._attachment_thumbs:
            thumb.setParent(None)
            thumb.deleteLater()
        self._attachment_thumbs = []
        self.attachment_row_widget.setVisible(False)

    def focus_composer(self):
        self.prompt_input.setFocus()

    def _save_attachment(self, pixmap: QPixmap) -> str:
        ensure_captures_dir()
        path = CAPTURES_DIR / f"{uuid.uuid4().hex}.png"
        pixmap.save(str(path), "PNG")
        return str(path)

    # ---- Chat bubbles -------------------------------------------------

    def _current_bubble_max_width(self) -> int:
        if not hasattr(self, "chat_scroll"):
            return DEFAULT_BUBBLE_MAX_WIDTH
        return max(240, int(self.chat_scroll.viewport().width() * 0.72))

    def _append_bubble(self, role: str, text: str, images: list | None = None) -> MessageBubble:
        bubble = MessageBubble(role, text, images or [])
        bubble.set_max_bubble_width(self._current_bubble_max_width())
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        return bubble

    def _scroll_to_bottom(self):
        QTimer.singleShot(
            0,
            lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            ),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bubble_widths()
        self._position_sidebar_overlay()

    def _update_bubble_widths(self):
        # Bubbles reflow with the window instead of staying pinned to whatever
        # width was current when each one was created.
        if not hasattr(self, "chat_layout"):
            return
        max_width = self._current_bubble_max_width()
        for i in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, MessageBubble):
                widget.set_max_bubble_width(max_width)

    # ---- Sending -------------------------------------------------

    def _on_submit(self):
        text = self.prompt_input.toPlainText().strip()
        if not text or self.current_thread_id is None:
            return

        thread_id = self.current_thread_id
        pixmaps = list(self._pending_images)
        image_paths = [self._save_attachment(p) for p in pixmaps]

        self._append_bubble("user", text, pixmaps)
        add_message(thread_id, "user", text, image_paths)
        self._maybe_auto_title(thread_id, text)
        self._refresh_sidebar()
        self.prompt_input.clear()
        self._clear_attachments()

        self._gemini_bubble = self._append_bubble("gemini", "")
        self._scroll_to_bottom()

        pil_images = [_qpixmap_to_pil(p) for p in pixmaps]
        self._stream_worker = GeminiStreamWorker(self.gemini_service, text, pil_images)
        self._stream_worker.chunk_received.connect(self._on_stream_chunk)
        self._stream_worker.finished_ok.connect(self._on_stream_finished)
        self._stream_worker.failed.connect(self._on_stream_failed)
        self._stream_worker.start()

    def _on_stream_chunk(self, partial_text: str):
        if self._gemini_bubble is not None:
            self._gemini_bubble.set_text(partial_text)
            self._scroll_to_bottom()

    def _on_stream_finished(self, full_text: str):
        if self.current_thread_id:
            add_message(self.current_thread_id, "gemini", full_text)
            self._refresh_sidebar()
        self._gemini_bubble = None

    def _on_stream_failed(self, error_message: str):
        if self._gemini_bubble is not None:
            self._gemini_bubble.set_text(f"⚠️ Gemini request failed: {error_message}")
        telemetry.capture("api_error_raised", {"stage": "stream"})
        self._gemini_bubble = None

    def _open_settings(self):
        SettingsDialog(self).exec()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    thread_id = window.start_new_thread("Preview")
    window._append_bubble("gemini", "Hi! Snip something and ask me about it.\n\n```python\ndef greet():\n    return 'hello'\n```")
    window.show()
    sys.exit(app.exec())
