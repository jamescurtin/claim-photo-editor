"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path

import piexif
import pytest
from PIL import Image
from PySide6.QtCore import QSettings

from claim_photo_editor.config import Config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_image(temp_dir: Path) -> Path:
    """Create a sample JPEG image for testing."""
    img_path = temp_dir / "test_image.jpg"

    # Create a simple test image
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    img.save(img_path, "JPEG", quality=95)

    return img_path


@pytest.fixture
def sample_image_with_exif(temp_dir: Path) -> Path:
    """Create a sample JPEG image with EXIF data."""
    img_path = temp_dir / "test_image_exif.jpg"

    # Create a simple test image
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))

    # Create EXIF data
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"Test Camera",
            piexif.ImageIFD.Model: b"Test Model",
            piexif.ImageIFD.Orientation: 1,
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: b"2024:01:15 10:30:00",
            piexif.ExifIFD.DateTimeDigitized: b"2024:01:15 10:30:00",
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)

    img.save(img_path, "JPEG", quality=95, exif=exif_bytes)

    return img_path


@pytest.fixture
def portrait_image(temp_dir: Path) -> Path:
    """Create a portrait-oriented test image."""
    img_path = temp_dir / "portrait_image.jpg"

    # Create portrait image (taller than wide)
    img = Image.new("RGB", (600, 800), color=(200, 150, 100))
    img.save(img_path, "JPEG", quality=95)

    return img_path


@pytest.fixture
def landscape_image(temp_dir: Path) -> Path:
    """Create a landscape-oriented test image."""
    img_path = temp_dir / "landscape_image.jpg"

    # Create landscape image (wider than tall)
    img = Image.new("RGB", (800, 600), color=(100, 200, 150))
    img.save(img_path, "JPEG", quality=95)

    return img_path


@pytest.fixture
def photo_directory(temp_dir: Path) -> Path:
    """Create a directory structure with photos."""
    # Create Estimate Photos directory
    estimate_dir = temp_dir / "Estimate Photos"
    estimate_dir.mkdir()

    # Create Completed Estimate Photos directory
    completed_dir = temp_dir / "Completed Estimate Photos"
    completed_dir.mkdir()

    # Create a folder with photos
    folder1 = estimate_dir / "TestFolder1"
    folder1.mkdir()

    # Create sample images
    for i in range(3):
        img = Image.new("RGB", (800, 600), color=(100 + i * 50, 150, 200))
        img.save(folder1 / f"photo_{i + 1}.jpg", "JPEG", quality=95)

    # Create another folder
    folder2 = estimate_dir / "TestFolder2"
    folder2.mkdir()
    img = Image.new("RGB", (800, 600), color=(150, 100, 200))
    img.save(folder2 / "photo_a.jpg", "JPEG", quality=95)

    return temp_dir


@pytest.fixture
def mock_config(temp_dir: Path) -> Config:
    """Create a mock config with temp directory."""
    # Use temporary settings
    settings = QSettings(str(temp_dir / "test_settings.ini"), QSettings.Format.IniFormat)

    config = Config()
    config._settings = settings
    config.photos_directory = temp_dir

    return config
