import math
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QVBoxLayout,
    QFileDialog, QApplication, QMenu, QMessageBox,
    QPushButton, QButtonGroup, QFrame, QLineEdit,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QSettings, QPointF
from PyQt6.QtGui import (
    QAction, QActionGroup, QIcon, QCloseEvent, QKeySequence, QShortcut,
    QPixmap, QPainter, QPen, QColor, QPolygonF,
)

from ui.file_browser import COMPUTER_LOCATION, FileBrowserPanel
from ui.viewer_stack import ViewerStack
from ui.file_panel import ViewStyle
from services.file_type_detector import detect_viewer_mode
from services.loader_thread import LoaderThread
from models.viewer_mode import ViewerMode


_MODE_LABEL: dict[ViewerMode, str] = {
    ViewerMode.IMAGE:    "이미지",
    ViewerMode.CAD_2D:  "2D CAD",
    ViewerMode.MODEL_3D: "3D 모델",
    ViewerMode.NONE:    "",
}

_OPEN_FILTER = (
    "지원 파일 (*.png *.jpg *.jpeg *.bmp *.gif *.ico *.tif *.tiff *.webp "
    "*.ppm *.pgm *.pbm *.pnm *.tga *.dds *.dib "
    "*.jfif *.jpe *.jp2 *.j2k *.jpc *.jpf *.jpx "
    "*.apng *.cur *.icns *.pcx *.qoi *.xbm *.xpm "
    "*.icb *.vda *.vst *.sgi *.rgb *.rgba *.bw *.ras *.mpo "
    "*.dxf *.dwg *.stl *.step *.stp);;"
    "이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.ico *.tif *.tiff *.webp "
    "*.ppm *.pgm *.pbm *.pnm *.tga *.dds *.dib "
    "*.jfif *.jpe *.jp2 *.j2k *.jpc *.jpf *.jpx "
    "*.apng *.cur *.icns *.pcx *.qoi *.xbm *.xpm "
    "*.icb *.vda *.vst *.sgi *.rgb *.rgba *.bw *.ras *.mpo);;"
    "2D CAD (*.dxf *.dwg);;"
    "3D 모델 (*.stl *.step *.stp);;"
    "모든 파일 (*.*)"
)

_VIEW_STYLES: list[tuple[ViewStyle, str]] = [
    (ViewStyle.LARGE_ICONS, "미리보기"),
    (ViewStyle.SMALL_ICONS, "아이콘"),
    (ViewStyle.LIST,        "간단히"),
    (ViewStyle.DETAILS,     "자세히"),
]

_STYLE_TO_IDX: dict[ViewStyle, int] = {
    ViewStyle.LARGE_ICONS: 0,
    ViewStyle.SMALL_ICONS: 1,
    ViewStyle.LIST:        2,
    ViewStyle.DETAILS:     3,
}
_IDX_TO_STYLE: dict[int, ViewStyle] = {v: k for k, v in _STYLE_TO_IDX.items()}

_WINDOW_ICON = Path(__file__).parent.parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"


