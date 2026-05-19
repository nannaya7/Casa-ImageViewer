from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QLabel, QStyle, QProxyStyle
from PyQt6.QtCore import QDir, QTimer, Qt, QLineF, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QPainter, QPen, QColor

from ui.folder_icons import make_folder_icon


class _ArrowBranchStyle(QProxyStyle):
    """Draws '>' / 'v' chevrons for branch indicators; draws nothing for leaf nodes (removes branch lines)."""

    _COLOR = QColor("#9A7860")

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PrimitiveElement.PE_IndicatorBranch:
            super().drawPrimitive(element, option, painter, widget)
            return

        if not (option.state & QStyle.StateFlag.State_Children):
            return  # leaf node — draw nothing, eliminating all branch lines

        cx = float(option.rect.center().x())
        cy = float(option.rect.center().y())
        hw, hh = 1.76, 2.82  # half-width, half-height of chevron

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._COLOR, 1.5,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if option.state & QStyle.StateFlag.State_Open:
            # "v" down chevron
            painter.drawLine(QLineF(cx - hh, cy - hw, cx, cy + hw))
            painter.drawLine(QLineF(cx, cy + hw, cx + hh, cy - hw))
        else:
            # ">" right chevron
            painter.drawLine(QLineF(cx - hw, cy - hh, cx + hw, cy))
            painter.drawLine(QLineF(cx + hw, cy, cx - hw, cy + hh))

        painter.restore()


class _FolderIconModel(QFileSystemModel):
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DecorationRole and index.isValid():
            path = Path(self.filePath(index))
            if path.is_dir():
                return make_folder_icon(path)
        return super().data(index, role)


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
        header.setObjectName("folderHeader")
        header.setFixedHeight(28)
        layout.addWidget(header)

        self._fs_model = _FolderIconModel()
        self._fs_model.setRootPath("")
        self._fs_model.setFilter(
            QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives
        )

        self._tree = QTreeView()
        self._tree.setStyle(_ArrowBranchStyle(self._tree.style()))
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

    def navigate_to(self, folder: str) -> None:
        index = self._fs_model.index(folder)
        if index.isValid():
            self._tree.setCurrentIndex(index)
            self._tree.scrollTo(index)
            self._tree.expand(index)

    def _on_folder_clicked(self, index) -> None:
        path = self._fs_model.filePath(index)
        self.folder_selected.emit(path)
