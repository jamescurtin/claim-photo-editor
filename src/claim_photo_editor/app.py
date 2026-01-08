"""Main application window."""

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
    QWidget,
)

from claim_photo_editor import __app_name__, __version__
from claim_photo_editor.config import Config, PDFSettings
from claim_photo_editor.models.photo import Photo
from claim_photo_editor.services.pdf_generator import PDFGenerator
from claim_photo_editor.services.updater import UpdateChecker
from claim_photo_editor.views.grid_view import GridView
from claim_photo_editor.views.photo_view import PhotoView
from claim_photo_editor.views.settings_dialog import SettingsDialog
from claim_photo_editor.views.sidebar import Sidebar
from claim_photo_editor.views.welcome_dialog import WelcomeDialog


def is_development_mode() -> bool:
    """Check if running in development mode."""
    # Check for common development indicators
    return (
        os.environ.get("CLAIM_PHOTO_EDITOR_DEV") == "1"
        or __version__.endswith("-dev")
        or not getattr(__import__("sys"), "frozen", False)  # Not frozen by PyInstaller
    )


class UpdateWorker(QThread):
    """Background worker for checking updates."""

    update_available = Signal(str, str)  # version, release_notes
    no_update = Signal()
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.checker = UpdateChecker()

    def run(self) -> None:
        """Check for updates in background."""
        try:
            has_update, version = self.checker.check_for_updates()
            if has_update and version:
                notes = self.checker.get_release_notes()
                self.update_available.emit(version, notes)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))


