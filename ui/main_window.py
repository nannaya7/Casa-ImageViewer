import math
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QVBoxLayout,
    QFileDialog, QMenu, QMessageBox,
    QPushButton, QButtonGroup, QFrame, QLineEdit,
    QSizePolicy, QDialog, QScrollArea, QTextBrowser,
)
from PyQt6.QtCore import Qt, QSize, QSettings, QPointF
from PyQt6.QtGui import (
    QAction, QActionGroup, QIcon, QCloseEvent, QKeySequence, QShortcut,
    QPixmap, QPainter, QPen, QColor, QPolygonF,
)

from ui.file_browser import COMPUTER_LOCATION, FileBrowserPanel
from ui.folder_icons import clear_folder_icon_cache
from ui.path_utils import format_size
from ui.viewer_stack import ViewerStack
from ui.file_panel import ViewStyle
from services.file_type_detector import (
    CAD_2D_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MODEL_3D_EXTENSIONS,
    detect_viewer_mode,
)
from services.loader_thread import LoaderThread
from models.viewer_mode import ViewerMode


_MODE_LABEL: dict[ViewerMode, str] = {
    ViewerMode.IMAGE:    "이미지",
    ViewerMode.CAD_2D:  "2D CAD",
    ViewerMode.MODEL_3D: "3D 모델",
    ViewerMode.NONE:    "",
}

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
_ABOUT_IMAGE = Path(__file__).parent.parent / "image" / "About_This_APP.png"

_LICENSE_HTML = """
<html>
<head>
<style>
    body { font-family: "Segoe UI", "Malgun Gothic", sans-serif; color: #4A382B;
           background: #FFFDF9; line-height: 1.45; }
    h2 { margin: 0 0 10px 0; color: #3A281E; }
    p { margin: 4px 0 14px 0; color: #7A6050; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #E5D7C8; padding: 8px 6px;
             text-align: left; vertical-align: top; }
    th { background: #EEE8DF; color: #3A281E; }
    a { color: #8A5A24; text-decoration: none; }
</style>
</head>
<body>
<h2>사용된 오픈소스 라이브러리</h2>
<p>아래 정보는 프로젝트에서 직접 사용하는 주요 패키지 기준입니다. 각 패키지의 세부
의존성은 배포판에 포함된 메타데이터와 원 프로젝트 라이선스를 따릅니다.</p>
<table>
    <tr><th>라이브러리</th><th>용도</th><th>라이선스</th></tr>
    <tr><td>PyQt6</td><td>GUI 프레임워크</td><td>GPL v3 또는 상용 라이선스</td></tr>
    <tr><td>Pillow</td><td>이미지 로딩/처리</td><td>HPND</td></tr>
    <tr><td>pillow-heif</td><td>HEIC/HEIF/AVIF 이미지 로딩</td><td>BSD-3-Clause</td></tr>
    <tr><td>rawpy</td><td>RAW 이미지 현상</td><td>MIT</td></tr>
    <tr><td>pypdfium2</td><td>PDF 페이지 렌더링</td><td>BSD-3-Clause, Apache-2.0 및 PDFium 관련 라이선스</td></tr>
    <tr><td>ezdxf</td><td>DXF 파싱 및 DWG 변환 연동</td><td>MIT</td></tr>
    <tr><td>trimesh</td><td>STL/메시 데이터 처리</td><td>MIT</td></tr>
    <tr><td>PyOpenGL</td><td>3D OpenGL 렌더링</td><td>BSD</td></tr>
    <tr><td>cadquery / cadquery-ocp / OCP</td><td>STEP 파일 로딩 및 테셀레이션</td><td>Apache-2.0 및 OCP 관련 라이선스</td></tr>
    <tr><td>numpy</td><td>수치 계산 및 메시 배열 처리</td><td>BSD-3-Clause</td></tr>
    <tr><td>ODA File Converter</td><td>DWG → DXF 변환</td><td>Open Design Alliance 배포 조건 적용, 별도 설치 필요</td></tr>
</table>
</body>
</html>
"""


def _extension_filter(exts: frozenset[str]) -> str:
    return " ".join(f"*{ext}" for ext in sorted(exts))


