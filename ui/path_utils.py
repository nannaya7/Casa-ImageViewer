from pathlib import Path

SPECIAL_FOLDERS: list[tuple[str, str]] = [
    ("바탕 화면", "Desktop"),
    ("문서",     "Documents"),
    ("다운로드", "Downloads"),
    ("음악",     "Music"),
    ("사진",     "Pictures"),
    ("동영상",   "Videos"),
]


def entry_display_name(path: Path) -> str:
    drive = path.drive.rstrip(":\\/")
    if drive and not path.name:
        return f"{drive} 드라이브"
    return path.name or str(path)


def is_drive_root(path: Path) -> bool:
    return bool(path.drive) and path.parent == path


def format_size(n: int) -> str:
    for unit, threshold in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"
