from PIL import Image, ImageOps
from PyQt6.QtGui import QImage, QPixmap


def load_image(file_path: str) -> Image.Image:
    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)  # EXIF 회전 자동 보정
        return img.copy()


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    img = image.convert("RGBA")
    raw = img.tobytes("raw", "RGBA")
    qimage = QImage(raw, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage)
