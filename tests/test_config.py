"""Tests for configuration module."""

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from claim_photo_editor.config import Config, ImageQuality, Orientation, PDFSettings


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create a config instance with temporary settings."""
    settings_file = tmp_path / "test_settings.ini"
    settings = QSettings(str(settings_file), QSettings.Format.IniFormat)

    config = Config()
    config._settings = settings
    return config


class TestConfig:
    """Tests for Config class."""

    def test_photos_directory_none_by_default(self, test_config: Config) -> None:
        """Test photos_directory is None when not set."""
        assert test_config.photos_directory is None

    def test_set_photos_directory(self, test_config: Config, tmp_path: Path) -> None:
        """Test setting photos directory."""
        test_config.photos_directory = tmp_path
        assert test_config.photos_directory == tmp_path

    def test_clear_photos_directory(self, test_config: Config, tmp_path: Path) -> None:
        """Test clearing photos directory."""
        test_config.photos_directory = tmp_path
        test_config.photos_directory = None
        assert test_config.photos_directory is None

    def test_estimate_photos_dir(self, test_config: Config, tmp_path: Path) -> None:
        """Test getting estimate photos directory."""
        test_config.photos_directory = tmp_path
        assert test_config.estimate_photos_dir == tmp_path / "Estimate Photos"

    def test_completed_photos_dir(self, test_config: Config, tmp_path: Path) -> None:
        """Test getting completed photos directory."""
        test_config.photos_directory = tmp_path
        assert test_config.completed_photos_dir == tmp_path / "Completed Estimate Photos"

    def test_estimate_photos_dir_none_without_base(self, test_config: Config) -> None:
        """Test estimate_photos_dir is None when no base set."""
        assert test_config.estimate_photos_dir is None
        assert test_config.completed_photos_dir is None


class TestPDFSettings:
    """Tests for PDFSettings dataclass."""

    def test_default_values(self) -> None:
        """Test default PDFSettings values."""
        settings = PDFSettings()

        assert settings.rows == 2
        assert settings.columns == 2
        assert settings.orientation == Orientation.LANDSCAPE
        assert settings.margin_top == 0.25
        assert settings.margin_bottom == 0.25
        assert settings.margin_left == 0.25
        assert settings.margin_right == 0.25
        assert settings.font_family == "Helvetica"
        assert settings.dpi == 75
        assert settings.image_quality == ImageQuality.MEDIUM

    def test_custom_values(self) -> None:
        """Test creating PDFSettings with custom values."""
        settings = PDFSettings(
            rows=3,
            columns=4,
            orientation=Orientation.PORTRAIT,
            dpi=150,
        )

        assert settings.rows == 3
        assert settings.columns == 4
        assert settings.orientation == Orientation.PORTRAIT
        assert settings.dpi == 150


class TestConfigPDFSettings:
    """Tests for PDF settings persistence."""

    def test_get_default_pdf_settings(self, test_config: Config) -> None:
        """Test getting default PDF settings."""
        settings = test_config.get_pdf_settings()

        assert settings.rows == 2
        assert settings.columns == 2
        assert settings.orientation == Orientation.LANDSCAPE

    def test_set_pdf_settings(self, test_config: Config) -> None:
        """Test saving PDF settings."""
        new_settings = PDFSettings(
            rows=3,
            columns=3,
            orientation=Orientation.PORTRAIT,
            margin_top=0.5,
            margin_bottom=0.5,
            margin_left=0.5,
            margin_right=0.5,
            font_family="Courier",
            dpi=150,
            image_quality=ImageQuality.HIGH,
        )

        test_config.set_pdf_settings(new_settings)

        # Retrieve and verify
        loaded = test_config.get_pdf_settings()
        assert loaded.rows == 3
        assert loaded.columns == 3
        assert loaded.orientation == Orientation.PORTRAIT
        assert loaded.margin_top == 0.5
        assert loaded.font_family == "Courier"
        assert loaded.dpi == 150
        assert loaded.image_quality == ImageQuality.HIGH

    def test_sync(self, test_config: Config) -> None:
        """Test syncing settings to disk."""
        test_config.photos_directory = Path("/test/path")
        test_config.sync()  # Should not raise


class TestOrientation:
    """Tests for Orientation enum."""

    def test_values(self) -> None:
        """Test Orientation enum values."""
        assert Orientation.PORTRAIT.value == "portrait"
        assert Orientation.LANDSCAPE.value == "landscape"


class TestImageQuality:
    """Tests for ImageQuality enum."""

    def test_values(self) -> None:
        """Test ImageQuality enum values."""
        assert ImageQuality.LOW.value == "low"
        assert ImageQuality.MEDIUM.value == "medium"
        assert ImageQuality.HIGH.value == "high"
