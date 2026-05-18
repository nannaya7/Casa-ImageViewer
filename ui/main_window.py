from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QLabel, QVBoxLayout,
    QFileDialog, QApplication, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QCloseEvent

from ui.file_browser import FileBrowserPanel
from ui.viewer_stack import ViewerStack
from ui.file_panel import ViewStyle
from services.file_type_detector import detect_viewer_mode
from services.loader_thread import LoaderThread
from models.viewer_mode import ViewerMode
from loaders.image_loader import load_image
from loaders.dxf_loader import load_dxf
from loaders.stl_loader import load_stl


_MODE_LABEL: dict[ViewerMode, str] = {
    ViewerMode.IMAGE: "이미지",
    ViewerMode.CAD_2D: "2D CAD",
    ViewerMode.MODEL_3D: "3D 모델",
    ViewerMode.NONE: "",
}

_OPEN_FILTER = (
    "지원 파일 (*.png *.jpg *.jpeg *.bmp *.gif *.ico *.tif *.tiff *.webp "
    "*.ppm *.pgm *.pbm *.pnm *.tga *.dds *.dib "
    "*.dxf *.dwg *.stl *.step *.stp);;"
    "이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.ico *.tif *.tiff *.webp);;"
    "2D CAD (*.dxf *.dwg);;"
    "3D 모델 (*.stl *.step *.stp);;"
    "모든 파일 (*.*)"
)

