from typing import Callable, Any

from PyQt6.QtCore import QThread, pyqtSignal


class LoaderThread(QThread):
    """Run a blocking loader function in a background thread.

    Emit ``finished`` with the return value on success, or ``error`` with the
    exception message on failure.  The caller is responsible for ignoring stale
    results (e.g. via a generation counter) when the user navigates away before
    loading completes.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn: Callable[[str], Any], file_path: str, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._file_path = file_path

    def run(self) -> None:
        try:
            result = self._fn(self._file_path)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
