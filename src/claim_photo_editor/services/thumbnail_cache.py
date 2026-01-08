"""Thumbnail and metadata caching service."""

import contextlib
import hashlib
import json
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QPixmap

# Default cache size in bytes (2GB)
DEFAULT_MAX_CACHE_SIZE = 2 * 1024 * 1024 * 1024


class ThumbnailCache:
    """Manages thumbnail and metadata caching for photos."""

    THUMBNAIL_SIZE = 200
    CACHE_VERSION = 1

    def __init__(self, max_size_bytes: int = DEFAULT_MAX_CACHE_SIZE) -> None:
        """
        Initialize the thumbnail cache.

        Args:
            max_size_bytes: Maximum cache size in bytes.
        """
        self._max_size = max_size_bytes
        self._cache_dir = self._get_cache_directory()
        self._thumbnails_dir = self._cache_dir / "thumbnails"
        self._metadata_dir = self._cache_dir / "metadata"
        self._ensure_directories()

    def _get_cache_directory(self) -> Path:
        """Get the cache directory path."""
        cache_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        return Path(cache_root) / "thumbnail_cache"

    def _ensure_directories(self) -> None:
        """Ensure cache directories exist."""
        self._thumbnails_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, photo_path: Path) -> str:
        """
        Generate a cache key for a photo.

        The key is based on the file path and modification time.
        """
        stat = photo_path.stat()
        key_data = f"{photo_path.absolute()}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _get_thumbnail_path(self, cache_key: str) -> Path:
        """Get the path for a cached thumbnail."""
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        return self._thumbnails_dir / subdir / f"{cache_key}.png"

    def _get_metadata_path(self, cache_key: str) -> Path:
        """Get the path for cached metadata."""
        subdir = cache_key[:2]
        return self._metadata_dir / subdir / f"{cache_key}.json"

    def get_thumbnail(self, photo_path: Path) -> QPixmap | None:
        """
        Get a cached thumbnail for a photo.

        Args:
            photo_path: Path to the photo file.

        Returns:
            Cached QPixmap or None if not cached.
        """
        try:
            cache_key = self._get_cache_key(photo_path)
            thumb_path = self._get_thumbnail_path(cache_key)

            if thumb_path.exists():
                pixmap = QPixmap(str(thumb_path))
                if not pixmap.isNull():
                    # Update access time for LRU
                    thumb_path.touch()
                    return pixmap
        except (OSError, ValueError):
            pass

        return None

    def save_thumbnail(self, photo_path: Path, pixmap: QPixmap) -> bool:
        """
        Save a thumbnail to the cache.

        Args:
            photo_path: Path to the original photo.
            pixmap: The thumbnail pixmap to cache.

        Returns:
            True if saved successfully.
        """
        try:
            cache_key = self._get_cache_key(photo_path)
            thumb_path = self._get_thumbnail_path(cache_key)
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            return bool(pixmap.save(str(thumb_path), "PNG"))
        except (OSError, ValueError):
            return False

    def get_metadata(self, photo_path: Path) -> dict[str, object] | None:
        """
        Get cached metadata for a photo.

        Args:
            photo_path: Path to the photo file.

        Returns:
            Cached metadata dict or None if not cached.
        """
        try:
            cache_key = self._get_cache_key(photo_path)
            meta_path = self._get_metadata_path(cache_key)

            if meta_path.exists():
                with meta_path.open(encoding="utf-8") as f:
                    data: dict[str, object] = json.load(f)
                    if data.get("version") == self.CACHE_VERSION:
                        # Update access time for LRU
                        meta_path.touch()
                        return data
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        return None

    def save_metadata(
        self,
        photo_path: Path,
        caption: str | None,
        timestamp: str | None,
        dimensions: tuple[int, int] | None,
        is_landscape: bool | None,
    ) -> bool:
        """
        Save metadata to the cache.

        Args:
            photo_path: Path to the original photo.
            caption: Photo caption.
            timestamp: Timestamp as ISO string.
            dimensions: Image dimensions (width, height).
            is_landscape: Whether image is landscape orientation.

        Returns:
            True if saved successfully.
        """
        try:
            cache_key = self._get_cache_key(photo_path)
            meta_path = self._get_metadata_path(cache_key)
            meta_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": self.CACHE_VERSION,
                "caption": caption,
                "timestamp": timestamp,
                "dimensions": list(dimensions) if dimensions else None,
                "is_landscape": is_landscape,
            }

            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except (OSError, ValueError):
            return False

    def get_cache_size(self) -> int:
        """Get the current cache size in bytes."""
        total_size = 0
        for cache_dir in [self._thumbnails_dir, self._metadata_dir]:
            if cache_dir.exists():
                for dirpath, _dirnames, filenames in os.walk(cache_dir):
                    for filename in filenames:
                        filepath = Path(dirpath) / filename
                        with contextlib.suppress(OSError):
                            total_size += filepath.stat().st_size
        return total_size

    def evict_old_entries(self) -> int:
        """
        Evict old cache entries if cache exceeds max size.

        Returns:
            Number of entries evicted.
        """
        current_size = self.get_cache_size()
        if current_size <= self._max_size:
            return 0

        # Collect all cache files with their access times
        cache_files: list[tuple[Path, float, int]] = []
        for cache_dir in [self._thumbnails_dir, self._metadata_dir]:
            if cache_dir.exists():
                for dirpath, _dirnames, filenames in os.walk(cache_dir):
                    for filename in filenames:
                        filepath = Path(dirpath) / filename
                        try:
                            stat = filepath.stat()
                            cache_files.append((filepath, stat.st_atime, stat.st_size))
                        except OSError:
                            pass

        # Sort by access time (oldest first)
        cache_files.sort(key=lambda x: x[1])

        # Delete oldest files until under limit
        evicted = 0
        target_size = int(self._max_size * 0.8)  # Evict to 80% of max
        for filepath, _atime, size in cache_files:
            if current_size <= target_size:
                break
            try:
                filepath.unlink()
                current_size -= size
                evicted += 1
            except OSError:
                pass

        return evicted

    def clear(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of files deleted.
        """
        deleted = 0
        for cache_dir in [self._thumbnails_dir, self._metadata_dir]:
            if cache_dir.exists():
                for dirpath, _dirnames, filenames in os.walk(cache_dir, topdown=False):
                    for filename in filenames:
                        filepath = Path(dirpath) / filename
                        try:
                            filepath.unlink()
                            deleted += 1
                        except OSError:
                            pass
                    # Remove empty directories
                    with contextlib.suppress(OSError):
                        Path(dirpath).rmdir()
        return deleted

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        size = self.get_cache_size()
        thumbnail_count = 0
        metadata_count = 0

        if self._thumbnails_dir.exists():
            for _dirpath, _dirnames, filenames in os.walk(self._thumbnails_dir):
                thumbnail_count += len(filenames)

        if self._metadata_dir.exists():
            for _dirpath, _dirnames, filenames in os.walk(self._metadata_dir):
                metadata_count += len(filenames)

        return {
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "max_size_mb": round(self._max_size / (1024 * 1024), 2),
            "thumbnail_count": thumbnail_count,
            "metadata_count": metadata_count,
        }


class _CacheManager:
    """Manager for the global thumbnail cache instance."""

    _instance: ThumbnailCache | None = None

    @classmethod
    def get_cache(cls, max_size_bytes: int = DEFAULT_MAX_CACHE_SIZE) -> ThumbnailCache:
        """Get or create the global thumbnail cache instance."""
        if cls._instance is None:
            cls._instance = ThumbnailCache(max_size_bytes)
        return cls._instance

    @classmethod
    def clear_cache(cls) -> int:
        """Clear the global thumbnail cache."""
        cache = cls.get_cache()
        return cache.clear()


def get_thumbnail_cache(max_size_bytes: int = DEFAULT_MAX_CACHE_SIZE) -> ThumbnailCache:
    """Get or create the global thumbnail cache instance."""
    return _CacheManager.get_cache(max_size_bytes)


def clear_thumbnail_cache() -> int:
    """Clear the global thumbnail cache."""
    return _CacheManager.clear_cache()
