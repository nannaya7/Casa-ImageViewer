from PyQt6.QtWidgets import QStackedWidget

from models.viewer_mode import ViewerMode
from ui.file_panel import FilePanelWidget
from ui.image_viewer import ImageViewerWidget
from ui.cad_viewer import Cad2DViewerWidget
from ui.model3d_viewer import Model3DViewerWidget

_MODE_INDEX: dict[ViewerMode, int] = {
    ViewerMode.IMAGE: 1,
    ViewerMode.CAD_2D: 2,
    ViewerMode.MODEL_3D: 3,
}


class ViewerStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_panel     = FilePanelWidget()
        self._image_viewer   = ImageViewerWidget()
        self._cad_viewer     = Cad2DViewerWidget()
        self._model3d_viewer = Model3DViewerWidget()

        self.addWidget(self._file_panel)       # 0
        self.addWidget(self._image_viewer)     # 1
        self.addWidget(self._cad_viewer)       # 2
        self.addWidget(self._model3d_viewer)   # 3

    @property
    def file_panel(self) -> FilePanelWidget:
        return self._file_panel

    @property
    def image_viewer(self) -> ImageViewerWidget:
        return self._image_viewer

    @property
    def cad_viewer(self) -> Cad2DViewerWidget:
        return self._cad_viewer

    @property
    def model3d_viewer(self) -> Model3DViewerWidget:
        return self._model3d_viewer

    def show_browser(self) -> None:
        self.setCurrentIndex(0)

    def switch_to(self, mode: ViewerMode) -> None:
        self.setCurrentIndex(_MODE_INDEX.get(mode, 0))