class MainWindow(QMainWindow):
    _MAX_RECENT = 10

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image & CAD Integrated Viewer")
        if _WINDOW_ICON.exists():
            self.setWindowIcon(QIcon(str(_WINDOW_ICON)))
        self.resize(1280, 800)

        self._current_file: str | None = None
        self._current_mode: ViewerMode = ViewerMode.NONE
        self._pending_mode: ViewerMode = ViewerMode.NONE
        self._loader_thread: LoaderThread | None = None
        self._loader_threads: list[LoaderThread] = []
        self._load_gen: int = 0
        self._recent_files: list[str] = []
        self._image_viewer_signals_connected = False

        self._settings = QSettings()

        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._file_browser = FileBrowserPanel()
        self._file_browser.setMinimumWidth(160)
        self._file_browser.folder_selected.connect(self._on_folder_selected)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._header_bar = self._build_header_bar()
        right_layout.addWidget(self._header_bar)

        self._viewer_stack = ViewerStack()
        self._viewer_stack.file_panel.file_opened.connect(self._on_file_opened)
        self._viewer_stack.file_panel.folder_navigated.connect(self._on_folder_selected)
        self._viewer_stack.file_panel.thumbnail_size_changed.connect(
            lambda size: self._settings.setValue("thumbnailSize", size)
        )
        right_layout.addWidget(self._viewer_stack)

        self._splitter.addWidget(self._file_browser)
        self._splitter.addWidget(right)
        self._splitter.setSizes([240, 1040])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        root.addWidget(self._splitter)

    def _build_header_bar(self) -> QWidget:
        container = QWidget()
        container.setObjectName("headerBar")
        container.setFixedHeight(52)

        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Browse-mode bar ───────────────────────────────────────────
        self._browse_bar = QWidget()
        self._browse_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        bl = QHBoxLayout(self._browse_bar)
        bl.setContentsMargins(12, 9, 12, 9)
        bl.setSpacing(8)

        btn_open = QPushButton("  열기")
        btn_open.setObjectName("btnOpen")
        btn_open.setIcon(
            self.style().standardIcon(
                self.style().StandardPixmap.SP_DirOpenIcon
            )
        )
        btn_open.setIconSize(QSize(18, 18))
        btn_open.setFixedHeight(34)
        btn_open.clicked.connect(self._open_file_dialog)
        bl.addWidget(btn_open)

        bl.addStretch(1)

        seg_frame = QFrame()
        seg_frame.setObjectName("segGroup")
        seg_frame.setFixedHeight(34)
        sl = QHBoxLayout(seg_frame)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(0)

        self._style_btn_group = QButtonGroup(self)
        self._style_btn_group.setExclusive(True)
        self._style_buttons: dict[ViewStyle, QPushButton] = {}

        for style, label in _VIEW_STYLES:
            btn = QPushButton(label)
            btn.setObjectName("segBtn")
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, s=style: self._on_view_style(s))
            self._style_btn_group.addButton(btn)
            self._style_buttons[style] = btn
            sl.addWidget(btn)

        self._style_buttons[ViewStyle.SMALL_ICONS].setChecked(True)
        bl.addWidget(seg_frame)

        bl.addStretch(1)

        self._search_box = QLineEdit()
        self._search_box.setObjectName("searchBox")
        self._search_box.setPlaceholderText("검색")
        self._search_box.setFixedSize(200, 34)
        self._search_box.textChanged.connect(self._on_search)
        bl.addWidget(self._search_box)

        # ── Viewer-mode bar ───────────────────────────────────────────
        self._viewer_bar = QWidget()
        self._viewer_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        vl = QHBoxLayout(self._viewer_bar)
        vl.setContentsMargins(12, 9, 12, 9)
        vl.setSpacing(4)

        self._btn_back = QPushButton("← 뒤로")
        self._btn_back.setObjectName("btnBack")
        self._btn_back.setFixedHeight(34)
        self._btn_back.clicked.connect(self._go_back)
        vl.addWidget(self._btn_back)

        # Image-only group (sep + edit controls)
        self._image_grp = QWidget()
        ig = QHBoxLayout(self._image_grp)
        ig.setContentsMargins(0, 0, 0, 0)
        ig.setSpacing(4)
        ig.addWidget(_make_vsep())

        self._btn_undo = QPushButton("↩ 취소")
        self._btn_undo.setFixedHeight(34)
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(lambda: self._viewer_stack.image_viewer.undo())
        ig.addWidget(self._btn_undo)

        btn_resize = QPushButton("크기 조정")
        btn_resize.setFixedHeight(34)
        btn_resize.clicked.connect(lambda: self._viewer_stack.image_viewer.open_resize_dialog())
        ig.addWidget(btn_resize)

        vl.addWidget(self._image_grp)

        # Common zoom group (sep + zoom controls)
        self._zoom_grp = QWidget()
        zg = QHBoxLayout(self._zoom_grp)
        zg.setContentsMargins(0, 0, 0, 0)
        zg.setSpacing(4)
        zg.addWidget(_make_vsep())

        for label, slot in (("확대", self._zoom_in), ("축소", self._zoom_out), ("맞춤", self._fit)):
            b = QPushButton(label)
            b.setFixedHeight(34)
            b.clicked.connect(slot)
            zg.addWidget(b)

        vl.addWidget(self._zoom_grp)

        # Rotate/save group (sep + rotate + save)
        self._rot_grp = QWidget()
        rg = QHBoxLayout(self._rot_grp)
        rg.setContentsMargins(0, 0, 0, 0)
        rg.setSpacing(4)
        rg.addWidget(_make_vsep())

        btn_cw = QPushButton()
        btn_cw.setIcon(_make_rotate_icon(clockwise=True))
        btn_cw.setIconSize(QSize(22, 22))
        btn_cw.setToolTip("시계 방향 회전")
        btn_cw.setFixedSize(34, 34)
        btn_cw.clicked.connect(lambda: self._viewer_stack.image_viewer.rotate_cw())
        rg.addWidget(btn_cw)

        btn_ccw = QPushButton()
        btn_ccw.setIcon(_make_rotate_icon(clockwise=False))
        btn_ccw.setIconSize(QSize(22, 22))
        btn_ccw.setToolTip("반시계 방향 회전")
        btn_ccw.setFixedSize(34, 34)
        btn_ccw.clicked.connect(lambda: self._viewer_stack.image_viewer.rotate_ccw())
        rg.addWidget(btn_ccw)

        btn_save = QPushButton("저장")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(lambda: self._viewer_stack.image_viewer.save_as())
        rg.addWidget(btn_save)

        vl.addWidget(self._rot_grp)
        vl.addStretch(1)

        outer.addWidget(self._browse_bar)
        outer.addWidget(self._viewer_bar)

        self._viewer_bar.setVisible(False)
        return container

    def _setup_menubar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("파일(&F)")

        open_act = QAction("열기(&O)...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        self._recent_menu = QMenu("최근 파일(&R)", self)
        file_menu.addMenu(self._recent_menu)

        file_menu.addSeparator()

        quit_act = QAction("종료(&X)", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_act)

        view_menu = mb.addMenu("보기(&V)")
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        self._view_actions: dict[ViewStyle, QAction] = {}
        for style, label in _VIEW_STYLES:
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, s=style: self._on_view_style(s))
            view_group.addAction(act)
            view_menu.addAction(act)
            self._view_actions[style] = act

        tools_menu = mb.addMenu("도구(&T)")
        tools_menu.setEnabled(False)

        help_menu = mb.addMenu("도움말(&H)")
        help_menu.setEnabled(False)

    def _setup_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_info    = QLabel("  폴더를 선택하세요")
        self._status_loading = QLabel("")
        self._status_zoom    = QLabel("")
        self._status_mode    = QLabel("")
        bar.addWidget(self._status_info, 1)
        bar.addPermanentWidget(self._status_loading)
        bar.addPermanentWidget(self._status_zoom)
        bar.addPermanentWidget(self._status_mode)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Alt+Left"), self).activated.connect(self._go_back)
        QShortcut(QKeySequence("Ctrl+Z"),   self).activated.connect(
            lambda: self._viewer_stack.image_viewer.undo()
        )
        QShortcut(QKeySequence("Ctrl++"),   self).activated.connect(self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="),   self).activated.connect(self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"),   self).activated.connect(self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"),   self).activated.connect(self._fit)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(
            lambda: self._viewer_stack.image_viewer.save_as()
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        geom = self._settings.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._settings.value("windowState")
        if state is not None:
            self.restoreState(state)

        style_idx = _settings_int(
            self._settings,
            "viewStyle",
            _STYLE_TO_IDX[ViewStyle.SMALL_ICONS],
        )
        style = _IDX_TO_STYLE.get(style_idx, ViewStyle.SMALL_ICONS)
        self._viewer_stack.file_panel.set_view_style(style)
        self._style_buttons[style].setChecked(True)
        self._view_actions[style].setChecked(True)

        thumb_size = _settings_int(self._settings, "thumbnailSize", 128)
        self._viewer_stack.file_panel.set_thumbnail_size(thumb_size)

        recent = self._settings.value("recentFiles") or []
        if isinstance(recent, str):
            recent = [recent]
        self._recent_files = [p for p in recent if Path(p).exists()][:self._MAX_RECENT]
        self._update_recent_menu()

        self._file_browser.navigate_to(COMPUTER_LOCATION)
        self._on_folder_selected(COMPUTER_LOCATION)

    def _save_settings(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        folder = self._viewer_stack.file_panel._current_folder
        if folder and folder != COMPUTER_LOCATION:
            self._settings.setValue("lastFolder", folder)
        self._settings.setValue("recentFiles", self._recent_files)
        style = next(
            (s for s, b in self._style_buttons.items() if b.isChecked()),
            ViewStyle.LARGE_ICONS,
        )
        self._settings.setValue("viewStyle", _STYLE_TO_IDX[style])
        self._settings.setValue(
            "thumbnailSize",
            self._viewer_stack.file_panel.thumbnail_size(),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_loading(wait=True)
        self._save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------

    def _add_recent(self, file_path: str) -> None:
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self._MAX_RECENT]
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        if not self._recent_files:
            no_act = QAction("(없음)", self)
            no_act.setEnabled(False)
            self._recent_menu.addAction(no_act)
            return
        for path_str in self._recent_files:
            p = Path(path_str)
            act = QAction(p.name, self)
            act.setToolTip(path_str)
            act.triggered.connect(lambda checked, fp=path_str: self._on_file_opened(fp))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        clear_act = QAction("목록 지우기", self)
        clear_act.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(clear_act)

    def _clear_recent(self) -> None:
        self._recent_files.clear()
        self._update_recent_menu()

    # ------------------------------------------------------------------
    # Async loading
    # ------------------------------------------------------------------

    def _get_loader(self, mode: ViewerMode, ext: str):
        if mode == ViewerMode.IMAGE:
            from loaders.image_loader import load_image
            return load_image
        if mode == ViewerMode.CAD_2D:
            from loaders.dxf_loader import load_dxf
            return load_dxf
        if mode == ViewerMode.MODEL_3D:
            if ext in (".step", ".stp"):
                from loaders.step_loader import load_step
                return load_step
            from loaders.stl_loader import load_stl
            return load_stl
        return None

    def _ensure_image_viewer_signals(self) -> None:
        if self._image_viewer_signals_connected:
            return
        iv = self._viewer_stack.image_viewer
        iv.undo_available.connect(self._btn_undo.setEnabled)
        self._image_viewer_signals_connected = True

    def _set_loading(self, loading: bool) -> None:
        self._header_bar.setEnabled(not loading)
        self._status_loading.setText("  로딩 중...  " if loading else "")

    def _cancel_loading(self, wait: bool = False) -> None:
        self._load_gen += 1
        if self._loader_thread is not None:
            if wait and self._loader_thread.isRunning():
                self._loader_thread.wait(1500)
            self._loader_thread = None
        if wait:
            for thread in list(self._loader_threads):
                if thread.isRunning():
                    thread.wait(1500)
        self._set_loading(False)

    def _forget_loader_thread(self, thread: LoaderThread) -> None:
        if thread in self._loader_threads:
            self._loader_threads.remove(thread)
        if self._loader_thread is thread:
            self._loader_thread = None
        thread.deleteLater()

    def _on_load_finished(self, gen: int, result) -> None:
        if gen != self._load_gen:
            return
        mode = self._pending_mode
        if mode == ViewerMode.IMAGE:
            self._ensure_image_viewer_signals()
            self._viewer_stack.image_viewer.display_image(result, self._current_file or "")
        elif mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.display_dxf(result)
        elif mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.display_mesh(result)
        self._set_loading(False)
        if self._current_file:
            path = Path(self._current_file)
            size_text = _safe_file_size(path)
            self._status_info.setText(f"  {path.name}    {size_text}")
        self._status_mode.setText(_MODE_LABEL.get(mode, ""))

    def _on_load_error(self, gen: int, msg: str) -> None:
        if gen != self._load_gen:
            return
        self._set_loading(False)
        QMessageBox.warning(self, "파일 오류", f"파일을 열 수 없습니다:\n{msg}")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def open_file(self, path: str) -> None:
        """Open a file directly — used when launched with a CLI/file-association argument."""
        p = Path(path)
        if not p.is_file():
            return
        parent = str(p.parent)
        self._file_browser.navigate_to(parent)
        self._on_folder_selected(parent)
        self._on_file_opened(path)

    def _on_folder_selected(self, folder_path: str) -> None:
        self._search_box.blockSignals(True)
        self._search_box.clear()
        self._search_box.blockSignals(False)
        self._viewer_stack.file_panel.load_folder(folder_path)
        self._viewer_stack.show_browser()
        self._set_browse_mode()
        count = self._viewer_stack.file_panel.file_count()
        self._status_info.setText(f"  {_folder_status_name(folder_path)}    {count}개 항목")
        self._status_zoom.setText("")
        self._status_mode.setText("")

    def _on_file_opened(self, file_path: str) -> None:
        self._cancel_loading()
        self._current_file = file_path
        self._add_recent(file_path)

        mode = detect_viewer_mode(file_path)
        self._pending_mode = mode
        path = Path(file_path)

        loader_fn = self._get_loader(mode, path.suffix.lower())
        if loader_fn is None:
            self._viewer_stack.switch_to(mode)
            self._set_back_only_mode()
            self._status_info.setText(f"  {path.name}    {_safe_file_size(path)}")
            self._status_mode.setText("")
            return

        self._viewer_stack.switch_to(mode)
        if mode == ViewerMode.IMAGE:
            self._set_image_mode()
        elif mode == ViewerMode.CAD_2D:
            self._set_cad_mode()
        elif mode == ViewerMode.MODEL_3D:
            self._set_3d_mode()

        self._set_loading(True)
        self._status_info.setText(f"  {path.name}    {_safe_file_size(path)}")
        self._status_zoom.setText("")
        self._status_mode.setText(_MODE_LABEL.get(mode, ""))

        self._load_gen += 1
        gen = self._load_gen
        self._loader_thread = LoaderThread(loader_fn, file_path, self)
        self._loader_threads.append(self._loader_thread)
        self._loader_thread.loaded.connect(
            lambda result, g=gen: self._on_load_finished(g, result)
        )
        self._loader_thread.error.connect(
            lambda msg, g=gen: self._on_load_error(g, msg)
        )
        self._loader_thread.finished.connect(
            lambda thread=self._loader_thread: self._forget_loader_thread(thread)
        )
        self._loader_thread.start()

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "파일 열기", "", _OPEN_FILTER)
        if path:
            self._on_file_opened(path)

    def _on_view_style(self, style: ViewStyle) -> None:
        self._viewer_stack.file_panel.set_view_style(style)
        self._settings.setValue("viewStyle", _STYLE_TO_IDX[style])
        self._style_buttons[style].setChecked(True)
        self._view_actions[style].setChecked(True)

    def _on_search(self, text: str) -> None:
        self._viewer_stack.file_panel.set_filter(text)

    def _go_back(self) -> None:
        self._cancel_loading()
        self._current_mode = ViewerMode.NONE
        self._viewer_stack.show_browser()
        self._set_browse_mode()
        folder = self._viewer_stack.file_panel._current_folder
        count  = self._viewer_stack.file_panel.file_count()
        self._status_info.setText(f"  {_folder_status_name(folder)}    {count}개 항목")
        self._status_zoom.setText("")
        self._status_mode.setText("")

    # ------------------------------------------------------------------
    # Zoom / fit dispatch
    # ------------------------------------------------------------------

    def _zoom_in(self) -> None:
        if self._current_mode == ViewerMode.IMAGE:
            self._viewer_stack.image_viewer.zoom_in()
        elif self._current_mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.zoom_in()
        elif self._current_mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.zoom_in()

    def _zoom_out(self) -> None:
        if self._current_mode == ViewerMode.IMAGE:
            self._viewer_stack.image_viewer.zoom_out()
        elif self._current_mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.zoom_out()
        elif self._current_mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.zoom_out()

    def _fit(self) -> None:
        if self._current_mode == ViewerMode.IMAGE:
            self._viewer_stack.image_viewer.fit()
        elif self._current_mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.fit()
        elif self._current_mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.fit()

    # ------------------------------------------------------------------
    # Header-bar mode switch
    # ------------------------------------------------------------------

    def _set_browse_mode(self) -> None:
        self._current_mode = ViewerMode.NONE
        self._browse_bar.setVisible(True)
        self._viewer_bar.setVisible(False)

    def _set_image_mode(self) -> None:
        self._ensure_image_viewer_signals()
        self._current_mode = ViewerMode.IMAGE
        self._browse_bar.setVisible(False)
        self._viewer_bar.setVisible(True)
        self._image_grp.setVisible(True)
        self._zoom_grp.setVisible(True)
        self._rot_grp.setVisible(True)

    def _set_cad_mode(self) -> None:
        self._current_mode = ViewerMode.CAD_2D
        self._browse_bar.setVisible(False)
        self._viewer_bar.setVisible(True)
        self._image_grp.setVisible(False)
        self._zoom_grp.setVisible(True)
        self._rot_grp.setVisible(False)

    def _set_3d_mode(self) -> None:
        self._current_mode = ViewerMode.MODEL_3D
        self._browse_bar.setVisible(False)
        self._viewer_bar.setVisible(True)
        self._image_grp.setVisible(False)
        self._zoom_grp.setVisible(True)
        self._rot_grp.setVisible(False)

    def _set_back_only_mode(self) -> None:
        self._current_mode = ViewerMode.NONE
        self._browse_bar.setVisible(False)
        self._viewer_bar.setVisible(True)
        self._image_grp.setVisible(False)
        self._zoom_grp.setVisible(False)
        self._rot_grp.setVisible(False)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_vsep() -> QWidget:
    sep = QWidget()
    sep.setObjectName("vSep")
    sep.setFixedWidth(1)
    sep.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    return sep


def _make_rotate_icon(clockwise: bool) -> QIcon:
    size = 24
    center = QPointF(size / 2, size / 2)
    radius = 7.2
    color = QColor("#5f4632")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    if clockwise:
        degrees = range(220, -70, -10)
    else:
        degrees = range(-40, 250, 10)

    points = [
        QPointF(
            center.x() + radius * math.cos(math.radians(deg)),
            center.y() + radius * math.sin(math.radians(deg)),
        )
        for deg in degrees
    ]

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(QPolygonF(points))

    end = points[-1]
    prev = points[-2]
    angle = math.atan2(end.y() - prev.y(), end.x() - prev.x())
    arrow_size = 4.4
    spread = 0.72
    arrow = QPolygonF([
        end,
        QPointF(
            end.x() - arrow_size * math.cos(angle - spread),
            end.y() - arrow_size * math.sin(angle - spread),
        ),
        QPointF(
            end.x() - arrow_size * math.cos(angle + spread),
            end.y() - arrow_size * math.sin(angle + spread),
        ),
    ])
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(arrow)
    painter.end()
    return QIcon(pixmap)


def _format_size(n: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


def _safe_file_size(path: Path) -> str:
    try:
        return _format_size(path.stat().st_size)
    except OSError:
        return "크기 알 수 없음"


def _settings_int(settings: QSettings, key: str, default: int) -> int:
    try:
        return int(settings.value(key, default))
    except (TypeError, ValueError):
        return default


def _folder_status_name(folder: str) -> str:
    if folder == COMPUTER_LOCATION:
        return "내 컴퓨터"
    return folder
