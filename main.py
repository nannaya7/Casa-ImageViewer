import sys
import ctypes
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"
_APP_ID = "PyImageViewer.CasaImageViewer.1"


def main() -> None:
    # Windows taskbar icon requires AppUserModelID set before QApplication
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)

    app = QApplication(sys.argv)
    app.setApplicationName("Image & CAD Integrated Viewer")
    app.setOrganizationName("PyImageViewer")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
