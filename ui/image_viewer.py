from pathlib import Path

from PIL import Image
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QRubberBand,
)
from PyQt6.QtCore import Qt, QRectF, QPoint, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QWheelEvent

from loaders.image_loader import load_image, pil_to_pixmap
from ui.resize_dialog import ResizeDialog


class ImageViewerWidget(QGraphicsView):
    _MIN_ZOOM = 0.02
    _MAX_ZOOM = 32.0
    _ZOOM_STEP = 1.25
    _UNDO_MAX = 20

    crop_mode_exited = pyqtSignal()   # emitted when crop mode ends (crop done or cancelled)
    undo_available = pyqtSignal(bool) # True when history stack is non-empty

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = None
        self._pil_image: Image.Image | None = None
        self._file_path: str = ""
        self._zoom: float = 1.0
        self._history: list[Image.Image] = []

        self._crop_mode: bool = False
        self._rb: QRubberBand | None = None
        self._rb_origin = QPoint()

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, file_path: str) -> None:
        self._file_path = file_path
        self._pil_image = load_image(file_path)
        self._zoom = 1.0
        self._history.clear()
        self.undo_available.emit(False)
        if self._crop_mode:
            self._exit_crop_internal()
        self.resetTransform()
        self._refresh_scene()
        self.fit()

    def display_image(self, pil_image: Image.Image, file_path: str = "") -> None:
        """Apply an already-loaded PIL image (called after async load)."""
        self._file_path = file_path
        self._pil_image = pil_image
        self._zoom = 1.0
        self._history.clear()
        self.undo_available.emit(False)
        if self._crop_mode:
            self._exit_crop_internal()
        self.resetTransform()
        self._refresh_scene()
        self.fit()

    def zoom_in(self) -> None:
        self._apply_zoom(self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / self._ZOOM_STEP)

    def fit(self) -> None:
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def rotate_cw(self) -> None:
        if self._pil_image:
            self._push_history()
            self._pil_image = self._pil_image.transpose(Image.Transpose.ROTATE_270)
            self._refresh_scene()
            self.fit()

    def rotate_ccw(self) -> None:
        if self._pil_image:
            self._push_history()
            self._pil_image = self._pil_image.transpose(Image.Transpose.ROTATE_90)
            self._refresh_scene()
            self.fit()

    def undo(self) -> None:
        if not self._history:
            return
        self._pil_image = self._history.pop()
        self._refresh_scene()
        self.fit()
        self.undo_available.emit(bool(self._history))

    def enter_crop_mode(self) -> None:
        self._crop_mode = True
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def exit_crop_mode(self) -> None:
        """Public: called by MainWindow to cancel crop mode."""
        if self._crop_mode:
            self._exit_crop_internal()
            self.crop_mode_exited.emit()

    def open_resize_dialog(self) -> None:
        if self._pil_image is None:
            return
        w, h = self._pil_image.size
        dlg = ResizeDialog(w, h, self)
        if dlg.exec() == ResizeDialog.DialogCode.Accepted:
            nw, nh = dlg.result_size
            if (nw, nh) != (w, h):
                self._push_history()
                self._pil_image = self._pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
                self._refresh_scene()
                self.fit()

    def save_as(self) -> None:
        if self._pil_image is None:
            return
        stem = Path(self._file_path).stem if self._file_path else "image"
        folder = str(Path(self._file_path).parent) if self._file_path else ""
        default = f"{folder}/{stem}_copy" if folder else stem

        path, _ = QFileDialog.getSaveFileName(
            self, "다른 이름으로 저장", default,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tif *.tiff);;WebP (*.webp)",
        )
        if not path:
            return
        try:
            img = self._pil_image.copy()
            if Path(path).suffix.lower() in (".jpg", ".jpeg") and img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(path)
        except Exception as exc:
            QMessageBox.warning(self, "저장 실패", str(exc))

    @property
    def is_crop_mode(self) -> bool:
        return self._crop_mode

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _exit_crop_internal(self) -> None:
        self._crop_mode = False
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().unsetCursor()
        if self._rb:
            self._rb.hide()
            self._rb = None

    def _push_history(self) -> None:
        if self._pil_image is None:
            return
        self._history.append(self._pil_image.copy())
        if len(self._history) > self._UNDO_MAX:
            self._history.pop(0)
        self.undo_available.emit(True)

    def _refresh_scene(self) -> None:
        if self._pil_image is None:
            return
        pixmap = pil_to_pixmap(self._pil_image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = self._zoom * factor
        if not (self._MIN_ZOOM <= new_zoom <= self._MAX_ZOOM):
            return
        self._zoom = new_zoom
        self.scale(factor, factor)

    def _do_crop(self, viewport_rect: QRect) -> None:
        if self._pil_image is None:
            return
        tl = self.mapToScene(viewport_rect.topLeft())
        br = self.mapToScene(viewport_rect.bottomRight())
        img_w, img_h = self._pil_image.size
        x0 = max(0, int(tl.x()))
        y0 = max(0, int(tl.y()))
        x1 = min(img_w, int(br.x()))
        y1 = min(img_h, int(br.y()))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        self._push_history()
        self._pil_image = self._pil_image.crop((x0, y0, x1, y1))
        self._refresh_scene()
        self.fit()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if self._crop_mode and event.button() == Qt.MouseButton.LeftButton:
            self._rb_origin = event.pos()
            if self._rb is None:
                self._rb = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
            self._rb.setGeometry(QRect(self._rb_origin, QSize()))
            self._rb.show()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._crop_mode and self._rb is not None:
            self._rb.setGeometry(QRect(self._rb_origin, event.pos()).normalized())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._crop_mode and event.button() == Qt.MouseButton.LeftButton:
            rect = QRect(self._rb_origin, event.pos()).normalized()
            # exit first so crop_mode_exited fires before scene update
            self._exit_crop_internal()
            self.crop_mode_exited.emit()
            self._do_crop(rect)
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._crop_mode and event.key() == Qt.Key.Key_Escape:
            self.exit_crop_mode()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._apply_zoom(self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP)
        event.accept()
