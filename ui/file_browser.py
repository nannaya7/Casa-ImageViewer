from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeView, QLabel, QStyle, QProxyStyle, QFileIconProvider,
)
from PyQt6.QtCore import QDir, Qt, QLineF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QStandardItemModel, QStandardItem

from ui.folder_icons import make_folder_icon

_SENTINEL = "__loading__"
COMPUTER_LOCATION = "__computer__"

_SPECIAL_FOLDERS = [
    ("바탕 화면", "Desktop"),
    ("문서",     "Documents"),
    ("다운로드", "Downloads"),
    ("음악",     "Music"),
    ("사진",     "Pictures"),
    ("동영상",   "Videos"),
]


class _ArrowBranchStyle(QProxyStyle):
    """Draws '>' / 'v' chevrons for branch indicators; draws nothing for leaf nodes."""

    _COLOR = QColor("#9A7860")

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PrimitiveElement.PE_IndicatorBranch:
            super().drawPrimitive(element, option, painter, widget)
            return

        if not (option.state & QStyle.StateFlag.State_Children):
            return

        cx = float(option.rect.center().x())
        cy = float(option.rect.center().y())
        hw, hh = 1.76, 2.82

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._COLOR, 1.5,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if option.state & QStyle.StateFlag.State_Open:
            painter.drawLine(QLineF(cx - hh, cy - hw, cx, cy + hw))
            painter.drawLine(QLineF(cx, cy + hw, cx + hh, cy - hw))
        else:
            painter.drawLine(QLineF(cx - hw, cy - hh, cx + hw, cy))
            painter.drawLine(QLineF(cx + hw, cy, cx - hw, cy + hh))

        painter.restore()


class FileBrowserPanel(QWidget):
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path_index: dict[str, QStandardItem] = {}
        self._initial_path = COMPUTER_LOCATION
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  폴더")
        header.setObjectName("folderHeader")
        header.setFixedHeight(28)
        layout.addWidget(header)

        self._model = QStandardItemModel()

        self._tree = QTreeView()
        self._tree.setStyle(_ArrowBranchStyle(self._tree.style()))
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.clicked.connect(self._on_folder_clicked)
        self._tree.expanded.connect(self._on_item_expanded)
        layout.addWidget(self._tree)

        self._build_root()
        self._tree.expand(self._model.index(0, 0))  # expand 내 컴퓨터

    def _build_root(self) -> None:
        provider = QFileIconProvider()

        pc_item = QStandardItem("내 컴퓨터")
        pc_item.setEditable(False)
        pc_item.setData(COMPUTER_LOCATION, Qt.ItemDataRole.UserRole)
        pc_item.setIcon(provider.icon(QFileIconProvider.IconType.Computer))
        pc_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._path_index[COMPUTER_LOCATION] = pc_item

        home = Path.home()
        for display, sub in _SPECIAL_FOLDERS:
            path = home / sub
            if path.is_dir():
                pc_item.appendRow(self._make_item(display, path))

        for fi in QDir.drives():
            path = Path(fi.absolutePath())
            pc_item.appendRow(self._make_item(_drive_display_name(path), path))

        self._model.appendRow(pc_item)

    # ------------------------------------------------------------------
    # Item factory & lazy loading
    # ------------------------------------------------------------------

    def _make_item(self, display: str, path: Path) -> QStandardItem:
        item = QStandardItem(display)
        item.setEditable(False)
        path_str = str(path)
        item.setData(path_str, Qt.ItemDataRole.UserRole)
        item.setIcon(make_folder_icon(path))
        self._path_index[path_str] = item
        # Placeholder child so the expand arrow appears
        ph = QStandardItem("")
        ph.setData(_SENTINEL, Qt.ItemDataRole.UserRole)
        item.appendRow(ph)
        return item

    def _populate_children(self, item: QStandardItem, path: Path) -> None:
        try:
            subdirs = sorted(
                (p for p in path.iterdir()
                 if p.is_dir() and not p.name.startswith('$')),
                key=lambda p: p.name.lower(),
            )
        except (PermissionError, OSError):
            subdirs = []
        for sub in subdirs:
            item.appendRow(self._make_item(sub.name, sub))

    def _ensure_populated(self, item: QStandardItem) -> None:
        """Replace placeholder with real children if not yet loaded."""
        if item.rowCount() == 1:
            child = item.child(0)
            if child and child.data(Qt.ItemDataRole.UserRole) == _SENTINEL:
                item.removeRow(0)
                path_str = item.data(Qt.ItemDataRole.UserRole)
                if path_str:
                    self._populate_children(item, Path(path_str))
        self._tree.expand(self._model.indexFromItem(item))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def navigate_to(self, folder: str) -> None:
        target = Path(folder)
        target_str = str(target)

        if target_str in self._path_index:
            self._select_item(self._path_index[target_str])
            return

        # Walk up until we find a known ancestor
        chain: list[Path] = []
        p = target
        while str(p) not in self._path_index:
            chain.append(p)
            parent = p.parent
            if parent == p:
                return  # unreachable from current tree
            p = parent

        # Expand ancestor chain downward, triggering lazy loading
        chain.reverse()
        ancestor = self._path_index[str(p)]
        for next_path in chain:
            self._ensure_populated(ancestor)
            next_str = str(next_path)
            if next_str not in self._path_index:
                return
            ancestor = self._path_index[next_str]

        self._select_item(ancestor)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_expanded(self, index) -> None:
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        if item.rowCount() == 1:
            child = item.child(0)
            if child and child.data(Qt.ItemDataRole.UserRole) == _SENTINEL:
                item.removeRow(0)
                self._populate_children(item, Path(path_str))

    def _on_folder_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.folder_selected.emit(path)

    def _select_item(self, item: QStandardItem) -> None:
        idx = self._model.indexFromItem(item)
        self._tree.setCurrentIndex(idx)
        self._tree.scrollTo(idx)


def _drive_display_name(path: Path) -> str:
    drive = path.drive.rstrip(":\\/")
    if drive:
        return f"{drive} 드라이브"
    return str(path)
