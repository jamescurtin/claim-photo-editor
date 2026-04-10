"""Image loading utilities with format fallback support."""

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def _pillow_to_qimage(path: Path) -> QImage:
    """Load an image via Pillow and convert to QImage (thread-safe)."""
    with Image.open(path) as img:
        has_alpha = img.mode in ("RGBA", "LA", "PA")
        mode = "RGBA" if has_alpha else "RGB"
        converted = img.convert(mode)
        bpp = 4 if has_alpha else 3
        fmt = QImage.Format.Format_RGBA8888 if has_alpha else QImage.Format.Format_RGB888
        data = converted.tobytes("raw", mode)
        qimage = QImage(data, converted.width, converted.height, bpp * converted.width, fmt)
        # QImage doesn't copy the data buffer, so copy before `data` goes out of scope
        return qimage.copy()


def load_qimage(path: Path) -> QImage:
    """
    Load an image as QImage, falling back to Pillow for formats Qt cannot handle.

    Thread-safe — can be called from any thread.

    Args:
        path: Path to the image file.

    Returns:
        QImage of the loaded image. May be null if both loaders fail.
    """
    image = QImage(str(path))
    if not image.isNull():
        return image

    try:
        return _pillow_to_qimage(path)
    except Exception:
        return QImage()


def load_pixmap(path: Path) -> QPixmap:
    """
    Load an image as QPixmap, falling back to Pillow for formats Qt cannot handle.

    Only safe to call from the main/GUI thread (QPixmap is not thread-safe).

    Args:
        path: Path to the image file.

    Returns:
        QPixmap of the loaded image. May be null if both loaders fail.
    """
    pixmap = QPixmap(str(path))
    if not pixmap.isNull():
        return pixmap

    try:
        return QPixmap.fromImage(_pillow_to_qimage(path))
    except Exception:
        return QPixmap()
