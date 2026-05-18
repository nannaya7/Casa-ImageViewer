from pathlib import Path
from models.viewer_mode import ViewerMode

IMAGE_EXTENSIONS = frozenset({
    '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.ico',
    '.tif', '.tiff', '.webp',
    '.ppm', '.pgm', '.pbm', '.pnm', '.tga', '.dds', '.dib',
    '.heic', '.heif', '.avif', '.svg', '.raw', '.psd', '.pdf',
})

CAD_2D_EXTENSIONS = frozenset({'.dxf', '.dwg'})

MODEL_3D_EXTENSIONS = frozenset({'.stl', '.step', '.stp'})

ALL_SUPPORTED = IMAGE_EXTENSIONS | CAD_2D_EXTENSIONS | MODEL_3D_EXTENSIONS


def detect_viewer_mode(file_path: str) -> ViewerMode:
    ext = Path(file_path).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return ViewerMode.IMAGE
    if ext in CAD_2D_EXTENSIONS:
        return ViewerMode.CAD_2D
    if ext in MODEL_3D_EXTENSIONS:
        return ViewerMode.MODEL_3D
    return ViewerMode.NONE


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALL_SUPPORTED
