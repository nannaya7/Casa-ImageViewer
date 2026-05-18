import sys
import ctypes
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"
_APP_ID    = "PyImageViewer.CasaImageViewer.1"

_APP_QSS = """
/* ── Base ─────────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #F5EDE0;
}
QWidget {
    font-family: "Segoe UI", "맑은 고딕", sans-serif;
    font-size: 13px;
    color: #3D2B1A;
    background-color: #F5EDE0;
}

/* ── Menu bar ──────────────────────────────────────────────────── */
QMenuBar {
    background-color: #EDE0CC;
    border-bottom: 1px solid #D4C4A8;
    padding: 2px 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #DDD0B8;
}
QMenu {
    background-color: #F5EDE0;
    border: 1px solid #C8B898;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 24px 6px 14px;
}
QMenu::item:selected {
    background-color: #E0D0B8;
}
QMenu::separator {
    height: 1px;
    background: #D8C8B0;
    margin: 4px 8px;
}

/* ── Header bar ────────────────────────────────────────────────── */
QWidget#headerBar {
    background-color: #EDE0CC;
    border-bottom: 1.5px solid #D4C4A8;
}

/* ── Default buttons ───────────────────────────────────────────── */
QPushButton {
    background-color: #E8D8C0;
    border: 1px solid #C8B898;
    border-radius: 12px;
    padding: 4px 14px;
    color: #3D2B1A;
}
QPushButton:hover {
    background-color: #E0CEBA;
    border-color: #B8A888;
}
QPushButton:pressed {
    background-color: #D4C0A0;
}
QPushButton:checked {
    background-color: #C8B498;
    border-color: #A89070;
    color: #2A1810;
    font-weight: 600;
}
QPushButton:disabled {
    color: #B0A090;
    border-color: #D8C8B0;
    background-color: #F0E8DE;
}

/* ── Open / Back buttons ───────────────────────────────────────── */
QPushButton#btnOpen, QPushButton#btnBack {
    background-color: #E8D8C0;
    border: 1.5px solid #C8B098;
    border-radius: 17px;
    padding: 5px 18px;
    font-weight: 600;
}
QPushButton#btnOpen:hover, QPushButton#btnBack:hover {
    background-color: #DFD0B0;
}
QPushButton#btnOpen:pressed, QPushButton#btnBack:pressed {
    background-color: #D4C0A0;
}

/* ── Segmented group ───────────────────────────────────────────── */
QFrame#segGroup {
    background-color: #E8D8C0;
    border: 1.5px solid #C8B898;
    border-radius: 17px;
}
QPushButton#segBtn {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 4px 14px;
    color: #5A4A3A;
    font-weight: normal;
}
QPushButton#segBtn:checked {
    background-color: #D4C0A0;
    border: none;
    color: #2A1810;
    font-weight: 600;
}
QPushButton#segBtn:hover:!checked {
    background-color: rgba(0, 0, 0, 30);
}
QPushButton#segBtn:pressed {
    background-color: #C8B898;
    border: none;
}

/* ── Search box ────────────────────────────────────────────────── */
QLineEdit#searchBox {
    background-color: #F0E8DC;
    border: 1.5px solid #C8B898;
    border-radius: 17px;
    padding: 4px 14px;
    color: #3D2B1A;
    selection-background-color: #D4C0A0;
}
QLineEdit#searchBox:focus {
    border-color: #A88858;
    background-color: #FAF4EE;
}

/* ── Vertical separator ────────────────────────────────────────── */
QWidget#vSep {
    background-color: #D0C0A8;
}

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle:horizontal {
    background-color: #D4C4A8;
    width: 1px;
}

/* ── Folder header label ───────────────────────────────────────── */
QLabel#folderHeader {
    background-color: #E8D8C4;
    color: #5A4A3A;
    font-size: 12px;
    font-weight: 600;
    border-bottom: 1px solid #D4C4A8;
    padding-left: 4px;
}

/* ── Tree view (left panel) ────────────────────────────────────── */
QTreeView {
    background-color: #F5EDE0;
    border: none;
    font-size: 12px;
    outline: none;
}
QTreeView::item {
    padding: 3px 4px;
    border-radius: 4px;
}
QTreeView::item:selected {
    background-color: #DDD0B8;
    color: #2A1810;
}
QTreeView::item:hover:!selected {
    background-color: #EAE0D0;
}
QTreeView::branch {
    background: transparent;
}

/* ── List widget (file panel icons) ───────────────────────────── */
QListWidget {
    background-color: #FAF5EE;
    border: none;
    outline: none;
}
QListWidget::item {
    border-radius: 6px;
    padding: 2px;
}
QListWidget::item:selected {
    background-color: #DDD0B8;
    color: #2A1810;
}
QListWidget::item:hover:!selected {
    background-color: #EEE8DC;
}

/* ── Detail tree (file panel list) ────────────────────────────── */
QTreeWidget {
    background-color: #FAF5EE;
    border: none;
    alternate-background-color: #F5EFE8;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 0;
}
QTreeWidget::item:selected {
    background-color: #DDD0B8;
    color: #2A1810;
}
QTreeWidget::item:hover:!selected {
    background-color: #EEE8DC;
}
QHeaderView {
    background-color: #EDE0CC;
}
QHeaderView::section {
    background-color: #EDE0CC;
    border: none;
    border-right: 1px solid #D4C4A8;
    border-bottom: 1px solid #D4C4A8;
    padding: 4px 8px;
    font-size: 12px;
    color: #5A4A3A;
    font-weight: 600;
}

/* ── Status bar ────────────────────────────────────────────────── */
QStatusBar {
    background-color: #EDE0CC;
    border-top: 1px solid #D4C4A8;
    color: #5A4A3A;
    font-size: 12px;
}
QStatusBar QLabel {
    background: transparent;
    color: #5A4A3A;
    font-size: 12px;
}

/* ── Scrollbars ────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #C8B898;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #B0A080;
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
    background: #C8B898;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #B0A080;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none; height: 0; width: 0;
}

/* ── Resize dialog spinboxes ───────────────────────────────────── */
QSpinBox {
    background-color: #F0E8DC;
    border: 1.5px solid #C8B898;
    border-radius: 6px;
    padding: 3px 6px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #E8D8C0;
    border: none;
    border-left: 1px solid #C8B898;
    width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #DDD0B8;
}

/* ── Checkboxes ────────────────────────────────────────────────── */
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #C8B898;
    border-radius: 4px;
    background-color: #F0E8DC;
}
QCheckBox::indicator:checked {
    background-color: #C8B498;
    border-color: #A89070;
}

/* ── Dialogs ───────────────────────────────────────────────────── */
QDialog {
    background-color: #F5EDE0;
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
    app.setStyleSheet(_APP_QSS)

    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
