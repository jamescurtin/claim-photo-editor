"""Tests for EXIF utilities."""

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from PIL.ExifTags import IFD, Base

from claim_photo_editor.utils.exif import (
    get_caption,
    get_image_dimensions,
    get_timestamp,
    is_landscape,
    set_caption,
)


class TestGetCaption:
    """Tests for get_caption function."""

    def test_no_caption(self, sample_image: Path) -> None:
        """Test getting caption from image without one."""
        caption = get_caption(sample_image)
        assert caption is None

    def test_get_after_set(self, sample_image: Path) -> None:
        """Test getting caption after setting it."""
        test_caption = "Test caption"
        set_caption(sample_image, test_caption)

        caption = get_caption(sample_image)
        assert caption == test_caption

    def test_invalid_file(self, temp_dir: Path) -> None:
        """Test getting caption from non-existent file."""
        caption = get_caption(temp_dir / "nonexistent.jpg")
        assert caption is None


class TestSetCaption:
    """Tests for set_caption function."""

    def test_set_caption(self, sample_image: Path) -> None:
        """Test setting a caption."""
        result = set_caption(sample_image, "My test caption")
        assert result is True

        # Verify it was saved
        caption = get_caption(sample_image)
        assert caption == "My test caption"

    def test_set_empty_caption(self, sample_image: Path) -> None:
        """Test setting an empty caption."""
        # First set a caption
        set_caption(sample_image, "Initial caption")

        # Then clear it
        result = set_caption(sample_image, "")
        assert result is True

        caption = get_caption(sample_image)
        assert caption is None or caption == ""

    def test_set_caption_with_special_chars(self, sample_image: Path) -> None:
        """Test setting caption with special characters."""
        test_caption = "Caption with special chars: @#$%"
        result = set_caption(sample_image, test_caption)
        assert result is True

        # Special chars may be replaced in ASCII encoding
        caption = get_caption(sample_image)
        assert caption is not None

    def test_set_caption_preserves_image(self, sample_image: Path) -> None:
        """Test that setting caption doesn't corrupt the image."""
        # Get original size
        with Image.open(sample_image) as img:
            original_size = img.size

        set_caption(sample_image, "Test caption")

        # Verify image is still valid
        with Image.open(sample_image) as img:
            assert img.size == original_size


class TestGetTimestamp:
    """Tests for get_timestamp function."""

    def test_no_timestamp(self, sample_image: Path) -> None:
        """Test getting timestamp from image without EXIF date."""
        # Should fall back to file modification time
        timestamp = get_timestamp(sample_image)
        assert timestamp is not None
        assert isinstance(timestamp, datetime)

    def test_with_exif_timestamp(self, sample_image_with_exif: Path) -> None:
        """Test getting timestamp from image with EXIF date."""
        timestamp = get_timestamp(sample_image_with_exif)
        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15

    def test_invalid_file(self, temp_dir: Path) -> None:
        """Test getting timestamp from non-existent file."""
        timestamp = get_timestamp(temp_dir / "nonexistent.jpg")
        assert timestamp is None


class TestGetImageDimensions:
    """Tests for get_image_dimensions function."""

    def test_landscape_dimensions(self, landscape_image: Path) -> None:
        """Test getting dimensions of landscape image."""
        width, height = get_image_dimensions(landscape_image)
        assert width == 800
        assert height == 600

    def test_portrait_dimensions(self, portrait_image: Path) -> None:
        """Test getting dimensions of portrait image."""
        width, height = get_image_dimensions(portrait_image)
        assert width == 600
        assert height == 800


class TestIsLandscape:
    """Tests for is_landscape function."""

    def test_landscape_image(self, landscape_image: Path) -> None:
        """Test detecting landscape orientation."""
        assert is_landscape(landscape_image) is True

    def test_portrait_image(self, portrait_image: Path) -> None:
        """Test detecting portrait orientation."""
        assert is_landscape(portrait_image) is False


class TestCaptionRoundtripFormats:
    """Test caption read/write roundtrip for all supported formats."""

    def test_jpeg_roundtrip(self, sample_image: Path) -> None:
        """Test caption roundtrip for JPEG format."""
        assert set_caption(sample_image, "JPEG caption") is True
        assert get_caption(sample_image) == "JPEG caption"

    def test_heic_roundtrip(self, sample_heic_image: Path) -> None:
        """Test caption roundtrip for HEIC format."""
        assert set_caption(sample_heic_image, "HEIC caption") is True
        assert get_caption(sample_heic_image) == "HEIC caption"

    def test_webp_roundtrip(self, sample_webp_image: Path) -> None:
        """Test caption roundtrip for WebP format."""
        assert set_caption(sample_webp_image, "WebP caption") is True
        assert get_caption(sample_webp_image) == "WebP caption"

    def test_png_roundtrip(self, sample_png_image: Path) -> None:
        """Test caption roundtrip for PNG format."""
        assert set_caption(sample_png_image, "PNG caption") is True
        assert get_caption(sample_png_image) == "PNG caption"

    def test_tiff_roundtrip(self, sample_tiff_image: Path) -> None:
        """Test caption roundtrip for TIFF format."""
        assert set_caption(sample_tiff_image, "TIFF caption") is True
        assert get_caption(sample_tiff_image) == "TIFF caption"

    def test_heic_preserves_image(self, sample_heic_image: Path) -> None:
        """Test that setting caption on HEIC doesn't corrupt the image."""
        with Image.open(sample_heic_image) as img:
            original_size = img.size

        set_caption(sample_heic_image, "Test caption")

        with Image.open(sample_heic_image) as img:
            assert img.size == original_size

    def test_webp_preserves_image(self, sample_webp_image: Path) -> None:
        """Test that setting caption on WebP doesn't corrupt the image."""
        with Image.open(sample_webp_image) as img:
            original_size = img.size

        set_caption(sample_webp_image, "Test caption")

        with Image.open(sample_webp_image) as img:
            assert img.size == original_size


class TestTimestampFormats:
    """Test timestamp reading across formats."""

    @pytest.fixture
    def heic_with_exif(self, temp_dir: Path) -> Path:
        """Create a HEIC image with EXIF timestamp."""
        img_path = temp_dir / "exif_test.heic"
        img = Image.new("RGB", (100, 100), color=(100, 150, 200))
        exif = img.getexif()
        exif_ifd = exif.get_ifd(IFD.Exif)
        exif_ifd[Base.DateTimeOriginal] = "2024:06:15 14:30:00"
        img.save(img_path, "HEIF", exif=exif.tobytes())
        return img_path

    def test_heic_timestamp(self, heic_with_exif: Path) -> None:
        """Test reading timestamp from HEIC file."""
        timestamp = get_timestamp(heic_with_exif)
        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 6
        assert timestamp.day == 15

    def test_webp_fallback_timestamp(self, sample_webp_image: Path) -> None:
        """Test WebP falls back to file modification time."""
        timestamp = get_timestamp(sample_webp_image)
        assert timestamp is not None
        assert isinstance(timestamp, datetime)

    def test_heic_dimensions(self, sample_heic_image: Path) -> None:
        """Test reading dimensions from HEIC file."""
        width, height = get_image_dimensions(sample_heic_image)
        assert width == 800
        assert height == 600
