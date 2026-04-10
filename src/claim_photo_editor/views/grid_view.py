"""Grid view widget for displaying photo thumbnails."""

from enum import Enum
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from claim_photo_editor.models.photo import Photo
from claim_photo_editor.services.thumbnail_cache import get_thumbnail_cache

if TYPE_CHECKING:
    from datetime import datetime
from claim_photo_editor.utils.exif import (
    get_caption,
    get_image_dimensions,
    get_timestamp,
)


class PhotoFilter(Enum):
    """Filter options for photo display."""

    ALL = "All Photos"
    CAPTIONED = "Captioned Only"
    UNCAPTIONED = "Uncaptioned Only"


def get_text_color() -> str:
    """Get appropriate text color based on current theme."""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        palette = app.palette()
        text_color = palette.color(QPalette.ColorRole.WindowText)
        return str(text_color.name())
    return "#000000"


def get_secondary_text_color() -> str:
    """Get appropriate secondary text color based on current theme."""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        palette = app.palette()
        # Use a muted version of the text color
        text_color = palette.color(QPalette.ColorRole.PlaceholderText)
        return str(text_color.name())
    return "#888888"


_SENTINEL = None  # Poison pill to stop workers


class ThumbnailWorker(QThread):
    """Worker thread that processes thumbnail load requests from a shared queue.

    Uses QImage (thread-safe) instead of QPixmap (GUI-thread only). All
    Pillow/image I/O is performed in this thread to avoid concurrent access
    to pillow-heif's non-thread-safe libheif from the main thread.
    """

    # path, image, caption, timestamp, dimensions
    content_loaded = Signal(str, QImage, object, object, object)

    def __init__(self, queue: "Queue[tuple[Path, int] | None]") -> None:
        super().__init__()
        self._queue = queue

    def run(self) -> None:
        """Process items from the queue until a sentinel is received.

        All image operations use Pillow (thread-safe). QImage is only created
        at the end from raw pixel data for the signal — no Qt image I/O calls
        are made from this thread (Qt's image plugins are not thread-safe).
        """
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                return
            photo_path, size = item
            try:
                caption = get_caption(photo_path)
                timestamp = get_timestamp(photo_path)
                dimensions = get_image_dimensions(photo_path)

                cache = get_thumbnail_cache()

                # Check thumbnail cache — load as Pillow image (thread-safe)
                cached_path = cache._lookup_cached_path(photo_path)
                if cached_path is not None:
                    with Image.open(cached_path) as cached_pil:
                        qimage = self._pil_to_qimage(cached_pil)
                    self.content_loaded.emit(
                        str(photo_path), qimage, caption, timestamp, dimensions
                    )
                    continue

                # Load and scale with Pillow (thread-safe)
                with Image.open(photo_path) as raw_img:
                    oriented = ImageOps.exif_transpose(raw_img) or raw_img
                    oriented.thumbnail((size, size), Image.Resampling.LANCZOS)
                    thumb = oriented.convert("RGB")

                    # Save to cache using Pillow (thread-safe)
                    save_path = cache._prepare_save_path(photo_path)
                    if save_path is not None:
                        thumb.save(str(save_path), "PNG")

                    qimage = self._pil_to_qimage(thumb)

                self.content_loaded.emit(str(photo_path), qimage, caption, timestamp, dimensions)
            except Exception:
                pass

    @staticmethod
    def _pil_to_qimage(pil_img: Image.Image) -> QImage:
        """Convert a Pillow image to QImage without using Qt image I/O."""
        rgb = pil_img.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimage = QImage(data, rgb.width, rgb.height, 3 * rgb.width, QImage.Format.Format_RGB888)
        return qimage.copy()  # Copy before data goes out of scope


# Single worker to avoid Qt image I/O thread-safety issues (QImage.save/scaled
# crash when called concurrently from multiple threads).
MAX_THUMBNAIL_WORKERS = 1
_work_queue: Queue[tuple[Path, int] | None] = Queue()
_workers: list[ThumbnailWorker] = []


def _ensure_workers() -> None:
    """Start worker threads if not already running."""
    if _workers:
        return
    for _ in range(MAX_THUMBNAIL_WORKERS):
        w = ThumbnailWorker(_work_queue)
        _workers.append(w)
        w.start()


