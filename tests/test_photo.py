"""Tests for Photo model."""

from pathlib import Path

import pytest

from claim_photo_editor.models.photo import Photo
from claim_photo_editor.utils.exif import set_caption


class TestPhotoInit:
    """Tests for Photo initialization."""

    def test_init_valid_image(self, sample_image: Path) -> None:
        """Test creating Photo from valid image."""
        photo = Photo(path=sample_image)
        assert photo.path == sample_image
        assert photo.name == sample_image.name

    def test_init_nonexistent_file(self, temp_dir: Path) -> None:
        """Test creating Photo from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Photo(path=temp_dir / "nonexistent.jpg")

    def test_init_unsupported_format(self, temp_dir: Path) -> None:
        """Test creating Photo from unsupported format."""
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("not an image")

        with pytest.raises(ValueError, match="Unsupported image format"):
            Photo(path=txt_file)


class TestPhotoProperties:
    """Tests for Photo properties."""

    def test_name(self, sample_image: Path) -> None:
        """Test getting photo name."""
        photo = Photo(path=sample_image)
        assert photo.name == "test_image.jpg"

    def test_caption_none(self, sample_image: Path) -> None:
        """Test caption is None when not set."""
        photo = Photo(path=sample_image)
        assert photo.caption is None

    def test_has_caption_false(self, sample_image: Path) -> None:
        """Test has_caption is False when no caption."""
        photo = Photo(path=sample_image)
        assert photo.has_caption is False

    def test_has_caption_true(self, sample_image: Path) -> None:
        """Test has_caption is True when caption exists."""
        set_caption(sample_image, "Test caption")
        photo = Photo(path=sample_image)
        assert photo.has_caption is True

    def test_timestamp(self, sample_image_with_exif: Path) -> None:
        """Test getting timestamp."""
        photo = Photo(path=sample_image_with_exif)
        assert photo.timestamp is not None
        assert photo.timestamp.year == 2024

    def test_timestamp_str(self, sample_image_with_exif: Path) -> None:
        """Test getting formatted timestamp string."""
        photo = Photo(path=sample_image_with_exif)
        assert "2024-01-15" in photo.timestamp_str

    def test_dimensions(self, sample_image: Path) -> None:
        """Test getting dimensions."""
        photo = Photo(path=sample_image)
        assert photo.width == 800
        assert photo.height == 600

    def test_is_landscape(self, landscape_image: Path, portrait_image: Path) -> None:
        """Test landscape detection."""
        landscape_photo = Photo(path=landscape_image)
        portrait_photo = Photo(path=portrait_image)

        assert landscape_photo.is_landscape_orientation is True
        assert portrait_photo.is_landscape_orientation is False


class TestPhotoCaptionSetter:
    """Tests for setting captions."""

    def test_set_caption(self, sample_image: Path) -> None:
        """Test setting a caption."""
        photo = Photo(path=sample_image)
        photo.caption = "New caption"

        # Reload and verify
        photo.reload()
        assert photo.caption == "New caption"

    def test_set_caption_none(self, sample_image: Path) -> None:
        """Test setting caption to None."""
        set_caption(sample_image, "Initial caption")
        photo = Photo(path=sample_image)

        photo.caption = None
        photo.reload()
        # Empty string or None after clearing
        assert not photo.caption or photo.caption == ""


class TestPhotoFromDirectory:
    """Tests for loading photos from directory."""

    def test_from_directory(self, photo_directory: Path) -> None:
        """Test loading photos from directory."""
        folder = photo_directory / "Estimate Photos" / "TestFolder1"
        photos = Photo.from_directory(folder)

        assert len(photos) == 3
        assert all(isinstance(p, Photo) for p in photos)

    def test_from_directory_empty(self, temp_dir: Path) -> None:
        """Test loading from empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        photos = Photo.from_directory(empty_dir)
        assert photos == []

    def test_from_directory_nonexistent(self, temp_dir: Path) -> None:
        """Test loading from non-existent directory."""
        photos = Photo.from_directory(temp_dir / "nonexistent")
        assert photos == []

    def test_from_directory_sorted(self, photo_directory: Path) -> None:
        """Test photos are sorted by name."""
        folder = photo_directory / "Estimate Photos" / "TestFolder1"
        photos = Photo.from_directory(folder)

        names = [p.name for p in photos]
        assert names == sorted(names)


class TestPhotoEquality:
    """Tests for Photo equality and hashing."""

    def test_equality(self, sample_image: Path) -> None:
        """Test two Photos with same path are equal."""
        photo1 = Photo(path=sample_image)
        photo2 = Photo(path=sample_image)

        assert photo1 == photo2

    def test_inequality(self, sample_image: Path, portrait_image: Path) -> None:
        """Test two Photos with different paths are not equal."""
        photo1 = Photo(path=sample_image)
        photo2 = Photo(path=portrait_image)

        assert photo1 != photo2

    def test_hash(self, sample_image: Path) -> None:
        """Test Photo can be used in sets."""
        photo1 = Photo(path=sample_image)
        photo2 = Photo(path=sample_image)

        photo_set = {photo1, photo2}
        assert len(photo_set) == 1
