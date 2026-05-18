from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QWheelEvent

from loaders.dxf_loader import load_dxf


class Cad2DViewerWidget(QGraphicsView):
    _ZOOM_STEP = 1.25
    _MIN_ZOOM = 0.0001
    _MAX_ZOOM = 10000.0
    _ENTITY_COLOR = QColor(200, 200, 200)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._zoom: float = 1.0

        self.setRenderHints(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.black)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, file_path: str) -> None:
        self._scene.clear()
        self._zoom = 1.0
        self.resetTransform()
        try:
            dxf_path = load_dxf(file_path)
        except Exception as exc:
            QMessageBox.warning(self, "DXF 오류", f"파일을 열 수 없습니다:\n{exc}")
            return
        if dxf_path.isEmpty():
            return
        pen = QPen(self._ENTITY_COLOR, 0)  # cosmetic pen — always 1 px regardless of zoom
        self._scene.addPath(dxf_path, pen)
        self._scene.setSceneRect(dxf_path.boundingRect().adjusted(-10, -10, 10, 10))
        self.fit()

    def fit(self) -> None:
        if self._scene.items():
            self.fitInView(self._scene.itemsBoundingRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self) -> None:
        self._apply_zoom(self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / self._ZOOM_STEP)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = self._zoom * factor
        if not (self._MIN_ZOOM <= new_zoom <= self._MAX_ZOOM):
            return
        self._zoom = new_zoom
        self.scale(factor, factor)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._apply_zoom(self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP)
        event.accept()
