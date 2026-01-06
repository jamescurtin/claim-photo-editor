"""Photo model for representing image files with metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from claim_photo_editor.utils.exif import (
    get_caption,
    get_image_dimensions,
    get_timestamp,
    is_landscape,
    set_caption,
)


@dataclass
class Photo:
    """Represents a photo file with its metadata."""

    path: Path
    _caption: str | None = field(default=None, repr=False)
    _timestamp: datetime | None = field(default=None, repr=False)
    _dimensions: tuple[int, int] | None = field(default=None, repr=False)
    _is_landscape: bool | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}

    def __post_init__(self) -> None:
        """Validate the photo path."""
        if not self.path.exists():
            raise FileNotFoundError(f"Photo not found: {self.path}")

        if self.path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {self.path.suffix}")

    def _load_metadata(self) -> None:
        """Load metadata from the image file."""
        if self._loaded:
            return

        self._caption = get_caption(self.path)
        self._timestamp = get_timestamp(self.path)
        self._dimensions = get_image_dimensions(self.path)
        self._is_landscape = is_landscape(self.path)
        self._loaded = True

    @property
    def name(self) -> str:
        """Get the filename of the photo."""
        return self.path.name

    @property
    def caption(self) -> str | None:
        """Get the caption from EXIF metadata."""
        self._load_metadata()
        return self._caption

    @caption.setter
    def caption(self, value: str | None) -> None:
        """Set the caption in EXIF metadata."""
        if value is None:
            value = ""

        if set_caption(self.path, value):
            self._caption = value if value else None
        else:
            raise OSError(f"Failed to save caption to {self.path}")

    @property
    def has_caption(self) -> bool:
        """Check if the photo has a caption."""
        return bool(self.caption)

    @property
    def timestamp(self) -> datetime | None:
        """Get the photo timestamp from EXIF metadata."""
        self._load_metadata()
        return self._timestamp

    @property
    def timestamp_str(self) -> str:
        """Get the timestamp as a formatted string."""
        ts = self.timestamp
        if ts:
            return ts.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"

    @property
    def dimensions(self) -> tuple[int, int]:
        """Get the image dimensions (width, height)."""
        self._load_metadata()
        return self._dimensions or (0, 0)

    @property
    def width(self) -> int:
        """Get the image width."""
        return self.dimensions[0]

    @property
    def height(self) -> int:
        """Get the image height."""
        return self.dimensions[1]

    @property
    def is_landscape_orientation(self) -> bool:
        """Check if the photo is in landscape orientation."""
        self._load_metadata()
        return self._is_landscape or False

    def reload(self) -> None:
        """Reload metadata from the image file."""
        self._loaded = False
        self._load_metadata()

    @classmethod
    def from_directory(cls, directory: Path) -> list["Photo"]:
        """
        Load all photos from a directory.

        Args:
            directory: Path to the directory to scan.

        Returns:
            List of Photo objects for all supported images in the directory.
        """
        photos: list[Photo] = []

        if not directory.exists() or not directory.is_dir():
            return photos

        for file_path in sorted(directory.iterdir()):
            if file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS:
                try:
                    photos.append(cls(path=file_path))
                except (FileNotFoundError, ValueError):
                    continue

        return photos

    def __eq__(self, other: object) -> bool:
        """Check equality based on path."""
        if isinstance(other, Photo):
            return self.path == other.path
        return False

    def __hash__(self) -> int:
        """Hash based on path."""
        return hash(self.path)
