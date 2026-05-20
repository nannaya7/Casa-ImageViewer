from pathlib import Path
from PyQt6.QtGui import QPixmap, QIcon

_ICON_DIR = Path(__file__).parent.parent / "image" / "folder_icon"

_HOME = Path.home()
_FAVORITES = frozenset({
    _HOME / "Desktop",
    _HOME / "Documents",
    _HOME / "Downloads",
    _HOME / "Music",
    _HOME / "Pictures",
    _HOME / "Videos",
})

_pm: dict[str, QPixmap] = {}


def _ensure() -> None:
    if _pm:
        return
    for name in ("default", "link", "user", "favorite", "share", "open", "selected"):
        _pm[name] = QPixmap(str(_ICON_DIR / f"folder_{name}.png"))


def _base_type(path: Path) -> str:
    if path.is_symlink():
        return "link"
    if str(path).startswith("\\\\"):
        return "share"
    if path == _HOME:
        return "user"
    if path in _FAVORITES:
        return "favorite"
    return "default"


def make_folder_icon(path: Path) -> QIcon:
    _ensure()
    icon = QIcon()
    icon.addPixmap(_pm[_base_type(path)], QIcon.Mode.Normal,   QIcon.State.Off)
    icon.addPixmap(_pm["open"],           QIcon.Mode.Normal,   QIcon.State.On)
    icon.addPixmap(_pm["open"],           QIcon.Mode.Active,   QIcon.State.Off)
    icon.addPixmap(_pm["selected"],       QIcon.Mode.Selected, QIcon.State.Off)
    return icon


def clear_folder_icon_cache() -> None:
    _pm.clear()