_VIEW_STYLES: list[tuple[ViewStyle, str]] = [
    (ViewStyle.LARGE_ICONS, "큰 아이콘"),
    (ViewStyle.SMALL_ICONS, "작은 아이콘"),
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
        self._load_gen: int = 0
        self._recent_files: list[str] = []

        self._settings = QSettings()

        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
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

        self._toolbar = self._build_toolbar()
        right_layout.addWidget(self._toolbar)

        self._viewer_stack = ViewerStack()
        self._viewer_stack.file_panel.file_opened.connect(self._on_file_opened)
        self._viewer_stack.file_panel.folder_navigated.connect(self._on_folder_selected)
        iv = self._viewer_stack.image_viewer
        iv.crop_mode_exited.connect(self._on_crop_mode_exited)
        iv.undo_available.connect(self._act_undo.setEnabled)
        right_layout.addWidget(self._viewer_stack)

        self._splitter.addWidget(self._file_browser)
        self._splitter.addWidget(right)
        self._splitter.setSizes([240, 1040])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        root.addWidget(self._splitter)

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar("도구 모음")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))

        # ── 뒤로 ──────────────────────────────────────────────────────
        self._act_back = QAction("← 뒤로", self)
        self._act_back.setShortcut("Alt+Left")
        self._act_back.triggered.connect(self._go_back)
        tb.addAction(self._act_back)
        self._sep_back = tb.addSeparator()

        # ── 탐색 모드: 뷰 스타일 ───────────────────────────────────────
        self._browse_acts: list[QAction] = []
        group = QActionGroup(self)
        group.setExclusive(True)
        self._view_actions: dict[ViewStyle, QAction] = {}

        for style, label in _VIEW_STYLES:
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, s=style: self._on_view_style(s))
            group.addAction(act)
            tb.addAction(act)
            self._view_actions[style] = act
            self._browse_acts.append(act)
        self._view_actions[ViewStyle.LARGE_ICONS].setChecked(True)

        # ── 이미지 전용: 편집 ──────────────────────────────────────────
        self._image_only_acts: list[QAction] = []

        sep_edit = tb.addSeparator()
        self._image_only_acts.append(sep_edit)

        self._act_undo = QAction("실행 취소", self)
        self._act_undo.setShortcut("Ctrl+Z")
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(lambda: self._viewer_stack.image_viewer.undo())
        tb.addAction(self._act_undo)
        self._image_only_acts.append(self._act_undo)

        sep_edit2 = tb.addSeparator()
        self._image_only_acts.append(sep_edit2)

        self._act_crop = QAction("자르기", self)
        self._act_crop.setCheckable(True)
        self._act_crop.triggered.connect(self._on_crop_toggle)
        tb.addAction(self._act_crop)
        self._image_only_acts.append(self._act_crop)

        act_resize = QAction("크기 조정", self)
        act_resize.triggered.connect(lambda: self._viewer_stack.image_viewer.open_resize_dialog())
        tb.addAction(act_resize)
        self._image_only_acts.append(act_resize)

        # ── 공용 뷰어: 확대/축소/맞춤 ─────────────────────────────────
        self._viewer_acts: list[QAction] = []

        sep_zoom = tb.addSeparator()
        self._viewer_acts.append(sep_zoom)

        act_zoom_in = QAction("확대", self)
        act_zoom_in.setShortcut("Ctrl++")
        act_zoom_in.triggered.connect(self._zoom_in)
        tb.addAction(act_zoom_in)
        self._viewer_acts.append(act_zoom_in)

        act_zoom_out = QAction("축소", self)
        act_zoom_out.setShortcut("Ctrl+-")
        act_zoom_out.triggered.connect(self._zoom_out)
        tb.addAction(act_zoom_out)
        self._viewer_acts.append(act_zoom_out)

        act_fit = QAction("화면 맞춤", self)
        act_fit.setShortcut("Ctrl+0")
        act_fit.triggered.connect(self._fit)
        tb.addAction(act_fit)
        self._viewer_acts.append(act_fit)

        # ── 이미지 전용: 회전 + 저장 ──────────────────────────────────
        sep_rot = tb.addSeparator()
        self._image_only_acts.append(sep_rot)

        for label, slot in (
            ("↻ 시계방향",  lambda: self._viewer_stack.image_viewer.rotate_cw()),
            ("↺ 반시계방향", lambda: self._viewer_stack.image_viewer.rotate_ccw()),
        ):
            act = QAction(label, self)
            act.triggered.connect(slot)
            tb.addAction(act)
            self._image_only_acts.append(act)

        sep_save = tb.addSeparator()
        self._image_only_acts.append(sep_save)

        act_save = QAction("다른 이름으로 저장", self)
        act_save.setShortcut("Ctrl+Shift+S")
        act_save.triggered.connect(lambda: self._viewer_stack.image_viewer.save_as())
        tb.addAction(act_save)
        self._image_only_acts.append(act_save)

        self._set_browse_mode()
        return tb

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

        mb.addMenu("보기(&V)")

    def _setup_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_info = QLabel("폴더를 선택하세요")
        self._status_loading = QLabel("")
        self._status_zoom = QLabel("")
        self._status_mode = QLabel("")
        bar.addWidget(self._status_info, 1)
        bar.addPermanentWidget(self._status_loading)
        bar.addPermanentWidget(self._status_zoom)
        bar.addPermanentWidget(self._status_mode)

    # ------------------------------------------------------------------
    # Settings — persist across sessions
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        geom = self._settings.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._settings.value("windowState")
        if state is not None:
            self.restoreState(state)

        style_idx = int(self._settings.value("viewStyle", 0))
        style = _IDX_TO_STYLE.get(style_idx, ViewStyle.LARGE_ICONS)
        self._viewer_stack.file_panel.set_view_style(style)
        self._view_actions[style].setChecked(True)

        recent = self._settings.value("recentFiles") or []
        if isinstance(recent, str):
            recent = [recent]
        self._recent_files = [p for p in recent if Path(p).exists()][:self._MAX_RECENT]
        self._update_recent_menu()

        last_folder = self._settings.value("lastFolder", "")
        if last_folder and Path(last_folder).is_dir():
            self._on_folder_selected(last_folder)

    def _save_settings(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        folder = self._viewer_stack.file_panel._current_folder
        if folder:
            self._settings.setValue("lastFolder", folder)
        self._settings.setValue("recentFiles", self._recent_files)
        style = next(
            (s for s, a in self._view_actions.items() if a.isChecked()),
            ViewStyle.LARGE_ICONS,
        )
        self._settings.setValue("viewStyle", _STYLE_TO_IDX[style])

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_loading()
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
        """Return the appropriate loader callable for the given mode/extension."""
        if mode == ViewerMode.IMAGE:
            return load_image
        if mode == ViewerMode.CAD_2D:
            return load_dxf
        if mode == ViewerMode.MODEL_3D:
            if ext in (".step", ".stp"):
                from loaders.step_loader import load_step
                return load_step
            return load_stl
        return None

    def _set_loading(self, loading: bool) -> None:
        self._toolbar.setEnabled(not loading)
        self._status_loading.setText("  로딩 중...  " if loading else "")

    def _cancel_loading(self) -> None:
        """Invalidate any pending load result and try to stop the thread."""
        self._load_gen += 1
        if self._loader_thread is not None:
            if self._loader_thread.isRunning():
                self._loader_thread.quit()
                self._loader_thread.wait(500)
            self._loader_thread = None
        self._set_loading(False)

    def _on_load_finished(self, gen: int, result) -> None:
        if gen != self._load_gen:
            return  # stale result — user already navigated away
        mode = self._pending_mode
        if mode == ViewerMode.IMAGE:
            self._viewer_stack.image_viewer.display_image(result, self._current_file or "")
        elif mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.display_dxf(result)
        elif mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.display_mesh(result)
        self._set_loading(False)
        if self._current_file:
            path = Path(self._current_file)
            self._status_info.setText(f"  {path.name}    {_format_size(path.stat().st_size)}")
        self._status_mode.setText(_MODE_LABEL.get(mode, ""))
        self._loader_thread = None

    def _on_load_error(self, gen: int, msg: str) -> None:
        if gen != self._load_gen:
            return
        self._set_loading(False)
        self._loader_thread = None
        QMessageBox.warning(self, "파일 오류", f"파일을 열 수 없습니다:\n{msg}")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_folder_selected(self, folder_path: str) -> None:
        self._viewer_stack.file_panel.load_folder(folder_path)
        self._viewer_stack.show_browser()
        self._set_browse_mode()
        count = self._viewer_stack.file_panel.file_count()
        self._status_info.setText(f"  {folder_path}    ({count}개 항목)")
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
            self._status_info.setText(f"  {path.name}    {_format_size(path.stat().st_size)}")
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
        self._status_info.setText(f"  {path.name}    {_format_size(path.stat().st_size)}")
        self._status_zoom.setText("")
        self._status_mode.setText(_MODE_LABEL.get(mode, ""))

        self._load_gen += 1
        gen = self._load_gen
        self._loader_thread = LoaderThread(loader_fn, file_path, self)
        self._loader_thread.finished.connect(
            lambda result, g=gen: self._on_load_finished(g, result)
        )
        self._loader_thread.error.connect(
            lambda msg, g=gen: self._on_load_error(g, msg)
        )
        self._loader_thread.start()

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "파일 열기", "", _OPEN_FILTER)
        if path:
            self._on_file_opened(path)

    def _on_view_style(self, style: ViewStyle) -> None:
        self._viewer_stack.file_panel.set_view_style(style)
        self._settings.setValue("viewStyle", _STYLE_TO_IDX[style])

    def _on_crop_toggle(self, checked: bool) -> None:
        iv = self._viewer_stack.image_viewer
        if checked:
            iv.enter_crop_mode()
        else:
            iv.exit_crop_mode()

    def _on_crop_mode_exited(self) -> None:
        self._act_crop.setChecked(False)

    def _go_back(self) -> None:
        iv = self._viewer_stack.image_viewer
        if iv.is_crop_mode:
            iv.exit_crop_mode()
        self._cancel_loading()
        self._current_mode = ViewerMode.NONE
        self._viewer_stack.show_browser()
        self._set_browse_mode()
        folder = self._viewer_stack.file_panel._current_folder
        count = self._viewer_stack.file_panel.file_count()
        self._status_info.setText(f"  {folder}    ({count}개 항목)")
        self._status_zoom.setText("")
        self._status_mode.setText("")

    # ------------------------------------------------------------------
    # Generic viewer dispatch (zoom/fit shared between image, CAD, 3D)
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
    # Toolbar mode switch
    # ------------------------------------------------------------------

    def _set_browse_mode(self) -> None:
        self._current_mode = ViewerMode.NONE
        self._act_back.setVisible(False)
        self._sep_back.setVisible(False)
        for act in self._browse_acts:
            act.setVisible(True)
        for act in self._image_only_acts:
            act.setVisible(False)
        for act in self._viewer_acts:
            act.setVisible(False)

    def _set_image_mode(self) -> None:
        self._current_mode = ViewerMode.IMAGE
        self._act_back.setVisible(True)
        self._sep_back.setVisible(True)
        for act in self._browse_acts:
            act.setVisible(False)
        for act in self._image_only_acts:
            act.setVisible(True)
        for act in self._viewer_acts:
            act.setVisible(True)
        self._act_crop.setChecked(False)

    def _set_cad_mode(self) -> None:
        self._current_mode = ViewerMode.CAD_2D
        self._act_back.setVisible(True)
        self._sep_back.setVisible(True)
        for act in self._browse_acts:
            act.setVisible(False)
        for act in self._image_only_acts:
            act.setVisible(False)
        for act in self._viewer_acts:
            act.setVisible(True)

    def _set_3d_mode(self) -> None:
        self._current_mode = ViewerMode.MODEL_3D
        self._act_back.setVisible(True)
        self._sep_back.setVisible(True)
        for act in self._browse_acts:
            act.setVisible(False)
        for act in self._image_only_acts:
            act.setVisible(False)
        for act in self._viewer_acts:
            act.setVisible(True)

    def _set_back_only_mode(self) -> None:
        self._current_mode = ViewerMode.NONE
        self._act_back.setVisible(True)
        self._sep_back.setVisible(True)
        for act in self._browse_acts:
            act.setVisible(False)
        for act in self._image_only_acts:
            act.setVisible(False)
        for act in self._viewer_acts:
            act.setVisible(False)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _format_size(n: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"
