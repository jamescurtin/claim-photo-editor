"""Tests for EXIF utilities."""

import os
import struct
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image, ImageCms
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

    def test_heic_refused(self, sample_heic_image: Path) -> None:
        """Test that HEIC is never written in place (it is converted to JPEG instead)."""
        original = sample_heic_image.read_bytes()
        assert set_caption(sample_heic_image, "HEIC caption") is False
        assert sample_heic_image.read_bytes() == original

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


def _decoded(path: Path) -> tuple[str, tuple[int, int], bytes]:
    """Return the decoded pixel data of an image."""
    with Image.open(path) as img:
        return img.mode, img.size, img.tobytes()


def _jpeg_scan_data(path: Path) -> bytes:
    """Return the bytes of a JPEG from the first SOS marker to the end of file."""
    data = path.read_bytes()
    pos = 2
    while data[pos + 1] != 0xDA:
        pos += 2 + struct.unpack(">H", data[pos + 2 : pos + 4])[0]
    return data[pos:]


def _make_photo_like(temp_dir: Path, name: str, fmt: str, **save_kwargs: object) -> Path:
    """Create a noisy image, where any re-encode would change pixel values."""
    noise = Image.effect_noise((320, 240), 40)
    gradient = Image.linear_gradient("L").resize((320, 240))
    img = Image.merge("RGB", (noise, gradient, noise.transpose(Image.Transpose.FLIP_LEFT_RIGHT)))
    if save_kwargs.pop("alpha", False):
        img.putalpha(gradient)
    path = temp_dir / name
    img.save(path, fmt, **save_kwargs)
    return path


class TestLosslessCaptionWrites:
    """Caption saves must change only metadata, never the image data."""

    @pytest.mark.parametrize(
        ("name", "fmt", "save_kwargs"),
        [
            ("photo.jpg", "JPEG", {"quality": 90}),
            ("progressive.jpg", "JPEG", {"quality": 90, "progressive": True}),
            ("photo.png", "PNG", {}),
            ("lossy.webp", "WEBP", {"quality": 80}),
            ("lossless.webp", "WEBP", {"lossless": True}),
            ("alpha.webp", "WEBP", {"quality": 80, "alpha": True}),
            ("lossless_alpha.webp", "WEBP", {"lossless": True, "alpha": True}),
            ("photo.tiff", "TIFF", {}),
            ("lzw.tiff", "TIFF", {"compression": "tiff_lzw"}),
        ],
    )
    def test_repeated_saves_keep_pixels(
        self, temp_dir: Path, name: str, fmt: str, save_kwargs: dict[str, object]
    ) -> None:
        """Test that many caption saves leave the decoded pixels exactly unchanged."""
        path = _make_photo_like(temp_dir, name, fmt, **save_kwargs)
        original = _decoded(path)

        for i in range(10):
            assert set_caption(path, f"Caption {i}") is True

        assert get_caption(path) == "Caption 9"
        assert _decoded(path) == original

    def test_webp_with_exif_replaced(self, temp_dir: Path) -> None:
        """Test that an existing WebP EXIF chunk is replaced, not duplicated."""
        exif = Image.Exif()
        exif[Base.Make] = "Phone"
        path = _make_photo_like(temp_dir, "exif.webp", "WEBP", quality=80, exif=exif.tobytes())

        assert set_caption(path, "First") is True
        assert set_caption(path, "Second") is True

        assert path.read_bytes().count(b"EXIF") == 1
        assert get_caption(path) == "Second"
        with Image.open(path) as img:
            assert img.getexif()[Base.Make] == "Phone"

    def test_jpeg_keeps_scan_data_and_metadata(self, temp_dir: Path) -> None:
        """Test that JPEG image data, ICC profile and XMP are kept byte for byte."""
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/">test</x:xmpmeta>'
        exif = Image.Exif()
        exif[Base.Make] = "Phone"
        path = _make_photo_like(
            temp_dir, "meta.jpg", "JPEG", quality=90, icc_profile=icc, xmp=xmp, exif=exif.tobytes()
        )
        scan = _jpeg_scan_data(path)

        assert set_caption(path, "Kitchen ceiling") is True

        assert _jpeg_scan_data(path) == scan
        with Image.open(path) as img:
            assert img.info["icc_profile"] == icc
            assert img.info["xmp"] == xmp
            assert img.getexif()[Base.Make] == "Phone"
        assert get_caption(path) == "Kitchen ceiling"

    def test_jpeg_without_exif_gets_exif(self, temp_dir: Path) -> None:
        """Test that a JPEG with only a JFIF header gains an EXIF block."""
        path = _make_photo_like(temp_dir, "jfif.jpg", "JPEG", quality=90)
        scan = _jpeg_scan_data(path)

        assert set_caption(path, "Added") is True

        assert _jpeg_scan_data(path) == scan
        assert get_caption(path) == "Added"

    def test_multipage_tiff_refused(self, temp_dir: Path) -> None:
        """Test that a multi-page TIFF is not re-saved (pages would be lost)."""
        path = temp_dir / "pages.tiff"
        Image.new("RGB", (50, 50)).save(
            path, save_all=True, append_images=[Image.new("RGB", (50, 50))]
        )
        original = path.read_bytes()

        assert set_caption(path, "Caption") is False
        assert path.read_bytes() == original


class TestAtomicCaptionWrites:
    """A failed save must leave the original file untouched."""

    def test_failed_replace_keeps_original(
        self, sample_image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that an interrupted replace leaves the original and no temp file."""
        original = sample_image.read_bytes()

        def fail_replace(*_args: object) -> None:
            raise OSError("simulated crash")

        monkeypatch.setattr(os, "replace", fail_replace)

        assert set_caption(sample_image, "Never written") is False
        assert sample_image.read_bytes() == original
        assert sorted(p.name for p in sample_image.parent.iterdir()) == [sample_image.name]

    def test_keeps_file_mode(self, sample_image: Path) -> None:
        """Test that the file permissions survive the replace."""
        sample_image.chmod(0o640)

        assert set_caption(sample_image, "Caption") is True

        assert sample_image.stat().st_mode & 0o777 == 0o640
