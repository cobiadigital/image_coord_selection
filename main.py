#!/usr/bin/env python3
"""
Image coordinate selection tool.
Opens PNG files from data/ and lets you draw a marquee selection to get corner coordinates.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QWidget,
)

ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]


class ImageCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_pixmap = None  # original, unscaled
        self.pixmap = None         # scaled for display
        self.zoom = 1.0
        self.origin = QPoint()
        self.selection = QRect()   # in display coords
        self.drawing = False
        self.on_selection_changed = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def load(self, path):
        self.source_pixmap = QPixmap(str(path))
        self.zoom = 1.0
        self.selection = QRect()
        self._apply_zoom()

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.selection = QRect()
        self._apply_zoom()

    def _apply_zoom(self):
        if not self.source_pixmap:
            return
        w = int(self.source_pixmap.width() * self.zoom)
        h = int(self.source_pixmap.height() * self.zoom)
        self.pixmap = self.source_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setFixedSize(self.pixmap.size())
        self.update()

    def paintEvent(self, _event):
        if not self.pixmap:
            return
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
        if not self.selection.isNull():
            pen = QPen(QColor("red"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.selection.normalized())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.selection = QRect(self.origin, self.origin)
            self.drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.selection = QRect(self.origin, event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            self.selection = QRect(self.origin, event.pos()).normalized()
            self.update()
            if self.on_selection_changed:
                # Convert display coords back to original image coords
                r = self.selection
                x1 = int(r.left() / self.zoom)
                y1 = int(r.top() / self.zoom)
                x2 = int(r.right() / self.zoom)
                y2 = int(r.bottom() / self.zoom)
                self.on_selection_changed(x1, y1, x2, y2)


class MainWindow(QMainWindow):
    def __init__(self, images):
        super().__init__()
        self.images = images
        self.current_idx = 0
        self.selection = None

        self.setWindowTitle("Image Coord Selection")

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.prev_image)
        toolbar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_image)
        toolbar.addWidget(self.next_btn)

        self.file_label = QLabel()
        self.file_label.setFont(QFont("Helvetica", 13))
        self.file_label.setContentsMargins(12, 0, 12, 0)
        toolbar.addWidget(self.file_label)

        toolbar.addSeparator()

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFont(QFont("Courier", 11))
        self.zoom_label.setContentsMargins(6, 0, 6, 0)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(52)
        toolbar.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)

        toolbar.addSeparator()

        self.coords_label = QLabel("Draw a selection...")
        self.coords_label.setFont(QFont("Courier", 11))
        toolbar.addWidget(self.coords_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self.copy_coords)
        toolbar.addWidget(copy_btn)

        # Scrollable image area
        self.canvas = ImageCanvas()
        self.canvas.on_selection_changed = self.on_selection

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(scroll)

        self.load_image()

    def load_image(self):
        path = self.images[self.current_idx]
        self.file_label.setText(f"{path.name}  ({self.current_idx + 1}/{len(self.images)})")
        self.prev_btn.setEnabled(self.current_idx > 0)
        self.next_btn.setEnabled(self.current_idx < len(self.images) - 1)
        self.canvas.load(path)
        self.selection = None
        self.coords_label.setText("Draw a selection...")
        self.zoom_label.setText("100%")

        # Resize window to fit image (up to 90% of screen)
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(self.canvas.pixmap.width() + 20, int(screen.width() * 0.9))
        h = min(self.canvas.pixmap.height() + 80, int(screen.height() * 0.9))
        self.resize(w, h)

    def zoom_in(self):
        idx = self._zoom_index()
        if idx < len(ZOOM_STEPS) - 1:
            self._set_zoom(ZOOM_STEPS[idx + 1])

    def zoom_out(self):
        idx = self._zoom_index()
        if idx > 0:
            self._set_zoom(ZOOM_STEPS[idx - 1])

    def _zoom_index(self):
        zoom = self.canvas.zoom
        closest = min(range(len(ZOOM_STEPS)), key=lambda i: abs(ZOOM_STEPS[i] - zoom))
        return closest

    def _set_zoom(self, zoom):
        self.canvas.set_zoom(zoom)
        self.selection = None
        self.coords_label.setText("Draw a selection...")
        self.zoom_label.setText(f"{int(zoom * 100)}%")

    def on_selection(self, x1, y1, x2, y2):
        self.selection = (x1, y1, x2, y2)
        text = f"{x1}, {y1}, {x2}, {y2}"
        self.coords_label.setText(text)
        print(f"Selection: {text}")
        self.copy_coords()

    def copy_coords(self):
        if self.selection:
            x1, y1, x2, y2 = self.selection
            QApplication.clipboard().setText(f"{x1}, {y1}, {x2}, {y2}")

    def prev_image(self):
        self.current_idx -= 1
        self.load_image()

    def next_image(self):
        self.current_idx += 1
        self.load_image()


def main():
    images = sorted(Path("data").glob("*.png"))
    if not images:
        print("No PNG files found in data/")
        return

    app = QApplication(sys.argv)
    window = MainWindow(images)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
