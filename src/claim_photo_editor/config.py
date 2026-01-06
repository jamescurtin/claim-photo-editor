"""Configuration and settings management."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from claim_photo_editor import __app_name__, __author__


class Orientation(Enum):
    """Page orientation for PDF generation."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ImageQuality(Enum):
    """Image quality presets for PDF generation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class PDFSettings:
    """Settings for PDF generation."""

    rows: int = 2
    columns: int = 2
    orientation: Orientation = Orientation.LANDSCAPE
    margin_top: float = 0.25
    margin_bottom: float = 0.25
    margin_left: float = 0.25
    margin_right: float = 0.25
    font_family: str = "Helvetica"  # ReportLab uses Helvetica as Arial equivalent
    dpi: int = 75
    image_quality: ImageQuality = ImageQuality.MEDIUM


class Config:
    """Application configuration manager using QSettings."""

    # Legacy key (for migration from old single-directory setting)
    PHOTOS_DIR_KEY = "photos_directory"
    # Separate directory keys
    NEW_PHOTOS_DIR_KEY = "directories/new_photos"
    COMPLETED_PHOTOS_DIR_KEY = "directories/completed_photos"
    # PDF settings keys
    PDF_ROWS_KEY = "pdf/rows"
    PDF_COLUMNS_KEY = "pdf/columns"
    PDF_ORIENTATION_KEY = "pdf/orientation"
    PDF_MARGIN_TOP_KEY = "pdf/margin_top"
    PDF_MARGIN_BOTTOM_KEY = "pdf/margin_bottom"
    PDF_MARGIN_LEFT_KEY = "pdf/margin_left"
    PDF_MARGIN_RIGHT_KEY = "pdf/margin_right"
    PDF_FONT_KEY = "pdf/font"
    PDF_DPI_KEY = "pdf/dpi"
    PDF_QUALITY_KEY = "pdf/quality"
    # Cache settings keys
    CACHE_MAX_SIZE_KEY = "cache/max_size_mb"
    DEFAULT_CACHE_SIZE_MB = 2048  # 2GB default

    def __init__(self) -> None:
        """Initialize configuration with QSettings."""
        self._settings = QSettings(__author__.lower().replace(" ", ""), __app_name__)
        self._migrate_legacy_settings()

    def _migrate_legacy_settings(self) -> None:
        """Migrate from old single-directory setting to new separate directories."""
        legacy_dir = self._get(self.PHOTOS_DIR_KEY)
        if legacy_dir and not self._get(self.NEW_PHOTOS_DIR_KEY):
            # Migrate to new format
            old_path = Path(legacy_dir)
            estimate_dir = old_path / "Estimate Photos"
            completed_dir = old_path / "Completed Estimate Photos"

            if estimate_dir.exists():
                self._set(self.NEW_PHOTOS_DIR_KEY, str(estimate_dir))
            if completed_dir.exists():
                self._set(self.COMPLETED_PHOTOS_DIR_KEY, str(completed_dir))

            # Remove legacy key
            self._settings.remove(self.PHOTOS_DIR_KEY)
            self.sync()

    def _get(self, key: str, default: Any = None) -> Any:
        """Get a value from settings."""
        return self._settings.value(key, default)

    def _set(self, key: str, value: Any) -> None:
        """Set a value in settings."""
        self._settings.setValue(key, value)

    @property
    def new_photos_dir(self) -> Path | None:
        """Get the New Photos directory."""
        value = self._get(self.NEW_PHOTOS_DIR_KEY)
        if value:
            return Path(value)
        return None

    @new_photos_dir.setter
    def new_photos_dir(self, path: Path | None) -> None:
        """Set the New Photos directory."""
        if path is None:
            self._settings.remove(self.NEW_PHOTOS_DIR_KEY)
        else:
            self._set(self.NEW_PHOTOS_DIR_KEY, str(path))

    @property
    def completed_photos_dir(self) -> Path | None:
        """Get the Completed Photos directory."""
        value = self._get(self.COMPLETED_PHOTOS_DIR_KEY)
        if value:
            return Path(value)
        return None

    @completed_photos_dir.setter
    def completed_photos_dir(self, path: Path | None) -> None:
        """Set the Completed Photos directory."""
        if path is None:
            self._settings.remove(self.COMPLETED_PHOTOS_DIR_KEY)
        else:
            self._set(self.COMPLETED_PHOTOS_DIR_KEY, str(path))

    # Legacy property aliases for backward compatibility
    @property
    def photos_directory(self) -> Path | None:
        """Legacy: Get the configured photos directory (returns new_photos_dir parent)."""
        new_dir = self.new_photos_dir
        if new_dir:
            return new_dir.parent
        return None

    @photos_directory.setter
    def photos_directory(self, path: Path | None) -> None:
        """Legacy: Set the photos directory (creates subdirectories)."""
        if path is None:
            self.new_photos_dir = None
            self.completed_photos_dir = None
        else:
            self.new_photos_dir = path / "Estimate Photos"
            self.completed_photos_dir = path / "Completed Estimate Photos"

    @property
    def estimate_photos_dir(self) -> Path | None:
        """Alias for new_photos_dir for backward compatibility."""
        return self.new_photos_dir

    def is_configured(self) -> bool:
        """Check if both directories are configured."""
        return self.new_photos_dir is not None and self.completed_photos_dir is not None

    def get_pdf_settings(self) -> PDFSettings:
        """Get all PDF settings as a dataclass."""
        orientation_val = self._get(self.PDF_ORIENTATION_KEY, Orientation.LANDSCAPE.value)
        quality_val = self._get(self.PDF_QUALITY_KEY, ImageQuality.MEDIUM.value)
        return PDFSettings(
            rows=int(self._get(self.PDF_ROWS_KEY, 2)),
            columns=int(self._get(self.PDF_COLUMNS_KEY, 2)),
            orientation=Orientation(orientation_val),
            margin_top=float(self._get(self.PDF_MARGIN_TOP_KEY, 0.25)),
            margin_bottom=float(self._get(self.PDF_MARGIN_BOTTOM_KEY, 0.25)),
            margin_left=float(self._get(self.PDF_MARGIN_LEFT_KEY, 0.25)),
            margin_right=float(self._get(self.PDF_MARGIN_RIGHT_KEY, 0.25)),
            font_family=str(self._get(self.PDF_FONT_KEY, "Helvetica")),
            dpi=int(self._get(self.PDF_DPI_KEY, 75)),
            image_quality=ImageQuality(quality_val),
        )

    def set_pdf_settings(self, settings: PDFSettings) -> None:
        """Save PDF settings."""
        self._set(self.PDF_ROWS_KEY, settings.rows)
        self._set(self.PDF_COLUMNS_KEY, settings.columns)
        self._set(self.PDF_ORIENTATION_KEY, settings.orientation.value)
        self._set(self.PDF_MARGIN_TOP_KEY, settings.margin_top)
        self._set(self.PDF_MARGIN_BOTTOM_KEY, settings.margin_bottom)
        self._set(self.PDF_MARGIN_LEFT_KEY, settings.margin_left)
        self._set(self.PDF_MARGIN_RIGHT_KEY, settings.margin_right)
        self._set(self.PDF_FONT_KEY, settings.font_family)
        self._set(self.PDF_DPI_KEY, settings.dpi)
        self._set(self.PDF_QUALITY_KEY, settings.image_quality.value)

    @property
    def cache_max_size_mb(self) -> int:
        """Get the maximum cache size in MB."""
        return int(self._get(self.CACHE_MAX_SIZE_KEY, self.DEFAULT_CACHE_SIZE_MB))

    @cache_max_size_mb.setter
    def cache_max_size_mb(self, value: int) -> None:
        """Set the maximum cache size in MB."""
        self._set(self.CACHE_MAX_SIZE_KEY, value)

    def sync(self) -> None:
        """Force sync settings to disk."""
        self._settings.sync()
