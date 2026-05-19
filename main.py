import sys
import ctypes
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"
_APP_ID    = "PyImageViewer.CasaImageViewer.1"

_APP_QSS = """
/* ── Base ─────────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #F8F4EE;
}
QWidget {
    font-family: "Segoe UI", "맑은 고딕", sans-serif;
    font-size: 13px;
    color: #4A382B;
    background-color: #F8F4EE;
}

/* ── Menu bar ──────────────────────────────────────────────────── */
QMenuBar {
    background-color: #EEE8DF;
    border-bottom: 1px solid #E5D7C8;
    padding: 2px 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #F3E5D0;
}
QMenu {
    background-color: #F8F4EE;
    border: 1px solid #E5D7C8;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 24px 6px 14px;
}
QMenu::item:selected {
    background-color: #F3E5D0;
}
QMenu::separator {
    height: 1px;
    background: #E5D7C8;
    margin: 4px 8px;
}

/* ── Header bar ────────────────────────────────────────────────── */
QWidget#headerBar {
    background-color: #EEE8DF;
    border-bottom: 1.5px solid #E5D7C8;
}

/* ── Default buttons ───────────────────────────────────────────── */
QPushButton {
    background-color: #EDE5D6;
    border: 1px solid #E5D7C8;
    border-radius: 12px;
    padding: 4px 14px;
    color: #4A382B;
}
QPushButton:hover {
    background-color: #F3E5D0;
    border-color: #D8A15B;
}
QPushButton:pressed {
    background-color: #E8D0B4;
}
QPushButton:checked {
    background-color: #D8A15B;
    border-color: #B87830;
    color: #3A281E;
    font-weight: 600;
}
QPushButton:disabled {
    color: #B8A89A;
    border-color: #E5D7C8;
    background-color: #F8F4EE;
}

/* ── Open / Back buttons ───────────────────────────────────────── */
QPushButton#btnOpen, QPushButton#btnBack {
    background-color: #EDE5D6;
    border: 1.5px solid #E5D7C8;
    border-radius: 17px;
    padding: 5px 18px;
    font-weight: 600;
}
QPushButton#btnOpen:hover, QPushButton#btnBack:hover {
    background-color: #F3E5D0;
    border-color: #D8A15B;
}
QPushButton#btnOpen:pressed, QPushButton#btnBack:pressed {
    background-color: #E8D0B4;
}

/* ── Segmented group ───────────────────────────────────────────── */
QFrame#segGroup {
    background-color: #EDE5D6;
    border: 1.5px solid #E5D7C8;
    border-radius: 17px;
}
QPushButton#segBtn {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 4px 14px;
    color: #7A6050;
    font-weight: normal;
}
QPushButton#segBtn:checked {
    background-color: #D8A15B;
    border: none;
    color: #3A281E;
    font-weight: 600;
}
QPushButton#segBtn:hover:!checked {
    background-color: rgba(0, 0, 0, 20);
}
QPushButton#segBtn:pressed {
    background-color: #C48840;
    border: none;
}

/* ── Search box ────────────────────────────────────────────────── */
QLineEdit#searchBox {
    background-color: #FFFDF9;
    border: 1.5px solid #E5D7C8;
    border-radius: 17px;
    padding: 4px 14px;
    color: #4A382B;
    selection-background-color: #F0D9A0;
}
QLineEdit#searchBox:focus {
    border-color: #D8A15B;
    background-color: #FFFDF9;
}

/* ── Vertical separator ────────────────────────────────────────── */
QWidget#vSep {
    background-color: #E5D7C8;
}

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle:horizontal {
    background-color: #E5D7C8;
    width: 1px;
}

/* ── Folder header label ───────────────────────────────────────── */
QLabel#folderHeader {
    background-color: #EEE8DF;
    color: #7A6050;
    font-size: 12px;
    font-weight: 600;
    border-bottom: 1px solid #E5D7C8;
    padding-left: 4px;
}

/* ── Tree view (left panel) ────────────────────────────────────── */
QTreeView {
    background-color: #FFFDF9;
    border: none;
    font-size: 12px;
    outline: none;
}
QTreeView::item {
    padding: 3px 4px;
    border-radius: 4px;
}
QTreeView::item:selected {
    background-color: #F0D9A0;
    color: #3A281E;
}
QTreeView::item:hover:!selected {
    background-color: #F3E5D0;
}

/* ── List widget (file panel icons) ───────────────────────────── */
QListWidget {
    background-color: #FFFDF9;
    border: none;
    outline: none;
}
QListWidget::item {
    border-radius: 6px;
    padding: 2px;
}
QListWidget::item:selected {
    background-color: #F0D9A0;
    color: #3A281E;
}
QListWidget::item:hover:!selected {
    background-color: #F3E5D0;
}

/* ── Detail tree (file panel list) ────────────────────────────── */
QTreeWidget {
    background-color: #FFFDF9;
    border: none;
    alternate-background-color: #F8F4EE;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 0;
}
QTreeWidget::item:selected {
    background-color: #F0D9A0;
    color: #3A281E;
}
QTreeWidget::item:hover:!selected {
    background-color: #F3E5D0;
}
QHeaderView {
    background-color: #EEE8DF;
}
QHeaderView::section {
    background-color: #EEE8DF;
    border: none;
    border-right: 1px solid #E5D7C8;
    border-bottom: 1px solid #E5D7C8;
    padding: 4px 8px;
    font-size: 12px;
    color: #7A6050;
    font-weight: 600;
}

/* ── Status bar ────────────────────────────────────────────────── */
QStatusBar {
    background-color: #EEE8DF;
    border-top: 1px solid #E5D7C8;
    color: #7A6050;
    font-size: 12px;
}
QStatusBar QLabel {
    background: transparent;
    color: #7A6050;
    font-size: 12px;
}

/* ── Scrollbars ────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #D0BCA8;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #B8A080;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none; height: 0; width: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #D0BCA8;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #B8A080;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none; height: 0; width: 0;
}

/* ── Resize dialog spinboxes ───────────────────────────────────── */
QSpinBox {
    background-color: #FFFDF9;
    border: 1.5px solid #E5D7C8;
    border-radius: 6px;
    padding: 3px 6px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #EDE5D6;
    border: none;
    border-left: 1px solid #E5D7C8;
    width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #F3E5D0;
}

/* ── Checkboxes ────────────────────────────────────────────────── */
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #E5D7C8;
    border-radius: 4px;
    background-color: #FFFDF9;
}
QCheckBox::indicator:checked {
    background-color: #D8A15B;
    border-color: #B87830;
}

/* ── Dialogs ───────────────────────────────────────────────────── */
QDialog {
    background-color: #F8F4EE;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}
"""



def main() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)

    app = QApplication(sys.argv)
    app.setApplicationName("Image & CAD Integrated Viewer")
    app.setOrganizationName("PyImageViewer")

    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    app.setStyleSheet(_APP_QSS)

    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1])
        if arg_path.is_file():
            QTimer.singleShot(0, lambda: window.open_file(str(arg_path)))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
