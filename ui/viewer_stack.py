from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QStackedWidget

from models.viewer_mode import ViewerMode
from ui.file_panel import FilePanelWidget

if TYPE_CHECKING:
    from ui.cad_viewer import Cad2DViewerWidget
    from ui.image_viewer import ImageViewerWidget
    from ui.model3d_viewer import Model3DViewerWidget


class ViewerStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_panel = FilePanelWidget()
        self._image_viewer: ImageViewerWidget | None = None
        self._cad_viewer: Cad2DViewerWidget | None = None
        self._model3d_viewer: Model3DViewerWidget | None = None

        self.addWidget(self._file_panel)       # 0

    @property
    def file_panel(self) -> FilePanelWidget:
        return self._file_panel

    @property
    def image_viewer(self) -> ImageViewerWidget:
        if self._image_viewer is None:
            from ui.image_viewer import ImageViewerWidget
            self._image_viewer = ImageViewerWidget()
            self.addWidget(self._image_viewer)
        return self._image_viewer

    @property
    def cad_viewer(self) -> Cad2DViewerWidget:
        if self._cad_viewer is None:
            from ui.cad_viewer import Cad2DViewerWidget
            self._cad_viewer = Cad2DViewerWidget()
            self.addWidget(self._cad_viewer)
        return self._cad_viewer

    @property
    def model3d_viewer(self) -> Model3DViewerWidget:
        if self._model3d_viewer is None:
            from ui.model3d_viewer import Model3DViewerWidget
            self._model3d_viewer = Model3DViewerWidget()
            self.addWidget(self._model3d_viewer)
        return self._model3d_viewer

    @property
    def has_image_viewer(self) -> bool:
        return self._image_viewer is not None

    def show_browser(self) -> None:
        self.setCurrentIndex(0)

    def switch_to(self, mode: ViewerMode) -> None:
        if mode == ViewerMode.IMAGE:
            self.setCurrentWidget(self.image_viewer)
        elif mode == ViewerMode.CAD_2D:
            self.setCurrentWidget(self.cad_viewer)
        elif mode == ViewerMode.MODEL_3D:
            self.setCurrentWidget(self.model3d_viewer)
        else:
            self.show_browser()
