from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QLabel, QVBoxLayout,
    QFileDialog, QApplication,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QActionGroup, QIcon

from ui.file_browser import FileBrowserPanel
from ui.viewer_stack import ViewerStack
from ui.file_panel import ViewStyle
from services.file_type_detector import detect_viewer_mode
from models.viewer_mode import ViewerMode

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


_WINDOW_ICON = Path(__file__).parent.parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image & CAD Integrated Viewer")
        if _WINDOW_ICON.exists():
            self.setWindowIcon(QIcon(str(_WINDOW_ICON)))
        self.resize(1280, 800)
        self._current_file: str | None = None
        self._current_mode: ViewerMode = ViewerMode.NONE
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()

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

        # ── 공용 뷰어: 확대/축소/맞춤 (이미지 + CAD 모드 공유) ─────────
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

        quit_act = QAction("종료(&X)", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_act)

        mb.addMenu("보기(&V)")

    def _setup_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_info = QLabel("폴더를 선택하세요")
        self._status_zoom = QLabel("")
        self._status_mode = QLabel("")
        bar.addWidget(self._status_info, 1)
        bar.addPermanentWidget(self._status_zoom)
        bar.addPermanentWidget(self._status_mode)

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
        self._current_file = file_path
        mode = detect_viewer_mode(file_path)
        path = Path(file_path)

        if mode == ViewerMode.IMAGE:
            self._viewer_stack.image_viewer.load_file(file_path)
            self._set_image_mode()
        elif mode == ViewerMode.CAD_2D:
            self._viewer_stack.cad_viewer.load_file(file_path)
            self._set_cad_mode()
        elif mode == ViewerMode.MODEL_3D:
            self._viewer_stack.model3d_viewer.load_file(file_path)
            self._set_3d_mode()
        else:
            self._set_back_only_mode()

        self._viewer_stack.switch_to(mode)
        self._status_info.setText(f"  {path.name}    {_format_size(path.stat().st_size)}")
        self._status_zoom.setText("")
        self._status_mode.setText(_MODE_LABEL.get(mode, ""))

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "파일 열기", "", _OPEN_FILTER)
        if path:
            self._on_file_opened(path)

    def _on_view_style(self, style: ViewStyle) -> None:
        self._viewer_stack.file_panel.set_view_style(style)

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
        self._current_mode = ViewerMode.NONE
        self._viewer_stack.show_browser()
        self._set_browse_mode()
        folder = self._viewer_stack.file_panel._current_folder
        count = self._viewer_stack.file_panel.file_count()
        self._status_info.setText(f"  {folder}    ({count}개 항목)")
        self._status_zoom.setText("")
        self._status_mode.setText("")

    # ------------------------------------------------------------------
    # Generic viewer dispatch (zoom/fit shared between image and CAD)
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
