"""Chat message bubbles: iMessage-style user bubbles, Gemini glass bubbles with Markdown + code highlighting."""

import re

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QTextEdit

from ui.highlighter import CodeHighlighter

CODE_FENCE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)

DEFAULT_BUBBLE_MAX_WIDTH = 320

THINKING_LABEL = "Thinking"
THINKING_MAX_DOTS = 3
THINKING_INTERVAL_MS = 400

# Solid, fully-opaque hex fills (no rgba alpha) on both bubble frames - the
# chat scroll area behind them carries its own translucent glass tint
# (ui/window.py's #chatBody), so the bubbles themselves must stay 100% opaque
# or message text loses contrast/crispness against whatever peeks through.
# Dark slate/blue palette to match the app's dark glass theme.
USER_BUBBLE_STYLE = """
QFrame#bubble { background-color: #1A73E8; border-radius: 16px; }
QLabel { color: white; background: transparent; }
"""

GEMINI_BUBBLE_STYLE = """
QFrame#bubble {
    background-color: #363B44;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 16px;
}
QLabel { color: #F1F3F5; background: transparent; }
"""

# Code blocks stay dark regardless of the overall theme - conventional and
# most readable for monospace content either way.
CODE_BLOCK_STYLE = """
QTextEdit {
    background-color: rgba(0, 0, 0, 90);
    color: #d8dee9;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 8px;
    padding: 8px;
}
"""


def _split_segments(text: str) -> list:
    """Split markdown text into ('text', str) / ('code', code) segments on ``` fences."""
    segments = []
    cursor = 0
    for match in CODE_FENCE_RE.finditer(text):
        if match.start() > cursor:
            segments.append(("text", text[cursor:match.start()]))
        segments.append(("code", match.group(2).strip("\n")))
        cursor = match.end()
    if cursor < len(text):
        segments.append(("text", text[cursor:]))
    if not segments:
        segments.append(("text", text))
    return segments


class MessageBubble(QWidget):
    """A single chat message: right-aligned blue bubble for the user, left-aligned card for Gemini."""

    def __init__(self, role: str, text: str = "", images: list | None = None, parent=None):
        super().__init__(parent)
        self.role = role
        self._is_user = role == "user"

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        self.bubble = QFrame()
        self.bubble.setObjectName("bubble")
        self.bubble.setStyleSheet(USER_BUBBLE_STYLE if self._is_user else GEMINI_BUBBLE_STYLE)
        self.bubble.setMaximumWidth(DEFAULT_BUBBLE_MAX_WIDTH)

        self._layout = QVBoxLayout(self.bubble)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(6)

        images = images or []
        if images:
            self._layout.addWidget(self._build_image_row(images))

        self._text_container = QVBoxLayout()
        self._text_container.setSpacing(6)
        self._layout.addLayout(self._text_container)

        if self._is_user:
            outer.addStretch()
            outer.addWidget(self.bubble)
        else:
            outer.addWidget(self.bubble)
            outer.addStretch()

        if text:
            self.set_text(text)
        elif not self._is_user:
            self._start_thinking_animation()

    def set_max_bubble_width(self, width: int):
        """Called by MainWindow.resizeEvent so bubbles reflow with the window instead
        of staying pinned to their initial (creation-time) width."""
        self.bubble.setMaximumWidth(max(180, width))

    @staticmethod
    def _build_image_row(images: list) -> QWidget:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        thumb_size = 120 if len(images) == 1 else 90
        for pixmap in images[:5]:
            thumb = QLabel()
            thumb.setFixedSize(thumb_size, thumb_size)
            thumb.setScaledContents(True)
            thumb.setPixmap(
                pixmap.scaled(
                    thumb_size, thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            thumb.setStyleSheet("border-radius: 10px;")
            row.addWidget(thumb)
        row.addStretch()
        return row_widget

    def set_text(self, text: str):
        """Replace the bubble's rendered content (Markdown + syntax-highlighted code blocks).
        Halts the "Thinking…" animation, if one is running, before rendering."""
        if hasattr(self, "loading_timer") and self.loading_timer.isActive():
            self.loading_timer.stop()
        self._render_text(text)

    def _render_text(self, text: str):
        while self._text_container.count():
            item = self._text_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for kind, content in _split_segments(text):
            if kind == "code":
                self._text_container.addWidget(self._build_code_widget(content))
            elif content.strip():
                self._text_container.addWidget(self._build_text_label(content.strip()))

    def _start_thinking_animation(self):
        """Show an animated "Thinking ." -> "Thinking .." -> "Thinking ..." loop
        until real content arrives via set_text()."""
        self._thinking_dots = 1
        self._render_text(f"{THINKING_LABEL} {'.' * self._thinking_dots}")

        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(THINKING_INTERVAL_MS)
        self.loading_timer.timeout.connect(self._animate_dots)
        self.loading_timer.start()

    def _animate_dots(self):
        self._thinking_dots = (self._thinking_dots % THINKING_MAX_DOTS) + 1
        self._render_text(f"{THINKING_LABEL} {'.' * self._thinking_dots}")

    @staticmethod
    def _build_text_label(text: str) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.MarkdownText)
        label.setText(text)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label

    @staticmethod
    def _build_code_widget(code: str) -> QTextEdit:
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(code)
        editor.setStyleSheet(CODE_BLOCK_STYLE)
        editor.setFont(QFont("Consolas", 10))
        editor.setFixedHeight(min(200, 30 + code.count("\n") * 16))
        editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        CodeHighlighter(editor.document())
        return editor
