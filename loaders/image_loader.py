from pathlib import Path

from PIL import Image, ImageOps
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_HEIF_EXTS = {".heic", ".heif"}
_AVIF_EXTS = {".avif"}
_PDF_EXTS = {".pdf"}
_RAW_EXTS = {".raw"}
_SVG_EXTS = {".svg"}
_SVG_FALLBACK_SIZE = 1024
_SVG_MAX_SIZE = 4096


def load_image(file_path: str) -> Image.Image:
    ext = Path(file_path).suffix.lower()
    if ext in _SVG_EXTS:
        return _load_svg(file_path)
    if ext in _PDF_EXTS:
        return _load_pdf(file_path)
    if ext in _RAW_EXTS:
        return _load_raw(file_path)
    if ext in _HEIF_EXTS:
        _register_heif()
    elif ext in _AVIF_EXTS:
        _register_avif()
    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)
        return img.copy()


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    img = image.convert("RGBA")
    raw = img.tobytes("raw", "RGBA")
    qimage = QImage(raw, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage)


def _register_heif() -> None:
    try:
        from pillow_heif import register_heif_opener
    except ImportError as exc:
        raise ImportError(
            "HEIC/HEIF 파일을 열려면 pillow-heif 패키지가 필요합니다.\n"
            "설치: python -m pip install pillow-heif"
        ) from exc
    register_heif_opener()


def _register_avif() -> None:
    try:
        import pillow_heif
    except ImportError as exc:
        raise ImportError(
            "AVIF 파일을 열려면 pillow-heif 패키지가 필요합니다.\n"
            "설치: python -m pip install pillow-heif"
        ) from exc

    register_avif = getattr(pillow_heif, "register_avif_opener", None)
    if register_avif is not None:
        register_avif()
    else:
        pillow_heif.register_heif_opener()


def _load_raw(file_path: str) -> Image.Image:
    try:
        import rawpy
    except ImportError as exc:
        raise ImportError(
            "RAW 파일을 열려면 rawpy 패키지가 필요합니다.\n"
            "설치: python -m pip install rawpy"
        ) from exc

    with rawpy.imread(file_path) as raw:
        rgb = raw.postprocess()
    return Image.fromarray(rgb)


def _load_pdf(file_path: str) -> Image.Image:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ImportError(
            "PDF 파일을 열려면 pypdfium2 패키지가 필요합니다.\n"
            "설치: python -m pip install pypdfium2"
        ) from exc

    pdf = pdfium.PdfDocument(file_path)
    try:
        if len(pdf) == 0:
            raise ValueError("PDF에 페이지가 없습니다.")
        page = pdf[0]
        try:
            bitmap = page.render(scale=2.0)
            return bitmap.to_pil().convert("RGBA")
        finally:
            page.close()
    finally:
        pdf.close()


def _load_svg(file_path: str) -> Image.Image:
    renderer = QSvgRenderer(file_path)
    if not renderer.isValid():
        raise ValueError(f"SVG 파일을 읽을 수 없습니다: {file_path}")

    size = renderer.defaultSize()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        size = QSize(_SVG_FALLBACK_SIZE, _SVG_FALLBACK_SIZE)
    if size.width() > _SVG_MAX_SIZE or size.height() > _SVG_MAX_SIZE:
        size = size.scaled(
            QSize(_SVG_MAX_SIZE, _SVG_MAX_SIZE),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    image = QImage(size, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    return _qimage_to_pil(image)


def _qimage_to_pil(image: QImage) -> Image.Image:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = image.width()
    height = image.height()
    ptr = image.bits()
    ptr.setsize(image.sizeInBytes())
    return Image.frombytes("RGBA", (width, height), bytes(ptr), "raw", "RGBA")
