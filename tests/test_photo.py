"""Tests for Photo model."""

import os
from pathlib import Path

import pytest
from PIL import Image, ImageCms
from PIL.ExifTags import IFD, Base

from claim_photo_editor.models.photo import Photo
from claim_photo_editor.utils.exif import ORIGINALS_DIR_NAME, get_caption, set_caption


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


class TestHeifConversion:
    """HEIC/HEIF photos are converted to JPEG once, on the first caption save."""

    @pytest.fixture
    def iphone_heic(self, temp_dir: Path) -> Path:
        """Create a HEIC with an ICC profile, a timestamp and a rotation."""
        path = temp_dir / "IMG_0001.HEIC"
        exif = Image.Exif()
        exif[Base.Orientation] = 6
        exif.get_ifd(IFD.Exif)[Base.DateTimeOriginal] = "2024:06:15 14:30:00"
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        Image.new("RGB", (200, 100), color=(100, 150, 200)).save(
            path, "HEIF", exif=exif.tobytes(), icc_profile=icc
        )
        os.utime(path, (1_700_000_000, 1_700_000_000))
        return path

    def test_converts_to_jpeg(self, iphone_heic: Path) -> None:
        """Test that the caption lands in a new JPEG and the original is set aside."""
        photo = Photo(path=iphone_heic)
        expected_size = photo.dimensions
        expected_timestamp = photo.timestamp

        photo.caption = "Water damage"

        assert photo.path == iphone_heic.with_name("IMG_0001.jpg")
        assert get_caption(photo.path) == "Water damage"
        assert not iphone_heic.exists()
        assert (iphone_heic.parent / ORIGINALS_DIR_NAME / "IMG_0001.HEIC").exists()

        with Image.open(photo.path) as img:
            assert img.format == "JPEG"
            assert img.size == expected_size
            assert img.getexif()[Base.Orientation] == 1
            assert img.info.get("icc_profile")
        assert photo.path.stat().st_mtime == 1_700_000_000

        photo.reload()
        assert photo.timestamp == expected_timestamp
        assert photo.caption == "Water damage"

    def test_later_edits_are_lossless(self, iphone_heic: Path) -> None:
        """Test that edits after the conversion do not touch the JPEG pixels."""
        photo = Photo(path=iphone_heic)
        photo.caption = "First"
        with Image.open(photo.path) as img:
            pixels = img.tobytes()

        photo.caption = "Second"

        assert get_caption(photo.path) == "Second"
        with Image.open(photo.path) as img:
            assert img.tobytes() == pixels

    def test_original_hidden_from_directory(self, iphone_heic: Path) -> None:
        """Test that the folder lists the converted photo once."""
        Photo(path=iphone_heic).caption = "Caption"

        photos = Photo.from_directory(iphone_heic.parent)

        assert [p.name for p in photos] == ["IMG_0001.jpg"]

    def test_name_collision(self, iphone_heic: Path) -> None:
        """Test that an existing JPEG with the same name (any case) is not overwritten."""
        existing = iphone_heic.with_name("IMG_0001.JPG")
        Image.new("RGB", (10, 10)).save(existing, "JPEG")
        existing_bytes = existing.read_bytes()

        photo = Photo(path=iphone_heic)
        photo.caption = "Caption"

        assert photo.path.name == "IMG_0001-1.jpg"
        assert existing.read_bytes() == existing_bytes

    def test_failed_conversion_raises_oserror(
        self, iphone_heic: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a failed conversion keeps the HEIC in place."""
        original = iphone_heic.read_bytes()

        def fail_replace(*_args: object) -> None:
            raise OSError("simulated crash")

        monkeypatch.setattr(os, "replace", fail_replace)
        photo = Photo(path=iphone_heic)

        with pytest.raises(OSError, match="Failed to convert"):
            photo.caption = "Caption"

        assert photo.path == iphone_heic
        assert iphone_heic.read_bytes() == original
        assert sorted(p.name for p in iphone_heic.parent.iterdir()) == [iphone_heic.name]


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
