"""Main translucent overlay window & chat sidebar."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QFrame,
)


class MainWindow(QWidget):
    """Translucent chat overlay showing the latest capture and Gemini conversation."""

    prompt_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GSight")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(420, 560)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet(
            "#container { background-color: rgba(20, 20, 24, 220); border-radius: 12px; }"
            "QLabel { color: #e8e8e8; }"
            "QListWidget { background: transparent; color: #e8e8e8; border: none; }"
            "QLineEdit {"
            "  background-color: rgba(255, 255, 255, 20); color: #e8e8e8;"
            "  border: 1px solid rgba(255, 255, 255, 40); border-radius: 6px; padding: 6px;"
            "}"
            "QPushButton {"
            "  background-color: #3d7eff; color: white; border: none;"
            "  border-radius: 6px; padding: 6px 14px;"
            "}"
            "QPushButton:hover { background-color: #5a90ff; }"
        )
        root.addWidget(container)

        layout = QVBoxLayout(container)

        title_bar = QHBoxLayout()
        title = QLabel("GSight")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        close_btn = QPushButton("x")
        close_btn.setFixedWidth(28)
        close_btn.clicked.connect(self.hide)
        title_bar.addWidget(title)
        title_bar.addStretch()
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        self.thumbnail_label = QLabel("No capture yet")
        self.thumbnail_label.setFixedHeight(160)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px dashed rgba(255,255,255,60); border-radius: 8px;")
        layout.addWidget(self.thumbnail_label)

        self.chat_list = QListWidget()
        layout.addWidget(self.chat_list, stretch=1)

        input_row = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Ask Gemini about this capture...")
        self.prompt_input.returnPressed.connect(self._on_submit)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.prompt_input)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

    def set_capture(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            self.thumbnail_label.width() or 380,
            160,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail_label.setPixmap(scaled)

    def add_message(self, role: str, text: str):
        self.chat_list.addItem(QListWidgetItem(f"{role}: {text}"))
        self.chat_list.scrollToBottom()

    def _on_submit(self):
        text = self.prompt_input.text().strip()
        if not text:
            return
        self.add_message("You", text)
        self.prompt_input.clear()
        self.prompt_submitted.emit(text)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.add_message("Gemini", "Hi! Snip something and ask me about it.")
    window.show()
    sys.exit(app.exec())
