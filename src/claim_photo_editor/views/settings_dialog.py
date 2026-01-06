"""Settings dialog for configuring PDF generation options."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from claim_photo_editor.config import Config, ImageQuality, Orientation, PDFSettings
from claim_photo_editor.services.thumbnail_cache import get_thumbnail_cache


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        """
        Initialize the settings dialog.

        Args:
            config: Application configuration.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.config = config
        self._settings = config.get_pdf_settings()
        self._setup_ui()
        self._load_settings()

    def _create_margin_spinbox(self) -> QDoubleSpinBox:
        """Create a margin spin box with standard settings."""
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0, 2)
        spinbox.setSingleStep(0.25)
        spinbox.setDecimals(2)
        return spinbox

    def _create_directories_group(self) -> QGroupBox:
        """Create the directories settings group."""
        dir_group = QGroupBox("Photo Directories")
        dir_layout = QFormLayout()

        # New Photos directory
        new_photos_layout = QHBoxLayout()
        self.new_photos_input = QLineEdit()
        self.new_photos_input.setReadOnly(True)
        self.new_photos_input.setPlaceholderText("Not configured")
        new_photos_layout.addWidget(self.new_photos_input)

        new_photos_btn = QPushButton("Browse...")
        new_photos_btn.clicked.connect(self._browse_new_photos)
        new_photos_layout.addWidget(new_photos_btn)
        dir_layout.addRow("New Photos:", new_photos_layout)

        # Completed Photos directory
        completed_layout = QHBoxLayout()
        self.completed_input = QLineEdit()
        self.completed_input.setReadOnly(True)
        self.completed_input.setPlaceholderText("Not configured")
        completed_layout.addWidget(self.completed_input)

        completed_btn = QPushButton("Browse...")
        completed_btn.clicked.connect(self._browse_completed_photos)
        completed_layout.addWidget(completed_btn)
        dir_layout.addRow("Completed Photos:", completed_layout)

        dir_group.setLayout(dir_layout)
        return dir_group

    def _create_pdf_group(self) -> QGroupBox:
        """Create the PDF settings group."""
        pdf_group = QGroupBox("PDF Generation")
        pdf_layout = QFormLayout()

        # Grid layout
        grid_layout = QHBoxLayout()
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 6)
        self.rows_spin.setValue(2)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.rows_spin)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 6)
        self.cols_spin.setValue(2)
        grid_layout.addWidget(QLabel("Columns:"))
        grid_layout.addWidget(self.cols_spin)
        grid_layout.addStretch()
        pdf_layout.addRow("Grid Layout:", grid_layout)

        # Orientation
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Landscape", Orientation.LANDSCAPE)
        self.orientation_combo.addItem("Portrait", Orientation.PORTRAIT)
        pdf_layout.addRow("Orientation:", self.orientation_combo)

        # Font
        self.font_combo = QComboBox()
        for font in ["Helvetica", "Times-Roman", "Courier"]:
            self.font_combo.addItem(font, font)
        pdf_layout.addRow("Font:", self.font_combo)

        # DPI
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(50, 300)
        self.dpi_spin.setValue(75)
        self.dpi_spin.setSuffix(" DPI")
        pdf_layout.addRow("Resolution:", self.dpi_spin)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Low (smallest file)", ImageQuality.LOW)
        self.quality_combo.addItem("Medium (balanced)", ImageQuality.MEDIUM)
        self.quality_combo.addItem("High (best quality)", ImageQuality.HIGH)
        pdf_layout.addRow("Image Quality:", self.quality_combo)

        pdf_group.setLayout(pdf_layout)
        return pdf_group

    def _create_margins_group(self) -> QGroupBox:
        """Create the margins settings group."""
        margins_group = QGroupBox("Margins (inches)")
        margins_layout = QFormLayout()

        self.margin_top = self._create_margin_spinbox()
        margins_layout.addRow("Top:", self.margin_top)

        self.margin_bottom = self._create_margin_spinbox()
        margins_layout.addRow("Bottom:", self.margin_bottom)

        self.margin_left = self._create_margin_spinbox()
        margins_layout.addRow("Left:", self.margin_left)

        self.margin_right = self._create_margin_spinbox()
        margins_layout.addRow("Right:", self.margin_right)

        margins_group.setLayout(margins_layout)
        return margins_group

    def _create_cache_group(self) -> QGroupBox:
        """Create the cache settings group."""
        cache_group = QGroupBox("Thumbnail Cache")
        cache_layout = QFormLayout()

        # Max cache size
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(100, 10000)  # 100MB to 10GB
        self.cache_size_spin.setSingleStep(100)
        self.cache_size_spin.setSuffix(" MB")
        cache_layout.addRow("Max Cache Size:", self.cache_size_spin)

        # Cache status label
        self.cache_status_label = QLabel()
        cache_layout.addRow("Current Usage:", self.cache_status_label)

        # Clear cache button
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_layout.addRow("", clear_cache_btn)

        cache_group.setLayout(cache_layout)
        return cache_group

    def _update_cache_status(self) -> None:
        """Update the cache status label."""
        cache = get_thumbnail_cache()
        stats = cache.get_cache_stats()
        self.cache_status_label.setText(
            f"{stats['size_mb']} MB ({stats['thumbnail_count']} thumbnails)"
        )

    def _clear_cache(self) -> None:
        """Clear the thumbnail cache."""
        result = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear the thumbnail cache?\n\n"
            "This will make folders slower to open the first time after clearing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            cache = get_thumbnail_cache()
            deleted = cache.clear()
            self._update_cache_status()
            QMessageBox.information(
                self,
                "Cache Cleared",
                f"Cleared {deleted} cached files.",
            )

    def _create_button_layout(self) -> QHBoxLayout:
        """Create the dialog button layout."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        return button_layout

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.addWidget(self._create_directories_group())
        layout.addWidget(self._create_pdf_group())
        layout.addWidget(self._create_margins_group())
        layout.addWidget(self._create_cache_group())
        layout.addLayout(self._create_button_layout())

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        # Load directory settings
        if self.config.new_photos_dir:
            self.new_photos_input.setText(str(self.config.new_photos_dir))
        if self.config.completed_photos_dir:
            self.completed_input.setText(str(self.config.completed_photos_dir))

        # Load PDF settings
        self.rows_spin.setValue(self._settings.rows)
        self.cols_spin.setValue(self._settings.columns)

        for combo, value in [
            (self.orientation_combo, self._settings.orientation),
            (self.font_combo, self._settings.font_family),
            (self.quality_combo, self._settings.image_quality),
        ]:
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)

        self.dpi_spin.setValue(self._settings.dpi)

        self.margin_top.setValue(self._settings.margin_top)
        self.margin_bottom.setValue(self._settings.margin_bottom)
        self.margin_left.setValue(self._settings.margin_left)
        self.margin_right.setValue(self._settings.margin_right)

        # Load cache settings
        self.cache_size_spin.setValue(self.config.cache_max_size_mb)
        self._update_cache_status()

    def _browse_new_photos(self) -> None:
        """Browse for new photos directory."""
        current = self.new_photos_input.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select New Photos Folder",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.new_photos_input.setText(directory)

    def _browse_completed_photos(self) -> None:
        """Browse for completed photos directory."""
        current = self.completed_input.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Completed Photos Folder",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.completed_input.setText(directory)

    def _save_settings(self) -> None:
        """Save settings and close dialog."""
        # Save directory settings
        new_photos_text = self.new_photos_input.text()
        if new_photos_text:
            self.config.new_photos_dir = Path(new_photos_text)

        completed_text = self.completed_input.text()
        if completed_text:
            self.config.completed_photos_dir = Path(completed_text)

        # Save PDF settings
        settings = PDFSettings(
            rows=self.rows_spin.value(),
            columns=self.cols_spin.value(),
            orientation=self.orientation_combo.currentData(),
            margin_top=self.margin_top.value(),
            margin_bottom=self.margin_bottom.value(),
            margin_left=self.margin_left.value(),
            margin_right=self.margin_right.value(),
            font_family=self.font_combo.currentData(),
            dpi=self.dpi_spin.value(),
            image_quality=self.quality_combo.currentData(),
        )
        self.config.set_pdf_settings(settings)

        # Save cache settings
        self.config.cache_max_size_mb = self.cache_size_spin.value()

        self.config.sync()
        self.accept()

    def _reset_to_defaults(self) -> None:
        """Reset PDF settings to defaults (preserves directory settings)."""
        defaults = PDFSettings()
        self._settings = defaults
        self._load_settings()
