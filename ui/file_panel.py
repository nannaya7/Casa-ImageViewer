from enum import Enum, auto
import sys
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QAbstractItemView, QListView, QFileIconProvider,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QSlider,
    QMenu, QMessageBox, QInputDialog, QApplication,
)
from PyQt6.QtCore import (
    Qt, QSize, QRect, QFileInfo, pyqtSignal, QObject, QThread,
    QUrl, QFile, QProcess, QDir,
)
from PyQt6.QtGui import (
    QImageReader, QImage, QPixmap, QIcon, QPainter, QDesktopServices,
)

from services.file_type_detector import is_supported
from ui.file_browser import COMPUTER_LOCATION
from ui.folder_icons import make_folder_icon

_OVERLAY_GRAB = 0.45  # bottom-left fraction to capture the shortcut arrow

_LARGE_DEFAULT = 128
_LARGE_MIN = 64
_LARGE_MAX = int(_LARGE_DEFAULT * 1.2)  # 153

_THUMB_EXTS = frozenset({
    '.png', '.jpg', '.jpeg', '.bmp', '.gif',
    '.tif', '.tiff', '.webp',
    '.ppm', '.pgm', '.pbm', '.pnm',
    '.jfif', '.jpe',
    '.jp2', '.j2k', '.jpc', '.jpf', '.jpx',
    '.apng', '.cur', '.icns', '.pcx', '.qoi', '.xbm', '.xpm',
    '.icb', '.vda', '.vst',
    '.sgi', '.rgb', '.rgba', '.bw',
    '.ras', '.mpo',
})

_SPECIAL_FOLDERS = [
    ("바탕 화면", "Desktop"),
    ("문서",     "Documents"),
    ("다운로드", "Downloads"),
    ("음악",     "Music"),
    ("사진",     "Pictures"),
    ("동영상",   "Videos"),
]


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
    ViewStyle.LIST:    2,
    ViewStyle.DETAILS: 3,
}


