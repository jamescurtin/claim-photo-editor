"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image
from PIL.ExifTags import IFD, Base
from PySide6.QtCore import QSettings

from claim_photo_editor.config import Config


def _make_test_image(
    temp_dir: Path,
    name: str,
    fmt: str,
    size: tuple[int, int] = (800, 600),
    color: tuple[int, int, int] = (100, 150, 200),
    **save_kwargs: object,
) -> Path:
    """Create a test image file."""
    img_path = temp_dir / name
    img = Image.new("RGB", size, color=color)
    img.save(img_path, fmt, **save_kwargs)
    return img_path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_image(temp_dir: Path) -> Path:
    """Create a sample JPEG image for testing."""
    return _make_test_image(temp_dir, "test_image.jpg", "JPEG", quality=95)


@pytest.fixture
def sample_image_with_exif(temp_dir: Path) -> Path:
    """Create a sample JPEG image with EXIF data."""
    img_path = temp_dir / "test_image_exif.jpg"

    img = Image.new("RGB", (800, 600), color=(100, 150, 200))

    exif = img.getexif()
    exif[Base.Make] = "Test Camera"
    exif[Base.Model] = "Test Model"
    exif[Base.Orientation] = 1

    exif_ifd = exif.get_ifd(IFD.Exif)
    exif_ifd[Base.DateTimeOriginal] = "2024:01:15 10:30:00"
    exif_ifd[Base.DateTimeDigitized] = "2024:01:15 10:30:00"

    img.save(img_path, "JPEG", quality=95, exif=exif.tobytes())

    return img_path


@pytest.fixture
def portrait_image(temp_dir: Path) -> Path:
    """Create a portrait-oriented test image."""
    return _make_test_image(
        temp_dir, "portrait_image.jpg", "JPEG", size=(600, 800), color=(200, 150, 100), quality=95
    )


@pytest.fixture
def landscape_image(temp_dir: Path) -> Path:
    """Create a landscape-oriented test image."""
    return _make_test_image(
        temp_dir, "landscape_image.jpg", "JPEG", size=(800, 600), color=(100, 200, 150), quality=95
    )


@pytest.fixture
def sample_heic_image(temp_dir: Path) -> Path:
    """Create a sample HEIC image for testing."""
    return _make_test_image(temp_dir, "test_image.heic", "HEIF")


@pytest.fixture
def sample_webp_image(temp_dir: Path) -> Path:
    """Create a sample WebP image for testing."""
    return _make_test_image(temp_dir, "test_image.webp", "WEBP", quality=95)


@pytest.fixture
def sample_png_image(temp_dir: Path) -> Path:
    """Create a sample PNG image for testing."""
    return _make_test_image(temp_dir, "test_image.png", "PNG")


@pytest.fixture
def sample_tiff_image(temp_dir: Path) -> Path:
    """Create a sample TIFF image for testing."""
    return _make_test_image(temp_dir, "test_image.tiff", "TIFF")


@pytest.fixture
def photo_directory(temp_dir: Path) -> Path:
    """Create a directory structure with photos."""
    estimate_dir = temp_dir / "Estimate Photos"
    estimate_dir.mkdir()

    completed_dir = temp_dir / "Completed Estimate Photos"
    completed_dir.mkdir()

    folder1 = estimate_dir / "TestFolder1"
    folder1.mkdir()

    for i in range(3):
        _make_test_image(
            folder1, f"photo_{i + 1}.jpg", "JPEG", color=(100 + i * 50, 150, 200), quality=95
        )

    folder2 = estimate_dir / "TestFolder2"
    folder2.mkdir()
    _make_test_image(folder2, "photo_a.jpg", "JPEG", color=(150, 100, 200), quality=95)

    return temp_dir


@pytest.fixture
def mock_config(temp_dir: Path) -> Config:
    """Create a mock config with temp directory."""
    settings = QSettings(str(temp_dir / "test_settings.ini"), QSettings.Format.IniFormat)

    config = Config()
    config._settings = settings
    config.photos_directory = temp_dir

    return config