class PhotoThumbnail(QFrame):
    """Widget for displaying a single photo thumbnail with caption."""

    clicked = Signal(object)  # Emits Photo object

    THUMBNAIL_SIZE = 200
    CAPTION_HEIGHT = 50  # Increased height for caption display

    def __init__(
        self, photo: Photo, parent: QWidget | None = None, defer_load: bool = False
    ) -> None:
        """
        Initialize the thumbnail widget.

        Args:
            photo: The Photo object to display.
            parent: Parent widget.
            defer_load: If True, don't load thumbnail immediately (call load_content() later).
        """
        super().__init__(parent)
        self.photo = photo
        self._content_loaded = False
        self._setup_ui(defer_load)

    def _setup_ui(self, defer_load: bool = False) -> None:
        """Set up the UI components."""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #f0f0f0;")
        self.image_label.setText("Loading...")
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Caption label - fixed height, shows blank if no caption
        self.caption_label = QLabel()
        self.caption_label.setWordWrap(True)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setMaximumWidth(self.THUMBNAIL_SIZE)
        self.caption_label.setFixedHeight(self.CAPTION_HEIGHT)
        layout.addWidget(self.caption_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setFixedWidth(self.THUMBNAIL_SIZE + 16)

        # Load content immediately unless deferred
        if not defer_load:
            self.load_content()

    def load_content(self) -> None:
        """Submit thumbnail and metadata loading to the shared worker pool."""
        if self._content_loaded:
            return
        self._content_loaded = True
        _work_queue.put((self.photo.path, self.THUMBNAIL_SIZE))

    content_ready = Signal()  # Emitted when worker finishes

    def apply_loaded_content(
        self,
        image: QImage,
        caption: str | None,
        timestamp: "datetime | None",
        dimensions: tuple[int, int],
    ) -> None:
        """Apply loaded thumbnail and metadata from a worker thread.

        Called by GridView._on_worker_content_loaded after path dispatch.
        Writes metadata to the Photo object on the main thread (safe).
        """
        self.photo._caption = caption
        self.photo._timestamp = timestamp
        self.photo._dimensions = dimensions
        w, h = dimensions
        self.photo._is_landscape = w > h
        self.photo._loaded = True

        self.image_label.setPixmap(QPixmap.fromImage(image))
        self._update_caption_display(caption)
        self.content_ready.emit()

    def _update_caption_display(self, caption: str | None) -> None:
        """Update the caption label text."""
        if caption:
            text_color = get_text_color()
            display_text = caption if len(caption) <= 60 else caption[:57] + "..."
            self.caption_label.setText(display_text)
            self.caption_label.setStyleSheet(f"color: {text_color};")
        else:
            self.caption_label.setText("")
            self.caption_label.setStyleSheet("")

    def refresh(self) -> None:
        """Refresh the display after caption change."""
        self.photo.reload()
        self._update_caption_display(self.photo.caption)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to emit clicked signal."""
        self.clicked.emit(self.photo)
        super().mousePressEvent(event)


class GridView(QWidget):
    """Grid view for displaying photo thumbnails."""

    photo_selected = Signal(object)  # Emits Photo object
    generate_pdf_requested = Signal()

    COLUMNS = 4
    BATCH_SIZE = 8  # Number of thumbnails to create per batch

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the grid view."""
        super().__init__(parent)
        self._photos: list[Photo] = []
        self._thumbnails: list[PhotoThumbnail] = []
        self._thumb_by_path: dict[str, PhotoThumbnail] = {}
        self._current_filter = PhotoFilter.ALL
        self._current_folder: Path | None = None
        self._is_loading = False
        self._pending_photos: list[Photo] = []
        self._batch_timer: QTimer | None = None
        self._workers_pending = 0
        self._workers_connected = False
        self._setup_ui()
        self._connect_workers()

    def _connect_workers(self) -> None:
        """Start worker threads and connect their signals."""
        if self._workers_connected:
            return
        _ensure_workers()
        for w in _workers:
            w.content_loaded.connect(self._on_worker_content_loaded)
        self._workers_connected = True

    def _on_worker_content_loaded(
        self,
        path: str,
        image: QImage,
        caption: str | None,
        timestamp: "datetime | None",
        dimensions: tuple[int, int],
    ) -> None:
        """Dispatch worker results to the correct PhotoThumbnail."""
        thumb = self._thumb_by_path.get(path)
        if thumb is not None:
            thumb.apply_loaded_content(image, caption, timestamp, dimensions)

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        toolbar = QHBoxLayout()

        # Folder name label
        self.folder_label = QLabel("Select a folder")
        self.folder_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        toolbar.addWidget(self.folder_label)

        toolbar.addStretch()

        # Filter dropdown
        filter_label = QLabel("Filter:")
        toolbar.addWidget(filter_label)

        self.filter_combo = QComboBox()
        for filter_option in PhotoFilter:
            self.filter_combo.addItem(filter_option.value, filter_option)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_combo)

        # Generate PDF button
        self.generate_btn = QPushButton("Generate PDF")
        self.generate_btn.clicked.connect(self.generate_pdf_requested.emit)
        self.generate_btn.setEnabled(False)
        toolbar.addWidget(self.generate_btn)

        main_layout.addLayout(toolbar)

        # Loading widget (shown during folder loading)
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.loading_label = QLabel("Loading photos...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 14px;")
        loading_layout.addWidget(self.loading_label)

        self.loading_progress = QProgressBar()
        self.loading_progress.setFixedWidth(300)
        loading_layout.addWidget(self.loading_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self.loading_widget.hide()
        main_layout.addWidget(self.loading_widget)

        # Scroll area for grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container for grid
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area)

        # Status bar
        self.status_label = QLabel()
        secondary_color = get_secondary_text_color()
        self.status_label.setStyleSheet(f"color: {secondary_color};")
        main_layout.addWidget(self.status_label)

    def show_loading(self) -> None:
        """Show loading indicator."""
        self._is_loading = True
        self.loading_progress.setRange(0, 0)  # Indeterminate
        self.loading_label.setText("Loading photos...")
        self.loading_widget.show()
        self.scroll_area.hide()
        self.folder_label.setText("Loading...")
        self.status_label.setText("")

    def hide_loading(self) -> None:
        """Hide loading indicator."""
        self._is_loading = False
        self.loading_widget.hide()
        self.scroll_area.show()

    def set_photos(self, photos: list[Photo], folder_path: Path) -> None:
        """
        Set the photos to display.

        Args:
            photos: List of Photo objects.
            folder_path: Path to the current folder.
        """
        self._photos = photos
        self._current_folder = folder_path
        self.folder_label.setText(folder_path.name)

        # Show loading with determinate progress
        total = len(photos)
        if total > 0:
            self.loading_progress.setRange(0, total)
            self.loading_progress.setValue(0)
            self.loading_label.setText(f"Loading 0 of {total} photos...")
            self.loading_widget.show()
            self.scroll_area.hide()
        else:
            self.hide_loading()

        self._refresh_grid()

    def _refresh_grid(self) -> None:
        """Refresh the grid display with current filter."""
        # Stop any pending batch loading
        if self._batch_timer:
            self._batch_timer.stop()

        # Drain stale work items so the new folder's items are processed immediately
        while not _work_queue.empty():
            try:
                _work_queue.get_nowait()
            except Exception:
                break

        # Clear existing thumbnails
        for thumb in self._thumbnails:
            thumb.deleteLater()
        self._thumbnails.clear()
        self._thumb_by_path.clear()
        self._workers_pending = 0

        # Filter photos - for "ALL" filter, skip has_caption check during initial load
        if self._current_filter == PhotoFilter.ALL:
            filtered_photos = self._photos
        else:
            # For filtered views, we need to check captions
            filtered_photos = self._get_filtered_photos()

        # Store photos to load in batches
        self._pending_photos = list(filtered_photos)

        # Start batch loading
        if self._pending_photos:
            self._batch_timer = QTimer(self)
            self._batch_timer.timeout.connect(self._load_next_batch)
            self._batch_timer.start(10)  # Small delay between batches for UI responsiveness
        else:
            self._finish_loading()

    def _load_next_batch(self) -> None:
        """Load the next batch of thumbnails."""
        if not self._pending_photos:
            if self._batch_timer:
                self._batch_timer.stop()
            self._finish_loading()
            return

        # Get next batch
        batch = self._pending_photos[: self.BATCH_SIZE]
        self._pending_photos = self._pending_photos[self.BATCH_SIZE :]

        # Calculate starting index
        start_idx = len(self._thumbnails)

        # Create thumbnails for this batch
        for i, photo in enumerate(batch):
            idx = start_idx + i
            thumb = PhotoThumbnail(photo, defer_load=True)
            thumb.clicked.connect(self._on_thumbnail_clicked)
            thumb.content_ready.connect(self._on_worker_finished)

            row = idx // self.COLUMNS
            col = idx % self.COLUMNS
            self.grid_layout.addWidget(thumb, row, col)
            self._thumbnails.append(thumb)
            self._thumb_by_path[str(photo.path)] = thumb

            self._workers_pending += 1
            thumb.load_content()

        # Update progress
        loaded = len(self._thumbnails)
        total = loaded + len(self._pending_photos)
        self.loading_progress.setValue(loaded)
        self.loading_label.setText(f"Loading {loaded} of {total} photos...")

        # Process events to keep UI responsive
        QApplication.processEvents()

    def _finish_loading(self) -> None:
        """Finish batch dispatching and show the grid. Status updates when workers complete."""
        self.hide_loading()

        # Add spacer at bottom
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.grid_layout.addWidget(
            spacer, len(self._thumbnails) // self.COLUMNS + 1, 0, 1, self.COLUMNS
        )

        # If all workers already finished (e.g., all from cache), update status now
        if self._workers_pending <= 0:
            self._update_status()

    def _on_worker_finished(self) -> None:
        """Called when a thumbnail worker completes. Updates status when all are done."""
        self._workers_pending -= 1
        if self._workers_pending <= 0:
            self._update_status()

    def _update_status(self) -> None:
        """Update the status bar and Generate PDF button from loaded metadata."""
        total = len(self._photos)
        captioned = sum(1 for p in self._photos if p.is_loaded and p.has_caption)
        filtered = len(self._thumbnails)
        self.status_label.setText(f"Showing {filtered} of {total} photos ({captioned} captioned)")
        self.generate_btn.setEnabled(captioned > 0)

    def _get_filtered_photos(self) -> list[Photo]:
        """Get photos based on current filter."""
        if self._current_filter == PhotoFilter.ALL:
            return self._photos
        elif self._current_filter == PhotoFilter.CAPTIONED:
            return [p for p in self._photos if p.has_caption]
        else:  # UNCAPTIONED
            return [p for p in self._photos if not p.has_caption]

    def _on_filter_changed(self, index: int) -> None:
        """Handle filter dropdown change."""
        self._current_filter = self.filter_combo.itemData(index)
        self._refresh_grid()

    def _on_thumbnail_clicked(self, photo: Photo) -> None:
        """Handle thumbnail click."""
        self.photo_selected.emit(photo)

    def refresh_photo(self, photo: Photo) -> None:
        """
        Refresh a specific photo's thumbnail.

        Args:
            photo: The photo to refresh.
        """
        for thumb in self._thumbnails:
            if thumb.photo == photo:
                thumb.refresh()
                break

        self._update_status()

    def get_captioned_photos(self) -> list[Photo]:
        """Get all photos that have captions."""
        return [p for p in self._photos if p.has_caption]

    def get_current_folder(self) -> Path | None:
        """Get the current folder path."""
        return self._current_folder

    def clear(self) -> None:
        """Clear the grid."""
        # Stop any pending batch loading
        if self._batch_timer:
            self._batch_timer.stop()
        self._pending_photos.clear()

        self._photos = []
        self._current_folder = None
        for thumb in self._thumbnails:
            thumb.deleteLater()
        self._thumbnails.clear()
        self._thumb_by_path.clear()
        self.folder_label.setText("Select a folder")
        self.status_label.setText("")
        self.generate_btn.setEnabled(False)