class _CompactSelectDelegate(QStyledItemDelegate):
    """선택 하이라이트를 아이콘+텍스트 너비에만 맞게 그린다."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        if not (opt.state & QStyle.StateFlag.State_Selected):
            super().paint(painter, opt, index)
            return

        icon_w = opt.decorationSize.width() if opt.decorationSize.isValid() else 0
        gap = 4 if icon_w else 0
        text_w = opt.fontMetrics.horizontalAdvance(opt.text)
        content_w = min(icon_w + gap + text_w + 10, opt.rect.width() - 4)

        sel_rect = QRect(
            opt.rect.left() + 2,
            opt.rect.top() + 2,
            content_w,
            opt.rect.height() - 4,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(opt.palette.highlight())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(sel_rect, 4, 4)
        painter.restore()

        if icon_w:
            icon_x = opt.rect.left() + 4
            icon_y = opt.rect.top() + (opt.rect.height() - icon_w) // 2
            opt.icon.paint(painter, QRect(icon_x, icon_y, icon_w, icon_w))

        text_x = opt.rect.left() + icon_w + gap + 4
        text_rect = QRect(text_x, opt.rect.top(), opt.rect.right() - text_x, opt.rect.height())
        painter.save()
        painter.setPen(opt.palette.highlightedText().color())
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            opt.text,
        )
        painter.restore()


def _format_size(n: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


def _computer_entries() -> list[Path]:
    home = Path.home()
    entries: list[Path] = []
    for _, sub in _SPECIAL_FOLDERS:
        path = home / sub
        if path.is_dir():
            entries.append(path)
    entries.extend(Path(fi.absolutePath()) for fi in QDir.drives())
    return entries


def _entry_display_name(path: Path) -> str:
    drive = path.drive.rstrip(":\\/")
    if drive and not path.name:
        return f"{drive} 드라이브"
    return path.name or str(path)


def _is_drive_root(path: Path) -> bool:
    return bool(path.drive) and path.parent == path


class FilePanelWidget(QWidget):
    file_opened = pyqtSignal(str)
    folder_navigated = pyqtSignal(str)
    thumbnail_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_folder: str = ""
        self._filter_query: str = ""
        self._icon_provider = QFileIconProvider()
        self._thumb_thread: QThread | None = None
        self._thumb_worker: _ThumbnailWorker | None = None
        self._thumb_gen: int = 0
        self._retired_thumbnails: list[tuple[QThread, _ThumbnailWorker | None]] = []
        self._last_entries: list[Path] = []
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
            icon_size=QSize(_LARGE_DEFAULT, _LARGE_DEFAULT),
            grid_size=QSize(200, 180),
        )

        # Container: large_list + bottom slider bar
        large_container = QWidget()
        lc_layout = QVBoxLayout(large_container)
        lc_layout.setContentsMargins(0, 0, 0, 0)
        lc_layout.setSpacing(0)
        lc_layout.addWidget(self._large_list)

        slider_bar = QWidget()
        slider_bar.setObjectName("sliderBar")
        slider_bar.setFixedHeight(28)
        sb_layout = QHBoxLayout(slider_bar)
        sb_layout.setContentsMargins(0, 4, 10, 4)
        sb_layout.addStretch()
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(_LARGE_MIN, _LARGE_MAX)
        self._size_slider.setValue(_LARGE_DEFAULT)
        self._size_slider.setFixedWidth(120)
        self._size_slider.valueChanged.connect(self._on_size_slider_changed)
        self._size_slider.sliderReleased.connect(self._on_size_slider_released)
        sb_layout.addWidget(self._size_slider)
        lc_layout.addWidget(slider_bar)

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
        self._list_view.setItemDelegate(_CompactSelectDelegate(self._list_view))

        self._detail_tree = QTreeWidget()
        self._detail_tree.setColumnCount(4)
        self._detail_tree.setHeaderLabels(["이름", "크기", "종류", "수정 날짜"])
        self._detail_tree.setRootIsDecorated(False)
        self._detail_tree.setAlternatingRowColors(True)
        self._detail_tree.setSortingEnabled(True)
        self._detail_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._detail_tree.itemDoubleClicked.connect(self._on_detail_double_clicked)
        self._detail_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._detail_tree.customContextMenuRequested.connect(self._show_detail_context_menu)

        self._stack.addWidget(large_container)    # 0
        self._stack.addWidget(self._small_list)   # 1
        self._stack.addWidget(self._list_view)    # 2
        self._stack.addWidget(self._detail_tree)  # 3

        layout.addWidget(self._stack)

    def _make_list(
        self,
        view_mode: QListView.ViewMode,
        icon_size: QSize,
        grid_size: QSize | None = None,
        top_to_bottom: bool = False,
    ) -> QListWidget:
        w = QListWidget()
        w.setViewMode(view_mode)
        w.setIconSize(icon_size)
        if grid_size is not None:
            w.setGridSize(grid_size)
        w.setResizeMode(QListView.ResizeMode.Adjust)
        w.setMovement(QListView.Movement.Static)
        w.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        if top_to_bottom:
            w.setFlow(QListView.Flow.TopToBottom)
            w.setWrapping(True)
        w.itemDoubleClicked.connect(self._on_item_double_clicked)
        w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        w.customContextMenuRequested.connect(
            lambda pos, widget=w: self._show_list_context_menu(widget, pos)
        )
        return w

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_view_style(self, style: ViewStyle) -> None:
        self._stack.setCurrentIndex(_STYLE_INDEX[style])
        self._populate_current_view(self._last_entries)

    def thumbnail_size(self) -> int:
        return self._size_slider.value()

    def set_thumbnail_size(self, size: int) -> None:
        size = max(_LARGE_MIN, min(_LARGE_MAX, int(size)))
        self._size_slider.setValue(size)

    def load_folder(self, folder_path: str) -> None:
        self._current_folder = folder_path
        self._filter_query = ""
        self._reload()

    def set_filter(self, query: str) -> None:
        self._filter_query = query.strip().lower()
        self._reload()

    def _reload(self) -> None:
        entries = self._get_entries()
        self._last_entries = entries
        self._populate_current_view(entries)

    def file_count(self) -> int:
        return len(self._last_entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _populate_current_view(self, entries: list[Path]) -> None:
        current = self._stack.currentIndex()
        if current == _STYLE_INDEX[ViewStyle.LARGE_ICONS]:
            self._populate_icon_list(self._large_list, entries)
            self._start_thumbnail_loading(entries, self._size_slider.value())
        elif current == _STYLE_INDEX[ViewStyle.SMALL_ICONS]:
            self._cancel_thumbnails()
            self._populate_icon_list(self._small_list, entries)
        elif current == _STYLE_INDEX[ViewStyle.LIST]:
            self._cancel_thumbnails()
            self._populate_icon_list(self._list_view, entries)
        elif current == _STYLE_INDEX[ViewStyle.DETAILS]:
            self._cancel_thumbnails()
            self._populate_details(entries)

    def _cancel_thumbnails(self) -> None:
        self._thumb_gen += 1
        thread = self._thumb_thread
        worker = self._thumb_worker
        self._thumb_thread = None
        self._thumb_worker = None
        if worker is not None:
            worker.cancel()
        if thread is not None:
            thread.quit()
            if thread.isRunning():
                self._retired_thumbnails.append((thread, worker))

    def _start_thumbnail_loading(self, entries: list[Path], max_size: int = _LARGE_DEFAULT) -> None:
        self._cancel_thumbnails()
        if not any(p.is_file() and p.suffix.lower() in _THUMB_EXTS for p in entries):
            return
        gen = self._thumb_gen
        worker = _ThumbnailWorker(entries, max_size)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(lambda idx, img, g=gen: self._on_thumbnail_ready(idx, img, g))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda t=thread, w=worker: self._on_thumbnail_thread_finished(t, w)
        )
        self._thumb_worker = worker
        self._thumb_thread = thread
        thread.start()

    def _on_thumbnail_thread_finished(self, thread: QThread, worker: _ThumbnailWorker) -> None:
        if self._thumb_thread is thread:
            self._thumb_thread = None
            self._thumb_worker = None
        self._retired_thumbnails = [
            item for item in self._retired_thumbnails if item != (thread, worker)
        ]
        thread.deleteLater()

    def _on_thumbnail_ready(self, idx: int, img: QImage, gen: int) -> None:
        if gen != self._thumb_gen:
            return
        item = self._large_list.item(idx)
        if item is not None:
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    def _get_entries(self) -> list[Path]:
        if not self._current_folder:
            return []
        if self._current_folder == COMPUTER_LOCATION:
            return _computer_entries()
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
        except (PermissionError, OSError):
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
        parent = (
            Path(self._current_folder).parent
            if self._current_folder and self._current_folder != COMPUTER_LOCATION
            else None
        )
        for entry in entries:
            label = ".." if (parent and entry == parent) else _entry_display_name(entry)
            item = QListWidgetItem(self._get_icon(entry), label)
            item.setData(Qt.ItemDataRole.UserRole, str(entry))
            widget.addItem(item)

    def _populate_details(self, entries: list[Path]) -> None:
        self._detail_tree.clear()
        parent = (
            Path(self._current_folder).parent
            if self._current_folder and self._current_folder != COMPUTER_LOCATION
            else None
        )
        for entry in entries:
            try:
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                stat = None
                modified = ""
            display_name = ".." if (parent and entry == parent) else _entry_display_name(entry)
            if entry.is_dir():
                row = QTreeWidgetItem([display_name, "", "폴더", modified])
            else:
                row = QTreeWidgetItem([
                    display_name,
                    _format_size(stat.st_size) if stat else "",
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

    def _on_size_slider_changed(self, size: int) -> None:
        grid_w = int(size * 200 / _LARGE_DEFAULT)
        grid_h = int(size * 180 / _LARGE_DEFAULT)
        self._large_list.setIconSize(QSize(size, size))
        self._large_list.setGridSize(QSize(grid_w, grid_h))

    def _on_size_slider_released(self) -> None:
        self.thumbnail_size_changed.emit(self._size_slider.value())
        if self._stack.currentIndex() == _STYLE_INDEX[ViewStyle.LARGE_ICONS]:
            self._start_thumbnail_loading(self._last_entries, self._size_slider.value())

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

    def _show_list_context_menu(self, widget: QListWidget, pos) -> None:
        item = widget.itemAt(pos)
        path = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._show_context_menu(path, widget.viewport().mapToGlobal(pos))

    def _show_detail_context_menu(self, pos) -> None:
        item = self._detail_tree.itemAt(pos)
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self._show_context_menu(path, self._detail_tree.viewport().mapToGlobal(pos))

    def _show_context_menu(self, path: str | None, global_pos) -> None:
        menu = QMenu(self)

        if path:
            p = Path(path)
            is_up_entry = self._is_up_entry(p)
            is_drive_root = _is_drive_root(p)

            open_act = menu.addAction("열기")
            open_default_act = menu.addAction("기본 앱으로 열기")
            reveal_act = menu.addAction("파일 위치 열기")
            menu.addSeparator()
            rename_act = menu.addAction("이름 바꾸기")
            trash_act = menu.addAction("휴지통으로 이동")
            menu.addSeparator()
            copy_path_act = menu.addAction("경로 복사")
            menu.addSeparator()

            rename_act.setEnabled(not is_up_entry and not is_drive_root)
            trash_act.setEnabled(not is_up_entry and not is_drive_root)

            open_act.triggered.connect(lambda checked=False, target=path: self._open_path(target))
            open_default_act.triggered.connect(
                lambda checked=False, target=p: self._open_default_app(target)
            )
            reveal_act.triggered.connect(lambda checked=False, target=p: self._reveal_in_explorer(target))
            rename_act.triggered.connect(lambda checked=False, target=p: self._rename_path(target))
            trash_act.triggered.connect(lambda checked=False, target=p: self._move_to_trash(target))
            copy_path_act.triggered.connect(lambda checked=False, target=path: self._copy_path(target))

        refresh_act = menu.addAction("새로 고침")
        refresh_act.triggered.connect(self._reload)

        if self._current_folder and self._current_folder != COMPUTER_LOCATION:
            open_folder_act = menu.addAction("현재 폴더 열기")
            open_folder_act.triggered.connect(
                lambda checked=False: self._open_default_app(Path(self._current_folder))
            )

        menu.exec(global_pos)

    def _is_up_entry(self, path: Path) -> bool:
        if not self._current_folder:
            return False
        folder = Path(self._current_folder)
        return folder.parent != folder and path == folder.parent

    def _open_default_app(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _reveal_in_explorer(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "파일 없음", "선택한 항목을 찾을 수 없습니다.")
            self._reload()
            return

        if sys.platform == "win32" and path.is_file():
            QProcess.startDetached("explorer.exe", ["/select,", str(path)])
        elif sys.platform == "darwin":
            args = ["-R", str(path)] if path.is_file() else [str(path)]
            QProcess.startDetached("open", args)
        else:
            target = path.parent if path.is_file() else path
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _rename_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "파일 없음", "선택한 항목을 찾을 수 없습니다.")
            self._reload()
            return

        new_name, ok = QInputDialog.getText(
            self,
            "이름 바꾸기",
            "새 이름:",
            text=path.name,
        )
        new_name = new_name.strip()
        if not ok or not new_name or new_name == path.name:
            return

        if any(sep in new_name for sep in ("\\", "/")):
            QMessageBox.warning(self, "이름 오류", "이름에는 경로 구분자를 사용할 수 없습니다.")
            return

        target = path.with_name(new_name)
        if target.exists():
            QMessageBox.warning(self, "이름 오류", "같은 이름의 항목이 이미 있습니다.")
            return

        try:
            path.rename(target)
        except OSError as exc:
            QMessageBox.warning(self, "이름 바꾸기 실패", str(exc))
            return

        self._reload()

    def _move_to_trash(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "파일 없음", "선택한 항목을 찾을 수 없습니다.")
            self._reload()
            return

        ret = QMessageBox.question(
            self,
            "휴지통으로 이동",
            f"'{path.name}' 항목을 휴지통으로 이동할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        ok = QFile.moveToTrash(str(path))
        if not ok:
            QMessageBox.warning(self, "삭제 실패", "이 항목을 휴지통으로 이동할 수 없습니다.")
            return

        self._reload()

    def _copy_path(self, path: str) -> None:
        QApplication.clipboard().setText(path)

    def closeEvent(self, event) -> None:
        self._cancel_thumbnails()
        for thread, _worker in list(self._retired_thumbnails):
            if thread.isRunning():
                thread.wait()
        super().closeEvent(event)
