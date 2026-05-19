from enum import Enum, auto
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QAbstractItemView, QListView, QFileIconProvider,
)
from PyQt6.QtCore import Qt, QSize, QFileInfo, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QImageReader, QImage, QPixmap, QIcon, QPainter

from services.file_type_detector import is_supported
from ui.folder_icons import make_folder_icon

_OVERLAY_GRAB = 0.45  # bottom-left fraction to capture the shortcut arrow

_THUMB_EXTS = frozenset({
    '.png', '.jpg', '.jpeg', '.bmp', '.gif',
    '.tif', '.tiff', '.webp',
    '.ppm', '.pgm', '.pbm', '.pnm',
})


class _ThumbnailWorker(QObject):
    ready = pyqtSignal(int, QImage)
    finished = pyqtSignal()

    def __init__(self, entries: list, max_size: int):
        super().__init__()
        self._entries = entries
        self._max_size = max_size
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for idx, path in enumerate(self._entries):
            if self._cancelled:
                break
            if not (path.is_file() and path.suffix.lower() in _THUMB_EXTS):
                continue
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            orig = reader.size()
            if orig.isValid() and orig.width() > 0 and orig.height() > 0:
                scaled = orig.scaled(
                    QSize(self._max_size, self._max_size),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                reader.setScaledSize(scaled)
            img = reader.read()
            if not img.isNull():
                self.ready.emit(idx, img)
        self.finished.emit()


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
    folder_navigated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_folder: str = ""
        self._filter_query: str = ""
        self._icon_provider = QFileIconProvider()
        self._thumb_thread: QThread | None = None
        self._thumb_worker: _ThumbnailWorker | None = None
        self._thumb_gen: int = 0
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
            icon_size=QSize(128, 128),
            grid_size=QSize(200, 180),
        )
        self._small_list = self._make_list(
            QListView.ViewMode.IconMode,
            icon_size=QSize(64, 64),
            grid_size=QSize(100, 90),
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
        self._filter_query = ""
        self._reload()

    def set_filter(self, query: str) -> None:
        self._filter_query = query.strip().lower()
        self._reload()

    def _reload(self) -> None:
        entries = self._get_entries()
        self._populate_icon_list(self._large_list, entries)
        self._populate_icon_list(self._small_list, entries)
        self._populate_icon_list(self._list_view, entries)
        self._populate_details(entries)
        self._start_thumbnail_loading(entries)

    def file_count(self) -> int:
        return self._large_list.count()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cancel_thumbnails(self) -> None:
        self._thumb_gen += 1
        if self._thumb_worker is not None:
            self._thumb_worker.cancel()
        if self._thumb_thread is not None:
            self._thumb_thread.quit()
            self._thumb_thread.wait(300)
        self._thumb_thread = None
        self._thumb_worker = None

    def _start_thumbnail_loading(self, entries: list[Path]) -> None:
        self._cancel_thumbnails()
        gen = self._thumb_gen
        worker = _ThumbnailWorker(entries, 128)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(lambda idx, img, g=gen: self._on_thumbnail_ready(idx, img, g))
        worker.finished.connect(thread.quit)
        self._thumb_worker = worker
        self._thumb_thread = thread
        thread.start()

    def _on_thumbnail_ready(self, idx: int, img: QImage, gen: int) -> None:
        if gen != self._thumb_gen:
            return
        item = self._large_list.item(idx)
        if item is not None:
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    def _get_entries(self) -> list[Path]:
        if not self._current_folder:
            return []
        try:
            folder = Path(self._current_folder)
            parent = folder.parent
            up = [parent] if parent != folder else []
            q = self._filter_query
            dirs = sorted(
                (e for e in folder.iterdir()
                 if e.is_dir() and (not q or q in e.name.lower())),
                key=lambda p: p.name.lower(),
            )
            files = sorted(
                (e for e in folder.iterdir()
                 if e.is_file() and is_supported(e.name) and (not q or q in e.name.lower())),
                key=lambda p: p.name.lower(),
            )
            return up + dirs + files
        except PermissionError:
            return []

    def _get_icon(self, path: Path) -> QIcon:
        if path.is_dir():
            return make_folder_icon(path)
        icon = self._icon_provider.icon(QFileInfo(str(path)))
        if path.is_symlink() or path.suffix.lower() == '.lnk':
            icon = self._resize_shortcut_overlay(path, icon)
        return icon

    def _resize_shortcut_overlay(self, path: Path, full_icon: QIcon) -> QIcon:
        try:
            if path.is_symlink():
                base_icon = self._icon_provider.icon(QFileInfo(str(path.resolve(strict=False))))
            elif path.is_dir():
                base_icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
            else:
                base_icon = self._icon_provider.icon(QFileIconProvider.IconType.File)
        except OSError:
            return full_icon

        sizes = full_icon.availableSizes() or [QSize(32, 32)]
        result = QIcon()
        for sz in sizes:
            full_pm = full_icon.pixmap(sz)
            base_pm = base_icon.pixmap(sz)
            if full_pm.isNull() or base_pm.isNull():
                result.addPixmap(full_pm)
                continue

            h = sz.height()
            grab = int(min(sz.width(), h) * _OVERLAY_GRAB)
            src = full_pm.copy(0, h - grab, grab, grab)
            small = int(grab * 0.65)
            arrow = src.scaled(
                small, small,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            composite = base_pm.copy()
            p = QPainter(composite)
            p.drawPixmap(0, h - small, arrow)
            p.end()
            result.addPixmap(composite)

        return result if not result.isNull() else full_icon

    def _populate_icon_list(self, widget: QListWidget, entries: list[Path]) -> None:
        widget.clear()
        parent = Path(self._current_folder).parent if self._current_folder else None
        for entry in entries:
            label = ".." if (parent and entry == parent) else entry.name
            item = QListWidgetItem(self._get_icon(entry), label)
            item.setData(Qt.ItemDataRole.UserRole, str(entry))
            widget.addItem(item)

    def _populate_details(self, entries: list[Path]) -> None:
        self._detail_tree.clear()
        parent = Path(self._current_folder).parent if self._current_folder else None
        for entry in entries:
            try:
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                modified = ""
            display_name = ".." if (parent and entry == parent) else entry.name
            if entry.is_dir():
                row = QTreeWidgetItem([display_name, "", "폴더", modified])
            else:
                row = QTreeWidgetItem([
                    display_name,
                    _format_size(stat.st_size),
                    entry.suffix.lower(),
                    modified,
                ])
                row.setTextAlignment(
                    1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            row.setIcon(0, self._get_icon(entry))
            row.setData(0, Qt.ItemDataRole.UserRole, str(entry))
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
            self._open_path(path)

    def _on_detail_double_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        if Path(path).is_dir():
            self.load_folder(path)
            self.folder_navigated.emit(path)
        else:
            self.file_opened.emit(path)
