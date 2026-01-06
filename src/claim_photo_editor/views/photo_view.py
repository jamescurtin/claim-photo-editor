"""Full-screen photo view with caption editing."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from claim_photo_editor.models.photo import Photo

# Style constants
BUTTON_STYLE = (
    "QPushButton { color: white; background: #444; padding: 8px 16px; border-radius: 4px; }"
    "QPushButton:hover { background: #555; }"
)
LABEL_STYLE = "color: #888; font-weight: bold;"
VALUE_STYLE = "color: white;"

# Auto-save delay in milliseconds
AUTO_SAVE_DELAY = 1000


class PhotoView(QWidget):
    """Full-screen photo view with metadata and caption editing."""

    closed = Signal()
    caption_changed = Signal(object)  # Emits Photo object
    navigate_requested = Signal(int)  # Emits direction: -1 for prev, 1 for next

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the photo view."""
        super().__init__(parent)
        self._photo: Photo | None = None
        self._auto_save_timer: QTimer | None = None
        self._last_saved_caption: str = ""
        self._setup_ui()
        self._setup_auto_save()

    def _create_top_bar(self) -> QHBoxLayout:
        """Create the top navigation bar."""
        top_bar = QHBoxLayout()

        close_btn = QPushButton("← Back to Grid")
        close_btn.setStyleSheet(BUTTON_STYLE)
        close_btn.clicked.connect(self.closed.emit)
        top_bar.addWidget(close_btn)

        top_bar.addStretch()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setStyleSheet(BUTTON_STYLE)
        self.prev_btn.clicked.connect(lambda: self.navigate_requested.emit(-1))
        top_bar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet(BUTTON_STYLE)
        self.next_btn.clicked.connect(lambda: self.navigate_requested.emit(1))
        top_bar.addWidget(self.next_btn)

        return top_bar

    def _create_metadata_panel(self) -> QFrame:
        """Create the metadata panel with filename, timestamp, and caption."""
        metadata_frame = QFrame()
        metadata_frame.setStyleSheet(
            "QFrame { background-color: #2a2a2a; border-radius: 8px; padding: 12px; }"
        )
        metadata_layout = QVBoxLayout(metadata_frame)

        # Filename row
        filename_row = QHBoxLayout()
        filename_label = QLabel("Filename:")
        filename_label.setStyleSheet(LABEL_STYLE)
        filename_row.addWidget(filename_label)
        self.filename_value = QLabel()
        self.filename_value.setStyleSheet(VALUE_STYLE)
        filename_row.addWidget(self.filename_value)
        filename_row.addStretch()
        metadata_layout.addLayout(filename_row)

        # Timestamp row
        timestamp_row = QHBoxLayout()
        timestamp_label = QLabel("Taken:")
        timestamp_label.setStyleSheet(LABEL_STYLE)
        timestamp_row.addWidget(timestamp_label)
        self.timestamp_value = QLabel()
        self.timestamp_value.setStyleSheet(VALUE_STYLE)
        timestamp_row.addWidget(self.timestamp_value)
        timestamp_row.addStretch()
        metadata_layout.addLayout(timestamp_row)

        # Caption row
        caption_row = self._create_caption_row()
        metadata_layout.addLayout(caption_row)

        return metadata_frame

    def _create_caption_row(self) -> QHBoxLayout:
        """Create the caption editing row with auto-save."""
        caption_row = QHBoxLayout()

        caption_label = QLabel("Caption:")
        caption_label.setStyleSheet(LABEL_STYLE)
        caption_row.addWidget(caption_label)

        self.caption_input = QLineEdit()
        self.caption_input.setPlaceholderText("Enter caption (auto-saves)...")
        self.caption_input.setStyleSheet(
            "QLineEdit { color: white; background: #444; padding: 8px; border-radius: 4px; }"
            "QLineEdit:focus { background: #555; }"
        )
        # Connect text changes to trigger auto-save timer
        self.caption_input.textChanged.connect(self._on_caption_text_changed)
        # Connect Enter/Return key to clear focus
        self.caption_input.returnPressed.connect(self._on_caption_return_pressed)
        caption_row.addWidget(self.caption_input, stretch=1)

        # Status label instead of save button
        self.save_status_label = QLabel()
        self.save_status_label.setStyleSheet("color: #888; font-size: 12px;")
        self.save_status_label.setFixedWidth(80)
        caption_row.addWidget(self.save_status_label)

        return caption_row

    def _setup_auto_save(self) -> None:
        """Set up the auto-save timer."""
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._auto_save_caption)

    def _on_caption_text_changed(self, _text: str) -> None:
        """Handle caption text changes - restart auto-save timer."""
        if self._auto_save_timer:
            self._auto_save_timer.stop()
            self._auto_save_timer.start(AUTO_SAVE_DELAY)
            self.save_status_label.setText("Typing...")
            self.save_status_label.setStyleSheet("color: #888; font-size: 12px;")

    def _on_caption_return_pressed(self) -> None:
        """Handle Enter/Return key in caption input - save and clear focus."""
        # Force immediate save
        if self._auto_save_timer:
            self._auto_save_timer.stop()
        self._auto_save_caption()
        # Clear focus from caption input
        self.caption_input.clearFocus()
        self.setFocus()

    def _auto_save_caption(self) -> None:
        """Auto-save the caption after typing stops."""
        if not self._photo:
            return

        new_caption = self.caption_input.text().strip()

        # Only save if caption actually changed
        if new_caption == self._last_saved_caption:
            self.save_status_label.setText("")
            return

        try:
            self._photo.caption = new_caption
            self._last_saved_caption = new_caption
            self.caption_changed.emit(self._photo)
            self.save_status_label.setText("Saved")
            self.save_status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
            # Clear the "Saved" status after a short delay
            QTimer.singleShot(2000, lambda: self.save_status_label.setText(""))
        except OSError as e:
            self.save_status_label.setText("Error!")
            self.save_status_label.setStyleSheet("color: #f44336; font-size: 12px;")
            print(f"Failed to save caption: {e}")

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.setStyleSheet("background-color: #1a1a1a;")
        # Enable clicking on the widget to receive focus (so clicking clears caption focus)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        main_layout.addLayout(self._create_top_bar())

        # Image display - use a clickable label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setStyleSheet("background-color: #000;")
        main_layout.addWidget(self.image_label, stretch=1)

        main_layout.addWidget(self._create_metadata_panel())

    def set_photo(self, photo: "Photo") -> None:
        """
        Set the photo to display.

        Args:
            photo: The Photo object to display.
        """
        self._photo = photo
        self._update_display()

    def _update_display(self) -> None:
        """Update the display with current photo data."""
        if not self._photo:
            return

        # Load and display image
        pixmap = QPixmap(str(self._photo.path))
        if not pixmap.isNull():
            # Scale to fit while maintaining aspect ratio
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to load image")
            self.image_label.setStyleSheet("color: white; background-color: #000;")

        # Update metadata
        self.filename_value.setText(self._photo.name)
        self.timestamp_value.setText(self._photo.timestamp_str)

        # Block signals while setting caption to avoid triggering auto-save
        self.caption_input.blockSignals(True)
        current_caption = self._photo.caption or ""
        self.caption_input.setText(current_caption)
        self._last_saved_caption = current_caption
        self.save_status_label.setText("")
        self.caption_input.blockSignals(False)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize to update image scaling."""
        super().resizeEvent(event)
        if self._photo:
            self._update_display()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to clear focus from caption input."""
        # Clear focus from caption input when clicking elsewhere
        if self.caption_input.hasFocus():
            self.caption_input.clearFocus()
            self.setFocus()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation."""
        # Check if caption input has focus - if so, let it handle arrow keys
        caption_focused = self.caption_input.hasFocus()

        if event.key() == Qt.Key.Key_Escape:
            if caption_focused:
                # Clear focus from caption input
                self.caption_input.clearFocus()
            else:
                self.closed.emit()
        elif event.key() == Qt.Key.Key_Left and not caption_focused:
            self.navigate_requested.emit(-1)
        elif event.key() == Qt.Key.Key_Right and not caption_focused:
            self.navigate_requested.emit(1)
        else:
            super().keyPressEvent(event)

    def set_navigation_enabled(self, has_prev: bool, has_next: bool) -> None:
        """
        Enable or disable navigation buttons.

        Args:
            has_prev: Whether there's a previous photo.
            has_next: Whether there's a next photo.
        """
        self.prev_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)

    def get_photo(self) -> "Photo | None":
        """Get the currently displayed photo."""
        return self._photo
