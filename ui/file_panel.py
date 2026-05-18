from enum import Enum, auto
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QAbstractItemView, QListView,
)
from PyQt6.QtCore import Qt, QSize, QFileInfo, pyqtSignal
from PyQt6.QtWidgets import QFileIconProvider

from services.file_type_detector import is_supported


class ViewStyle(Enum):
    LARGE_ICONS = auto()
    SMALL_ICONS = auto()
    LIST = auto()
    DETAILS = auto()


_STYLE_INDEX: dict[ViewStyle, int] = {
    ViewStyle.LARGE_ICONS: 0,
    ViewStyle.SMALL_ICONS: 1,
    ViewStyle.LIST: 2,
    ViewStyle.DETAILS: 3,
}


def _format_size(n: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


class FilePanelWidget(QWidget):
    file_opened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_folder: str = ""
        self._icon_provider = QFileIconProvider()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()

        self._large_list = self._make_list(
            QListView.ViewMode.IconMode,
            icon_size=QSize(64, 64),
            grid_size=QSize(100, 90),
        )
        self._small_list = self._make_list(
            QListView.ViewMode.IconMode,
            icon_size=QSize(24, 24),
            grid_size=QSize(160, 32),
        )
        self._list_view = self._make_list(
            QListView.ViewMode.ListMode,
            icon_size=QSize(20, 20),
            grid_size=QSize(200, 24),
            top_to_bottom=True,
        )

        self._detail_tree = QTreeWidget()
        self._detail_tree.setColumnCount(4)
        self._detail_tree.setHeaderLabels(["이름", "크기", "종류", "수정 날짜"])
        self._detail_tree.setRootIsDecorated(False)
        self._detail_tree.setAlternatingRowColors(True)
        self._detail_tree.setSortingEnabled(True)
        self._detail_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._detail_tree.itemDoubleClicked.connect(self._on_detail_double_clicked)

        self._stack.addWidget(self._large_list)   # 0
        self._stack.addWidget(self._small_list)   # 1
        self._stack.addWidget(self._list_view)    # 2
        self._stack.addWidget(self._detail_tree)  # 3

        layout.addWidget(self._stack)

    def _make_list(
        self,
        view_mode: QListView.ViewMode,
        icon_size: QSize,
        grid_size: QSize,
        top_to_bottom: bool = False,
    ) -> QListWidget:
        w = QListWidget()
        w.setViewMode(view_mode)
        w.setIconSize(icon_size)
        w.setGridSize(grid_size)
        w.setResizeMode(QListView.ResizeMode.Adjust)
        w.setMovement(QListView.Movement.Static)
        w.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        if top_to_bottom:
            w.setFlow(QListView.Flow.TopToBottom)
            w.setWrapping(True)
        w.itemDoubleClicked.connect(self._on_item_double_clicked)
        return w

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_view_style(self, style: ViewStyle) -> None:
        self._stack.setCurrentIndex(_STYLE_INDEX[style])

    def load_folder(self, folder_path: str) -> None:
        self._current_folder = folder_path
        entries = self._get_entries()
        self._populate_icon_list(self._large_list, entries)
        self._populate_icon_list(self._small_list, entries)
        self._populate_icon_list(self._list_view, entries)
        self._populate_details(entries)

    def file_count(self) -> int:
        return self._large_list.count()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_entries(self) -> list[Path]:
        if not self._current_folder:
            return []
        try:
            return sorted(
                (e for e in Path(self._current_folder).iterdir()
                 if e.is_file() and is_supported(e.name)),
                key=lambda p: p.name.lower(),
            )
        except PermissionError:
            return []

    def _get_icon(self, path: Path):
        return self._icon_provider.icon(QFileInfo(str(path)))

    def _populate_icon_list(self, widget: QListWidget, entries: list[Path]) -> None:
        widget.clear()
        for entry in entries:
            item = QListWidgetItem(self._get_icon(entry), entry.name)
            item.setData(Qt.ItemDataRole.UserRole, str(entry))
            widget.addItem(item)

    def _populate_details(self, entries: list[Path]) -> None:
        self._detail_tree.clear()
        for entry in entries:
            stat = entry.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            row = QTreeWidgetItem([
                entry.name,
                _format_size(stat.st_size),
                entry.suffix.lower(),
                modified,
            ])
            row.setIcon(0, self._get_icon(entry))
            row.setData(0, Qt.ItemDataRole.UserRole, str(entry))
            row.setTextAlignment(
                1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._detail_tree.addTopLevelItem(row)

        self._detail_tree.setColumnWidth(0, 240)
        self._detail_tree.setColumnWidth(1, 80)
        self._detail_tree.setColumnWidth(2, 70)
        self._detail_tree.setColumnWidth(3, 140)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_opened.emit(path)

    def _on_detail_double_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.file_opened.emit(path)
