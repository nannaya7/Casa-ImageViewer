from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QLabel
from PyQt6.QtCore import QDir, QTimer, pyqtSignal
from PyQt6.QtGui import QFileSystemModel


class FileBrowserPanel(QWidget):
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initial_path = str(Path.home())
        self._setup_ui()
        QTimer.singleShot(0, lambda: self.folder_selected.emit(self._initial_path))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  폴더")
        header.setFixedHeight(28)
        header.setStyleSheet(
            "background-color: #2d2d2d; color: #cccccc; font-size: 12px;"
        )
        layout.addWidget(header)

        self._fs_model = QFileSystemModel()
        self._fs_model.setRootPath("")
        self._fs_model.setFilter(
            QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives
        )

        self._tree = QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setRootIndex(self._fs_model.index(""))
        self._tree.hideColumn(1)
        self._tree.hideColumn(2)
        self._tree.hideColumn(3)
        self._tree.setHeaderHidden(True)
        self._tree.clicked.connect(self._on_folder_clicked)

        layout.addWidget(self._tree)

        index = self._fs_model.index(self._initial_path)
        self._tree.setCurrentIndex(index)
        self._tree.scrollTo(index)
        self._tree.expand(index)

    def _on_folder_clicked(self, index) -> None:
        path = self._fs_model.filePath(index)
        self.folder_selected.emit(path)
