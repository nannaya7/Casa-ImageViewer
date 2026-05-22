import math
from pathlib import Path

from PIL import Image
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QRubberBand, QWidget,
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
    _CROP_MIN_SIZE = 6
    _CROP_HANDLE_SIZE = 9
    _CROP_EDGE_GRAB = 5

    crop_mode_exited = pyqtSignal()   # kept for compatibility with older callers
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

        self._rb: QRubberBand | None = None
        self._rb_origin = QPoint()
        self._crop_rect = QRect()
        self._crop_scene_rect = QRectF()
        self._crop_action: str = ""
        self._crop_start_pos = QPoint()
        self._crop_start_rect = QRect()
        self._crop_handles: dict[str, QWidget] = {}
        self._pan_active = False
        self._pan_start_pos = QPoint()
        self._pan_start_h = 0
        self._pan_start_v = 0
        self._auto_resize = False

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
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
        self._cancel_crop_selection()
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
        self._cancel_crop_selection()
        self.resetTransform()
        self._refresh_scene()
        self.fit()

    def zoom_in(self) -> None:
        self._apply_zoom(self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / self._ZOOM_STEP)

    def fit(self) -> None:
        if self._pixmap_item:
            self.resetTransform()
            self._zoom = 1.0
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._update_crop_overlay_from_scene()

    def set_auto_resize(self, enabled: bool) -> None:
        self._auto_resize = enabled
        if enabled:
            self.fit()

    def rotate_cw(self) -> None:
        if self._pil_image:
            self._cancel_crop_selection()
            self._push_history()
            self._pil_image = self._pil_image.transpose(Image.Transpose.ROTATE_270)
            self._refresh_scene()
            self.fit()

    def rotate_ccw(self) -> None:
        if self._pil_image:
            self._cancel_crop_selection()
            self._push_history()
            self._pil_image = self._pil_image.transpose(Image.Transpose.ROTATE_90)
            self._refresh_scene()
            self.fit()

    def undo(self) -> None:
        if not self._history:
            return
        self._cancel_crop_selection()
        self._pil_image = self._history.pop()
        self._refresh_scene()
        self.fit()
        self.undo_available.emit(bool(self._history))

    def enter_crop_mode(self) -> None:
        """Compatibility no-op: cropping is always available while an image is shown."""
        self._cancel_crop_selection()

    def exit_crop_mode(self) -> None:
        """Cancel the current crop selection."""
        if self._crop_rect_is_usable() or self._crop_action:
            self._cancel_crop_selection()
            self.crop_mode_exited.emit()

    def open_resize_dialog(self) -> None:
        if self._pil_image is None:
            return
        w, h = self._pil_image.size
        dlg = ResizeDialog(w, h, self)
        if dlg.exec() == ResizeDialog.DialogCode.Accepted:
            nw, nh = dlg.result_size
            if (nw, nh) != (w, h):
                self._cancel_crop_selection()
                self._push_history()
                self._pil_image = self._pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
                self._refresh_scene()
                self.fit()

    def save_as(self) -> None:
        if self._pil_image is None:
            return
        stem = Path(self._file_path).stem if self._file_path else "image"
        folder = str(Path(self._file_path).parent) if self._file_path else ""
        default = str(Path(folder) / f"{stem}_copy.png") if folder else f"{stem}_copy.png"

        path, _ = QFileDialog.getSaveFileName(
            self, "다른 이름으로 저장", default,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tif *.tiff);;WebP (*.webp)",
        )
        if not path:
            return
        try:
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".png")
                path = str(target)
            img = self._pil_image.copy()
            if target.suffix.lower() in (".jpg", ".jpeg") and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(path)
        except Exception as exc:
            QMessageBox.warning(self, "저장 실패", str(exc))

    @property
    def is_crop_mode(self) -> bool:
        return self._crop_rect_is_usable() or bool(self._crop_action)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cancel_crop_selection(self) -> None:
        self._crop_action = ""
        self._crop_rect = QRect()
        self._crop_scene_rect = QRectF()
        self._pan_active = False
        self.viewport().unsetCursor()
        self._hide_crop_overlay()

    def _hide_crop_overlay(self) -> None:
        if self._rb:
            self._rb.hide()
        for handle in self._crop_handles.values():
            handle.hide()

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
        self._update_crop_overlay_from_scene()

    def _do_crop(self, scene_rect: QRectF) -> None:
        if self._pil_image is None:
            return
        rect = scene_rect.normalized()
        img_w, img_h = self._pil_image.size
        x0 = max(0, math.floor(rect.left()))
        y0 = max(0, math.floor(rect.top()))
        x1 = min(img_w, math.ceil(rect.right()))
        y1 = min(img_h, math.ceil(rect.bottom()))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        self._push_history()
        self._pil_image = self._pil_image.crop((x0, y0, x1, y1))
        self._refresh_scene()
        self.fit()

    def _ensure_crop_overlay(self) -> None:
        if self._rb is None:
            self._rb = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        if self._crop_handles:
            return
        for name in (
            "top_left", "top", "top_right", "right",
            "bottom_right", "bottom", "bottom_left", "left",
        ):
            handle = QWidget(self.viewport())
            handle.setFixedSize(self._CROP_HANDLE_SIZE, self._CROP_HANDLE_SIZE)
            handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            handle.setStyleSheet(
                "background-color: #F8F4EE;"
                "border: 1px solid #5F4632;"
                "border-radius: 2px;"
            )
            handle.hide()
            self._crop_handles[name] = handle

    def _set_crop_rect(self, rect: QRect, update_scene: bool = True) -> None:
        rect = rect.normalized().intersected(self.viewport().rect())
        self._crop_rect = rect
        if rect.width() < 1 or rect.height() < 1:
            if update_scene:
                self._crop_scene_rect = QRectF()
            self._hide_crop_overlay()
            return
        if update_scene:
            self._crop_scene_rect = self._viewport_rect_to_scene_rect(rect)

        self._ensure_crop_overlay()
        if self._rb is not None:
            self._rb.setGeometry(rect)
            self._rb.show()
        self._update_crop_handles()

    def _update_crop_handles(self) -> None:
        if not self._crop_rect.isValid() or self._crop_rect.isNull():
            self._hide_crop_overlay()
            return
        self._ensure_crop_overlay()
        for name, rect in self._crop_handle_rects().items():
            handle = self._crop_handles[name]
            handle.setGeometry(rect)
            handle.show()
            handle.raise_()

    def _crop_handle_rects(self) -> dict[str, QRect]:
        rect = self._crop_rect
        size = self._CROP_HANDLE_SIZE
        half = size // 2
        cx = rect.center().x()
        cy = rect.center().y()
        points = {
            "top_left": rect.topLeft(),
            "top": QPoint(cx, rect.top()),
            "top_right": rect.topRight(),
            "right": QPoint(rect.right(), cy),
            "bottom_right": rect.bottomRight(),
            "bottom": QPoint(cx, rect.bottom()),
            "bottom_left": rect.bottomLeft(),
            "left": QPoint(rect.left(), cy),
        }
        return {
            name: QRect(point.x() - half, point.y() - half, size, size)
            for name, point in points.items()
        }

    def _viewport_rect_to_scene_rect(self, rect: QRect) -> QRectF:
        tl = self.mapToScene(rect.topLeft())
        br = self.mapToScene(rect.bottomRight())
        return QRectF(tl, br).normalized()

    def _update_crop_overlay_from_scene(self) -> None:
        if self._crop_scene_rect.isNull() or not self._crop_scene_rect.isValid():
            return
        tl = self.mapFromScene(self._crop_scene_rect.topLeft())
        br = self.mapFromScene(self._crop_scene_rect.bottomRight())
        self._set_crop_rect(QRect(tl, br), update_scene=False)

    def _crop_hit_test(self, pos: QPoint) -> str:
        if (
            self._crop_rect.width() < self._CROP_MIN_SIZE
            or self._crop_rect.height() < self._CROP_MIN_SIZE
        ):
            return ""
        for name, rect in self._crop_handle_rects().items():
            if rect.contains(pos):
                return name

        outer = self._crop_rect.adjusted(
            -self._CROP_EDGE_GRAB,
            -self._CROP_EDGE_GRAB,
            self._CROP_EDGE_GRAB,
            self._CROP_EDGE_GRAB,
        )
        inner = self._crop_rect.adjusted(
            self._CROP_EDGE_GRAB,
            self._CROP_EDGE_GRAB,
            -self._CROP_EDGE_GRAB,
            -self._CROP_EDGE_GRAB,
        )
        if outer.contains(pos) and not inner.contains(pos):
            near_left = abs(pos.x() - self._crop_rect.left()) <= self._CROP_EDGE_GRAB
            near_right = abs(pos.x() - self._crop_rect.right()) <= self._CROP_EDGE_GRAB
            near_top = abs(pos.y() - self._crop_rect.top()) <= self._CROP_EDGE_GRAB
            near_bottom = abs(pos.y() - self._crop_rect.bottom()) <= self._CROP_EDGE_GRAB
            if near_top and near_left:
                return "top_left"
            if near_top and near_right:
                return "top_right"
            if near_bottom and near_left:
                return "bottom_left"
            if near_bottom and near_right:
                return "bottom_right"
            if near_left:
                return "left"
            if near_right:
                return "right"
            if near_top:
                return "top"
            if near_bottom:
                return "bottom"
        if self._crop_rect.contains(pos):
            return "inside"
        return ""

    def _update_crop_cursor(self, pos: QPoint) -> None:
        if self._pan_active:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        action = self._crop_action or self._crop_hit_test(pos)
        if not action and self._can_pan():
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            return

        cursor = {
            "top_left": Qt.CursorShape.SizeFDiagCursor,
            "bottom_right": Qt.CursorShape.SizeFDiagCursor,
            "top_right": Qt.CursorShape.SizeBDiagCursor,
            "bottom_left": Qt.CursorShape.SizeBDiagCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "inside": Qt.CursorShape.PointingHandCursor,
        }.get(action, Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(cursor)

    def _can_pan(self) -> bool:
        return (
            self.horizontalScrollBar().maximum() > self.horizontalScrollBar().minimum()
            or self.verticalScrollBar().maximum() > self.verticalScrollBar().minimum()
        )

    def _start_pan(self, pos: QPoint) -> None:
        self._pan_active = True
        self._pan_start_pos = pos
        self._pan_start_h = self.horizontalScrollBar().value()
        self._pan_start_v = self.verticalScrollBar().value()
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def _update_pan(self, pos: QPoint) -> None:
        delta = pos - self._pan_start_pos
        self.horizontalScrollBar().setValue(self._pan_start_h - delta.x())
        self.verticalScrollBar().setValue(self._pan_start_v - delta.y())

    def _clamp_to_viewport(self, pos: QPoint) -> QPoint:
        bounds = self.viewport().rect()
        return QPoint(
            max(bounds.left(), min(bounds.right(), pos.x())),
            max(bounds.top(), min(bounds.bottom(), pos.y())),
        )

    def _resize_crop_rect(self, action: str, pos: QPoint) -> QRect:
        pos = self._clamp_to_viewport(pos)
        rect = QRect(self._crop_start_rect)
        if "left" in action:
            rect.setLeft(pos.x())
        if "right" in action:
            rect.setRight(pos.x())
        if "top" in action:
            rect.setTop(pos.y())
        if "bottom" in action:
            rect.setBottom(pos.y())
        return rect.normalized()

    def _crop_rect_is_usable(self) -> bool:
        return (
            self._crop_rect.width() >= self._CROP_MIN_SIZE
            and self._crop_rect.height() >= self._CROP_MIN_SIZE
            and self._crop_scene_rect.isValid()
            and not self._crop_scene_rect.isNull()
        )

    def _commit_crop(self) -> None:
        if not self._crop_rect_is_usable():
            return
        rect = QRectF(self._crop_scene_rect)
        self._cancel_crop_selection()
        self._do_crop(rect)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if self._pil_image is not None and event.button() == Qt.MouseButton.RightButton and self._can_pan():
            self._start_pan(event.pos())
            event.accept()
            return

        if self._pil_image is not None and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            hit = self._crop_hit_test(pos)
            if hit == "inside":
                self._commit_crop()
                event.accept()
                return

            self._crop_action = hit or "draw"
            self._crop_start_pos = pos
            self._crop_start_rect = QRect(self._crop_rect)
            if self._crop_action == "draw":
                self._rb_origin = pos
                self._set_crop_rect(QRect(self._rb_origin, QSize()))
            self._update_crop_cursor(pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pil_image is not None:
            pos = event.pos()
            if self._pan_active:
                self._update_pan(pos)
            elif self._crop_action == "draw":
                self._set_crop_rect(QRect(self._rb_origin, pos))
            elif self._crop_action:
                self._set_crop_rect(self._resize_crop_rect(self._crop_action, pos))
            self._update_crop_cursor(pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._pil_image is not None and event.button() == Qt.MouseButton.RightButton:
            if self._pan_active:
                self._pan_active = False
                self._update_crop_cursor(event.pos())
            event.accept()
            return

        if self._pil_image is not None and event.button() == Qt.MouseButton.LeftButton:
            if not self._crop_rect_is_usable():
                self._crop_rect = QRect()
                self._crop_scene_rect = QRectF()
                self._hide_crop_overlay()
            self._crop_action = ""
            self._update_crop_cursor(event.pos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self.is_crop_mode:
            self._cancel_crop_selection()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._apply_zoom(self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP)
        event.accept()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._update_crop_overlay_from_scene()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_resize:
            self.fit()
        else:
            self._update_crop_overlay_from_scene()