class PhotoLoaderWorker(QThread):
    """Background worker for loading photos."""

    photos_loaded = Signal(list, Path)  # List of Photo objects, folder path
    error = Signal(str)

    def __init__(self, folder_path: Path) -> None:
        super().__init__()
        self.folder_path = folder_path
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the loading operation."""
        self._cancelled = True

    def run(self) -> None:
        """Load photos in background."""
        try:
            if self._cancelled:
                return
            photos = Photo.from_directory(self.folder_path)
            if not self._cancelled:
                self.photos_loaded.emit(photos, self.folder_path)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


class PDFGeneratorWorker(QThread):
    """Background worker for generating PDFs."""

    progress = Signal(int, int)  # current, total
    finished = Signal()
    error = Signal(str)

    def __init__(self, photos: list[Photo], output_path: Path, settings: "PDFSettings") -> None:
        super().__init__()
        self.photos = photos
        self.output_path = output_path
        self.settings = settings

    def run(self) -> None:
        """Generate PDF in background."""
        try:
            generator = PDFGenerator(self.settings)
            generator.generate(self.photos, self.output_path, progress_callback=self._on_progress)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int) -> None:
        """Emit progress signal."""
        self.progress.emit(current, total)


class MainWindow(QMainWindow):
    """Main application window."""

    # Auto-refresh interval in milliseconds (30 seconds)
    AUTO_REFRESH_INTERVAL = 30000

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        self.config = Config()
        self._photos: list[Photo] = []
        self._current_photo_index = 0
        self._photo_loader: PhotoLoaderWorker | None = None
        self._old_loaders: list[PhotoLoaderWorker] = []  # Keep refs to prevent GC
        self._file_watcher: QFileSystemWatcher | None = None
        self._auto_refresh_timer: QTimer | None = None
        self._loading_folder_path: Path | None = None
        self._pdf_progress: QProgressDialog | None = None
        self._pdf_folder_path: Path | None = None
        self._setup_ui()
        self._setup_menu()
        self._setup_file_watcher()
        self._check_directory()
        self._check_for_updates()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setMinimumSize(1200, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.folder_selected.connect(self._on_folder_selected)
        main_layout.addWidget(self.sidebar)

        # Stacked widget for grid/photo views
        self.stack = QStackedWidget()

        # Grid view
        self.grid_view = GridView()
        self.grid_view.photo_selected.connect(self._on_photo_selected)
        self.grid_view.generate_pdf_requested.connect(self._generate_pdf)
        self.stack.addWidget(self.grid_view)

        # Photo view
        self.photo_view = PhotoView()
        self.photo_view.closed.connect(self._show_grid_view)
        self.photo_view.caption_changed.connect(self._on_caption_changed)
        self.photo_view.navigate_requested.connect(self._navigate_photo)
        self.stack.addWidget(self.photo_view)

        main_layout.addWidget(self.stack, stretch=1)

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = QMenuBar()
        self.setMenuBar(menubar)

        # File menu
        file_menu = menubar.addMenu("File")

        change_dir_action = file_menu.addAction("Change Photo Directories...")
        change_dir_action.triggered.connect(self._show_welcome_dialog)

        file_menu.addSeparator()

        refresh_action = QAction("Refresh Folders", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(self._refresh_all)
        file_menu.addAction(refresh_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        settings_action = edit_menu.addAction("Settings...")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._show_about)

        check_updates_action = help_menu.addAction("Check for Updates...")
        check_updates_action.triggered.connect(self._manual_update_check)

    def _setup_file_watcher(self) -> None:
        """Set up file system watcher for auto-refresh."""
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)

        # Also set up periodic refresh timer as backup
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._refresh_sidebar)
        self._auto_refresh_timer.start(self.AUTO_REFRESH_INTERVAL)

    def _on_directory_changed(self, _path: str) -> None:
        """Handle directory change from file watcher."""
        # Debounce by using a short timer
        QTimer.singleShot(500, self._refresh_sidebar)

    def _check_directory(self) -> None:
        """Check if photos directories are configured."""
        if not self.config.is_configured():
            self._show_welcome_dialog()
        else:
            self._refresh_sidebar()

    def _show_welcome_dialog(self) -> None:
        """Show the welcome/setup dialog."""
        dialog = WelcomeDialog(self)

        # Pre-fill with existing values if available
        if self.config.new_photos_dir:
            dialog.new_photos_input.setText(str(self.config.new_photos_dir))
            dialog._new_photos_dir = self.config.new_photos_dir
        if self.config.completed_photos_dir:
            dialog.completed_input.setText(str(self.config.completed_photos_dir))
            dialog._completed_photos_dir = self.config.completed_photos_dir
        dialog._update_continue_button()

        if dialog.exec():
            new_dir = dialog.get_new_photos_dir()
            completed_dir = dialog.get_completed_photos_dir()

            if new_dir:
                self.config.new_photos_dir = new_dir
            if completed_dir:
                self.config.completed_photos_dir = completed_dir

            self.config.sync()
            self._refresh_sidebar()

    def _refresh_all(self) -> None:
        """Refresh both sidebar and current grid."""
        self._refresh_sidebar()
        # If we have a current folder, reload its photos
        current_folder = self.grid_view.get_current_folder()
        if current_folder and current_folder.exists():
            self._on_folder_selected(current_folder)

    def _refresh_sidebar(self) -> None:
        """Refresh the sidebar folder list."""
        new_photos_dir = self.config.new_photos_dir
        if new_photos_dir and new_photos_dir.exists():
            self.sidebar.set_estimate_directory(new_photos_dir)

            # Update file watcher
            if self._file_watcher:
                # Remove old paths
                if self._file_watcher.directories():
                    self._file_watcher.removePaths(self._file_watcher.directories())
                # Add new path
                self._file_watcher.addPath(str(new_photos_dir))
        elif self.config.is_configured():
            QMessageBox.warning(
                self,
                "Directory Not Found",
                f"The New Photos folder was not found:\n{new_photos_dir}\n\n"
                "Please update your settings.",
            )

    def _on_folder_selected(self, folder_path: Path) -> None:
        """Handle folder selection from sidebar."""
        # Skip if already loading this folder
        if (
            hasattr(self, "_loading_folder_path")
            and self._loading_folder_path == folder_path
            and self._photo_loader is not None
            and self._photo_loader.isRunning()
        ):
            return

        # Cancel any existing loader gracefully (don't use terminate())
        if self._photo_loader is not None:
            self._photo_loader.cancel()
            # Disconnect signals to avoid stale callbacks
            try:
                self._photo_loader.photos_loaded.disconnect(self._on_photos_loaded)
                self._photo_loader.error.disconnect(self._on_photo_load_error)
            except RuntimeError:
                pass  # Signals may not be connected
            # Keep reference to prevent "destroyed while running" warning
            self._photo_loader.finished.connect(self._cleanup_old_loader)
            self._old_loaders.append(self._photo_loader)

        # Track which folder we're loading
        self._loading_folder_path = folder_path

        # Show loading state
        self.grid_view.show_loading()

        # Load photos in background
        self._photo_loader = PhotoLoaderWorker(folder_path)
        self._photo_loader.photos_loaded.connect(self._on_photos_loaded)
        self._photo_loader.error.connect(self._on_photo_load_error)
        self._photo_loader.start()

    def _on_photos_loaded(self, photos: list[Photo], folder_path: Path) -> None:
        """Handle photos loaded from background thread."""
        # Ignore if this is from a stale loader (different folder)
        if hasattr(self, "_loading_folder_path") and self._loading_folder_path != folder_path:
            return

        self._photos = photos
        self.grid_view.set_photos(self._photos, folder_path)
        self._show_grid_view()

    def _on_photo_load_error(self, error: str) -> None:
        """Handle photo loading error."""
        self.grid_view.hide_loading()
        QMessageBox.warning(
            self,
            "Error Loading Photos",
            f"Failed to load photos: {error}",
        )

    def _cleanup_old_loader(self) -> None:
        """Clean up finished old loaders."""
        # Remove finished loaders from the list
        self._old_loaders = [loader for loader in self._old_loaders if loader.isRunning()]

    def _on_photo_selected(self, photo: Photo) -> None:
        """Handle photo selection from grid."""
        try:
            self._current_photo_index = self._photos.index(photo)
        except ValueError:
            self._current_photo_index = 0

        self._show_photo_view(photo)

    def _show_grid_view(self) -> None:
        """Switch to grid view."""
        self.stack.setCurrentWidget(self.grid_view)

    def _show_photo_view(self, photo: Photo) -> None:
        """Switch to photo view."""
        self.photo_view.set_photo(photo)
        self._update_navigation_buttons()
        self.stack.setCurrentWidget(self.photo_view)

    def _update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        has_prev = self._current_photo_index > 0
        has_next = self._current_photo_index < len(self._photos) - 1
        self.photo_view.set_navigation_enabled(has_prev, has_next)

    def _navigate_photo(self, direction: int) -> None:
        """Navigate to previous or next photo."""
        new_index = self._current_photo_index + direction
        if 0 <= new_index < len(self._photos):
            self._current_photo_index = new_index
            photo = self._photos[new_index]
            self.photo_view.set_photo(photo)
            self._update_navigation_buttons()

    def _on_caption_changed(self, photo: Photo) -> None:
        """Handle caption change from photo view."""
        self.grid_view.refresh_photo(photo)

    def _generate_pdf(self) -> None:
        """Generate PDF from captioned photos."""
        captioned_photos = self.grid_view.get_captioned_photos()
        folder_path = self.grid_view.get_current_folder()

        if not captioned_photos:
            QMessageBox.warning(
                self,
                "No Captioned Photos",
                "There are no captioned photos to include in the PDF.",
            )
            return

        if not folder_path:
            return

        # Get default filename
        default_name = PDFGenerator.get_default_filename(folder_path.name)

        # Show save dialog
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            default_name,
            "PDF Files (*.pdf)",
        )

        if not save_path:
            return

        # Store folder path for later use
        self._pdf_folder_path = folder_path

        # Show progress dialog
        self._pdf_progress = QProgressDialog(self)
        self._pdf_progress.setLabelText("Generating PDF...")
        self._pdf_progress.setRange(0, len(captioned_photos))
        self._pdf_progress.setValue(0)
        self._pdf_progress.setCancelButton(None)
        self._pdf_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._pdf_progress.show()

        # Generate PDF in background
        settings = self.config.get_pdf_settings()
        self._pdf_worker = PDFGeneratorWorker(captioned_photos, Path(save_path), settings)
        self._pdf_worker.progress.connect(self._on_pdf_progress)
        self._pdf_worker.finished.connect(self._on_pdf_finished)
        self._pdf_worker.error.connect(self._on_pdf_error)
        self._pdf_worker.start()

    def _on_pdf_progress(self, current: int, total: int) -> None:
        """Handle PDF generation progress update."""
        if hasattr(self, "_pdf_progress") and self._pdf_progress:
            self._pdf_progress.setValue(current)
            self._pdf_progress.setLabelText(f"Processing photo {current} of {total}...")

    def _on_pdf_finished(self) -> None:
        """Handle PDF generation completion."""
        if hasattr(self, "_pdf_progress") and self._pdf_progress:
            self._pdf_progress.close()
            self._pdf_progress = None

        # Ask about moving folder (only once)
        if hasattr(self, "_pdf_folder_path") and self._pdf_folder_path:
            folder_path = self._pdf_folder_path
            self._pdf_folder_path = None  # Clear to prevent duplicate dialogs
            self._prompt_move_folder(folder_path)

    def _on_pdf_error(self, error: str) -> None:
        """Handle PDF generation error."""
        if hasattr(self, "_pdf_progress") and self._pdf_progress:
            self._pdf_progress.close()

        QMessageBox.critical(
            self,
            "PDF Generation Failed",
            f"Failed to generate PDF: {error}",
        )

    def _prompt_move_folder(self, folder_path: Path) -> None:
        """Prompt user to move folder to Completed."""
        completed_dir = self.config.completed_photos_dir
        if not completed_dir:
            return

        result = QMessageBox.question(
            self,
            "Move to Completed?",
            f"PDF saved successfully!\n\n"
            f"Would you like to move '{folder_path.name}' to the Completed Photos folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if result == QMessageBox.StandardButton.Yes:
            try:
                # Ensure completed directory exists
                completed_dir.mkdir(parents=True, exist_ok=True)

                # Move folder
                dest = completed_dir / folder_path.name
                shutil.move(str(folder_path), str(dest))

                # Refresh sidebar and clear grid
                self._refresh_sidebar()
                self.grid_view.clear()

                QMessageBox.information(
                    self,
                    "Folder Moved",
                    f"'{folder_path.name}' has been moved to the Completed Photos folder.",
                )

            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Move Failed",
                    f"Failed to move folder: {e}",
                )

    def _show_settings(self) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Refresh sidebar in case directories changed
            self._refresh_sidebar()

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h2>{__app_name__}</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>A desktop application for captioning photos and generating PDF contact sheets.</p>"
            f"<p>© 2024 James Curtin</p>",
        )

    def _check_for_updates(self) -> None:
        """Check for updates in background (skipped in development mode)."""
        if is_development_mode():
            return

        self._update_worker = UpdateWorker()
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _manual_update_check(self) -> None:
        """Manually check for updates."""
        if is_development_mode():
            QMessageBox.information(
                self,
                "Development Mode",
                "Update checking is disabled in development mode.",
            )
            return

        progress = QProgressDialog(self)
        progress.setLabelText("Checking for updates...")
        progress.setRange(0, 0)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        checker = UpdateChecker()
        has_update, version = checker.check_for_updates()
        progress.close()

        if has_update and version:
            self._on_update_available(version, checker.get_release_notes())
        else:
            QMessageBox.information(
                self,
                "No Updates",
                f"You are running the latest version ({__version__}).",
            )

    def _on_update_available(self, version: str, _release_notes: str) -> None:
        """Handle update available notification."""
        result = QMessageBox.question(
            self,
            "Update Available",
            f"A new version ({version}) is available!\n\n"
            f"Current version: {__version__}\n\n"
            f"Would you like to download and install it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if result == QMessageBox.StandardButton.Yes:
            self._download_update()

    def _download_update(self) -> None:
        """Download and install update."""
        progress = QProgressDialog(self)
        progress.setLabelText("Downloading update...")
        progress.setCancelButtonText("Cancel")
        progress.setRange(0, 100)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        checker = UpdateChecker()

        def update_progress(received: int, total: int) -> None:
            if total > 0:
                percent = int(received * 100 / total)
                progress.setValue(percent)

        success = checker.download_and_install(update_progress)
        progress.close()

        if not success:
            QMessageBox.warning(
                self,
                "Update Failed",
                "Failed to download or install the update.\n\n"
                "Please download the update manually from the releases page.",
            )
