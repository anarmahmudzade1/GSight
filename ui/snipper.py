"""Full-screen translucent drag-to-crop snippet widget."""

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap
from PyQt6.QtWidgets import QWidget, QApplication


class SnipperOverlay(QWidget):
    """Covers the full virtual desktop; user drags a rectangle to capture it."""

    captured = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._origin = None
        self._current_rect = QRect()

        self.setGeometry(self._virtual_desktop_geometry())

    @staticmethod
    def _virtual_desktop_geometry() -> QRect:
        geometry = QRect()
        for screen in QApplication.screens():
            geometry = geometry.united(screen.geometry())
        return geometry

    def showEvent(self, event):
        self._origin = None
        self._current_rect = QRect()
        self.raise_()
        self.activateWindow()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if not self._current_rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._current_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            pen = QPen(QColor(0, 200, 255), 2)
            painter.setPen(pen)
            painter.drawRect(self._current_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.pos()
            self._current_rect = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            self._current_rect = QRect(self._origin, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return

        rect = QRect(self._origin, event.pos()).normalized()
        self._origin = None
        self._current_rect = QRect()
        self.hide()

        if rect.width() > 2 and rect.height() > 2:
            screen = QApplication.primaryScreen()
            global_rect = rect.translated(self.geometry().topLeft())
            pixmap = screen.grabWindow(
                0,
                global_rect.x(),
                global_rect.y(),
                global_rect.width(),
                global_rect.height(),
            )
            self.captured.emit(pixmap)
        else:
            self.cancelled.emit()

        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._origin = None
            self._current_rect = QRect()
            self.hide()
            self.cancelled.emit()
            self.close()
