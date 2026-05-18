import sys
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "image" / "icon" / "Casa-ImageViewer-ICON.png"


def main() -> None:
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
