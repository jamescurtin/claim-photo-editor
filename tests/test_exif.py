"""Tests for EXIF utilities."""

from datetime import datetime
from pathlib import Path

from PIL import Image

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
