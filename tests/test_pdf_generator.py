"""Tests for PDF generator service."""

from pathlib import Path

import pytest
from PIL import Image

from claim_photo_editor.config import ImageQuality, Orientation, PDFSettings
from claim_photo_editor.models.photo import Photo
from claim_photo_editor.services.pdf_generator import PDFGenerator
from claim_photo_editor.utils.exif import set_caption


@pytest.fixture
def pdf_settings() -> PDFSettings:
    """Create default PDF settings for testing."""
    return PDFSettings()


@pytest.fixture
def captioned_photos(temp_dir: Path) -> list[Photo]:
    """Create a list of captioned photos for testing."""
    photos = []
    for i in range(4):
        img_path = temp_dir / f"photo_{i}.jpg"
        img = Image.new("RGB", (800, 600), color=(100 + i * 30, 150, 200))
        img.save(img_path, "JPEG", quality=95)

        set_caption(img_path, f"Caption for photo {i}")
        photos.append(Photo(path=img_path))

    return photos


@pytest.fixture
def mixed_photos(temp_dir: Path) -> list[Photo]:
    """Create a mix of captioned and uncaptioned photos."""
    photos = []
    for i in range(4):
        img_path = temp_dir / f"photo_{i}.jpg"
        img = Image.new("RGB", (800, 600), color=(100 + i * 30, 150, 200))
        img.save(img_path, "JPEG", quality=95)

        # Only caption even-numbered photos
        if i % 2 == 0:
            set_caption(img_path, f"Caption for photo {i}")

        photos.append(Photo(path=img_path))

    return photos


class TestPDFGenerator:
    """Tests for PDFGenerator class."""

    def test_generate_pdf(
        self, pdf_settings: PDFSettings, captioned_photos: list[Photo], temp_dir: Path
    ) -> None:
        """Test generating a PDF."""
        output_path = temp_dir / "output.pdf"

        generator = PDFGenerator(pdf_settings)
        generator.generate(captioned_photos, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_excludes_uncaptioned(
        self, pdf_settings: PDFSettings, mixed_photos: list[Photo], temp_dir: Path
    ) -> None:
        """Test that uncaptioned photos are excluded."""
        output_path = temp_dir / "output.pdf"

        generator = PDFGenerator(pdf_settings)
        generator.generate(mixed_photos, output_path)

        # PDF should be generated with only captioned photos
        assert output_path.exists()

    def test_generate_no_captioned_photos(self, pdf_settings: PDFSettings, temp_dir: Path) -> None:
        """Test error when no captioned photos."""
        # Create uncaptioned photos
        img_path = temp_dir / "uncaptioned.jpg"
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(img_path, "JPEG", quality=95)

        photos = [Photo(path=img_path)]
        output_path = temp_dir / "output.pdf"

        generator = PDFGenerator(pdf_settings)

        with pytest.raises(ValueError, match="No captioned photos"):
            generator.generate(photos, output_path)

    def test_generate_with_portrait_orientation(
        self, captioned_photos: list[Photo], temp_dir: Path
    ) -> None:
        """Test generating PDF in portrait orientation."""
        settings = PDFSettings(orientation=Orientation.PORTRAIT)
        output_path = temp_dir / "portrait.pdf"

        generator = PDFGenerator(settings)
        generator.generate(captioned_photos, output_path)

        assert output_path.exists()

    def test_generate_with_custom_grid(self, captioned_photos: list[Photo], temp_dir: Path) -> None:
        """Test generating PDF with custom grid layout."""
        settings = PDFSettings(rows=1, columns=2)
        output_path = temp_dir / "custom_grid.pdf"

        generator = PDFGenerator(settings)
        generator.generate(captioned_photos, output_path)

        assert output_path.exists()

    def test_generate_with_high_quality(
        self, captioned_photos: list[Photo], temp_dir: Path
    ) -> None:
        """Test generating PDF with high quality images."""
        settings = PDFSettings(dpi=150, image_quality=ImageQuality.HIGH)
        output_path = temp_dir / "high_quality.pdf"

        generator = PDFGenerator(settings)
        generator.generate(captioned_photos, output_path)

        assert output_path.exists()
        # High quality should result in larger file
        assert output_path.stat().st_size > 0

    def test_generate_with_custom_margins(
        self, captioned_photos: list[Photo], temp_dir: Path
    ) -> None:
        """Test generating PDF with custom margins."""
        settings = PDFSettings(
            margin_top=1.0,
            margin_bottom=1.0,
            margin_left=1.0,
            margin_right=1.0,
        )
        output_path = temp_dir / "custom_margins.pdf"

        generator = PDFGenerator(settings)
        generator.generate(captioned_photos, output_path)

        assert output_path.exists()


class TestPDFGeneratorFilename:
    """Tests for PDF filename generation."""

    def test_get_default_filename(self) -> None:
        """Test default filename generation."""
        filename = PDFGenerator.get_default_filename("TestFolder")
        assert filename == "TestFolder Photos.pdf"

    def test_get_default_filename_with_spaces(self) -> None:
        """Test filename generation with spaces in folder name."""
        filename = PDFGenerator.get_default_filename("My Test Folder")
        assert filename == "My Test Folder Photos.pdf"


class TestPDFGeneratorImageQuality:
    """Tests for image quality settings."""

    def test_low_quality_smaller_file(self, captioned_photos: list[Photo], temp_dir: Path) -> None:
        """Test that low quality produces smaller files than high quality."""
        low_quality = PDFSettings(image_quality=ImageQuality.LOW, dpi=75)
        high_quality = PDFSettings(image_quality=ImageQuality.HIGH, dpi=150)

        low_path = temp_dir / "low.pdf"
        high_path = temp_dir / "high.pdf"

        PDFGenerator(low_quality).generate(captioned_photos, low_path)
        PDFGenerator(high_quality).generate(captioned_photos, high_path)

        # Low quality should be smaller
        assert low_path.stat().st_size < high_path.stat().st_size
