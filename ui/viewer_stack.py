from PyQt6.QtWidgets import QStackedWidget, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

from models.viewer_mode import ViewerMode
from ui.file_panel import FilePanelWidget
from ui.image_viewer import ImageViewerWidget

_MODE_INDEX: dict[ViewerMode, int] = {
    ViewerMode.IMAGE: 1,
    ViewerMode.CAD_2D: 2,
    ViewerMode.MODEL_3D: 3,
}


class _Placeholder(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #888888;")
        layout = QVBoxLayout(self)
        layout.addWidget(label)


class ViewerStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_panel = FilePanelWidget()
        self._image_viewer = ImageViewerWidget()

        self.addWidget(self._file_panel)                                        # 0
        self.addWidget(self._image_viewer)                                      # 1
        self.addWidget(_Placeholder("2D CAD Viewer\n(4단계 구현 예정)"))       # 2
        self.addWidget(_Placeholder("3D Model Viewer\n(5단계 구현 예정)"))     # 3

    @property
    def file_panel(self) -> FilePanelWidget:
        return self._file_panel

    @property
    def image_viewer(self) -> ImageViewerWidget:
        return self._image_viewer

    def show_browser(self) -> None:
        self.setCurrentIndex(0)

    def switch_to(self, mode: ViewerMode) -> None:
        self.setCurrentIndex(_MODE_INDEX.get(mode, 0))