_IMAGE_FILTER = _extension_filter(IMAGE_EXTENSIONS)
_CAD_2D_FILTER = _extension_filter(CAD_2D_EXTENSIONS)
_MODEL_3D_FILTER = _extension_filter(MODEL_3D_EXTENSIONS)
_SUPPORTED_FILTER = " ".join((_IMAGE_FILTER, _CAD_2D_FILTER, _MODEL_3D_FILTER))

_OPEN_FILTER = (
    f"지원 파일 ({_SUPPORTED_FILTER});;"
    f"이미지 ({_IMAGE_FILTER});;"
    f"2D CAD ({_CAD_2D_FILTER});;"
    f"3D 모델 ({_MODEL_3D_FILTER});;"
    "모든 파일 (*.*)"
)


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
        outer.addWidget(self._build_browse_bar())
        outer.addWidget(self._build_viewer_bar())

        self._viewer_bar.setVisible(False)
        return container

    def _build_browse_bar(self) -> QWidget:
        self._browse_bar = QWidget()
        self._browse_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        bl = QHBoxLayout(self._browse_bar)
        bl.setContentsMargins(12, 9, 12, 9)
        bl.setSpacing(8)

        btn_open = QPushButton("  열기")
        btn_open.setObjectName("btnOpen")
        btn_open.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
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

        return self._browse_bar

    def _build_viewer_bar(self) -> QWidget:
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

        # Image-only controls
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

        # Zoom controls (image + CAD + 3D)
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

        # Rotate / save controls (image only)
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

        self._btn_auto_resize = QPushButton("Auto-Resize")
        self._btn_auto_resize.setObjectName("btnAutoResize")
        self._btn_auto_resize.setCheckable(True)
        self._btn_auto_resize.setFixedHeight(34)
        self._btn_auto_resize.setToolTip("창 크기가 바뀔 때 이미지를 자동으로 맞춤")
        self._btn_auto_resize.toggled.connect(
            lambda checked: self._viewer_stack.image_viewer.set_auto_resize(checked)
        )
        rg.addWidget(self._btn_auto_resize)
        vl.addWidget(self._rot_grp)

        vl.addStretch(1)
        return self._viewer_bar

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
        quit_act.triggered.connect(self.close)
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
        about_act = QAction("이 앱에 관하여", self)
        about_act.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_act)

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
            self._settings, "viewStyle", _STYLE_TO_IDX[ViewStyle.SMALL_ICONS]
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
        self._settings.setValue("thumbnailSize", self._viewer_stack.file_panel.thumbnail_size())

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_loading(wait=True)
        self._save_settings()
        clear_folder_icon_cache()
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
                self._loader_thread.wait()
            self._loader_thread = None
        if wait:
            for thread in list(self._loader_threads):
                if thread.isRunning():
                    thread.wait()
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
            self._status_info.setText(f"  {path.name}    {_safe_file_size(path)}")
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
        path = Path(file_path)
        if not path.is_file():
            QMessageBox.warning(self, "파일 없음", f"파일을 찾을 수 없습니다:\n{file_path}")
            self._recent_files = [p for p in self._recent_files if p != file_path]
            self._update_recent_menu()
            return

        mode = detect_viewer_mode(file_path)
        if mode == ViewerMode.NONE:
            QMessageBox.warning(self, "지원하지 않는 파일", f"지원하지 않는 파일 형식입니다:\n{path.name}")
            return

        self._current_file = file_path
        self._add_recent(file_path)
        self._pending_mode = mode

        loader_fn = self._get_loader(mode, path.suffix.lower())
        if loader_fn is None:
            self._viewer_stack.switch_to(mode)
            self._set_viewer_mode(ViewerMode.NONE)
            self._status_info.setText(f"  {path.name}    {_safe_file_size(path)}")
            self._status_mode.setText("")
            return

        self._viewer_stack.switch_to(mode)
        self._set_viewer_mode(mode)

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

    def _show_about_dialog(self) -> None:
        if not _ABOUT_IMAGE.exists():
            QMessageBox.warning(self, "이 앱에 관하여", f"이미지를 찾을 수 없습니다:\n{_ABOUT_IMAGE}")
            return

        pixmap = QPixmap(str(_ABOUT_IMAGE))
        if pixmap.isNull():
            QMessageBox.warning(self, "이 앱에 관하여", "About 이미지를 읽을 수 없습니다.")
            return

        max_width = 900
        display_pixmap = pixmap
        if pixmap.width() > max_width:
            display_pixmap = pixmap.scaled(
                max_width,
                int(pixmap.height() * max_width / pixmap.width()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        dialog = QDialog(self)
        dialog.setWindowTitle("이 앱에 관하여")
        if _WINDOW_ICON.exists():
            dialog.setWindowIcon(QIcon(str(_WINDOW_ICON)))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addStretch(1)
        close_button = QPushButton("X")
        close_button.setFixedSize(30, 30)
        close_button.setToolTip("닫기")
        close_button.clicked.connect(dialog.reject)
        top_bar.addWidget(close_button)
        layout.addLayout(top_bar)

        image_container = QWidget()
        image_container.setFixedSize(display_pixmap.size())

        label = QLabel(image_container)
        label.setPixmap(display_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setGeometry(0, 0, display_pixmap.width(), display_pixmap.height())

        license_button = QPushButton(image_container)
        license_button.setToolTip("사용된 오픈소스 라이선스 정보 보기")
        license_button.setCursor(Qt.CursorShape.PointingHandCursor)
        license_button.clicked.connect(self._show_open_source_dialog)
        license_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 1);
                border: none;
                border-radius: 22px;
            }
            QPushButton:hover {
                background: rgba(216, 161, 91, 35);
                border: 2px solid #D8A15B;
            }
            QPushButton:pressed {
                background: rgba(216, 161, 91, 60);
            }
        """)
        scale_x = display_pixmap.width() / pixmap.width()
        scale_y = display_pixmap.height() / pixmap.height()
        license_button.setGeometry(
            int(46 * scale_x), int(1304 * scale_y),
            int(868 * scale_x), int(172 * scale_y),
        )
        license_button.raise_()

        scroll_area = QScrollArea()
        scroll_area.setWidget(image_container)
        scroll_area.setWidgetResizable(False)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(scroll_area)

        dialog.resize(
            min(display_pixmap.width() + 40, 940),
            min(display_pixmap.height() + 70, 780),
        )
        dialog.exec()

    def _show_open_source_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("오픈소스 라이선스")
        if _WINDOW_ICON.exists():
            dialog.setWindowIcon(QIcon(str(_WINDOW_ICON)))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        title = QLabel("오픈소스 라이선스")
        title.setObjectName("dialogTitle")
        top_bar.addWidget(title)
        top_bar.addStretch(1)
        close_button = QPushButton("X")
        close_button.setFixedSize(30, 30)
        close_button.setToolTip("닫기")
        close_button.clicked.connect(dialog.reject)
        top_bar.addWidget(close_button)
        layout.addLayout(top_bar)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_LICENSE_HTML)
        layout.addWidget(browser)

        dialog.resize(720, 560)
        dialog.exec()

    def _on_view_style(self, style: ViewStyle) -> None:
        self._viewer_stack.file_panel.set_view_style(style)
        self._settings.setValue("viewStyle", _STYLE_TO_IDX[style])
        self._style_buttons[style].setChecked(True)
        self._view_actions[style].setChecked(True)

    def _on_search(self, text: str) -> None:
        self._viewer_stack.file_panel.set_filter(text)

    def _go_back(self) -> None:
        self._cancel_loading()
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

    def _set_viewer_mode(self, mode: ViewerMode) -> None:
        """Show viewer header. ViewerMode.NONE = back button only (no viewer controls)."""
        self._current_mode = mode
        self._browse_bar.setVisible(False)
        self._viewer_bar.setVisible(True)
        self._image_grp.setVisible(mode == ViewerMode.IMAGE)
        self._zoom_grp.setVisible(mode != ViewerMode.NONE)
        self._rot_grp.setVisible(mode == ViewerMode.IMAGE)
        if mode == ViewerMode.IMAGE:
            self._ensure_image_viewer_signals()
        else:
            self._btn_auto_resize.blockSignals(True)
            self._btn_auto_resize.setChecked(False)
            self._btn_auto_resize.blockSignals(False)


# ------------------------------------------------------------------
# Module-level helpers
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

    degrees = range(220, -70, -10) if clockwise else range(-40, 250, 10)
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


def _safe_file_size(path: Path) -> str:
    try:
        return format_size(path.stat().st_size)
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
