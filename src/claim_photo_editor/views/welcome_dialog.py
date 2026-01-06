"""Welcome dialog for first-time setup."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from claim_photo_editor import __app_name__


class WelcomeDialog(QDialog):
    """Welcome dialog for first-time directory configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the welcome dialog."""
        super().__init__(parent)
        self._new_photos_dir: Path | None = None
        self._completed_photos_dir: Path | None = None
        self._setup_ui()

    def _create_welcome_section(self) -> QLabel:
        """Create the welcome message section."""
        welcome_label = QLabel(
            f"<h2>Welcome to {__app_name__}!</h2>"
            "<p>This application helps you caption photos and generate PDF contact sheets.</p>"
            "<p>To get started, please select the folders where your photos are stored:</p>"
        )
        welcome_label.setWordWrap(True)
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return welcome_label

    def _create_new_photos_section(self) -> QVBoxLayout:
        """Create the new photos folder selection section."""
        new_photos_group = QVBoxLayout()
        new_photos_label = QLabel("<b>New Photos Folder</b>")
        new_photos_label.setToolTip("The folder containing photos that need to be captioned")
        new_photos_group.addWidget(new_photos_label)

        new_photos_desc = QLabel(
            "<i>Select the folder containing photos that need to be captioned.</i>"
        )
        new_photos_desc.setStyleSheet("color: gray;")
        new_photos_desc.setWordWrap(True)
        new_photos_group.addWidget(new_photos_desc)

        new_photos_row = QHBoxLayout()
        self.new_photos_input = QLineEdit()
        self.new_photos_input.setPlaceholderText("No folder selected")
        self.new_photos_input.setReadOnly(True)
        new_photos_row.addWidget(self.new_photos_input)

        new_photos_btn = QPushButton("Browse...")
        new_photos_btn.clicked.connect(self._browse_new_photos)
        new_photos_row.addWidget(new_photos_btn)
        new_photos_group.addLayout(new_photos_row)

        return new_photos_group

    def _create_completed_photos_section(self) -> QVBoxLayout:
        """Create the completed photos folder selection section."""
        completed_group = QVBoxLayout()
        completed_label = QLabel("<b>Completed Photos Folder</b>")
        completed_label.setToolTip("The folder where completed photo sets will be moved")
        completed_group.addWidget(completed_label)

        completed_desc = QLabel(
            "<i>Select the folder where completed photo sets will be moved after "
            "generating a PDF.</i>"
        )
        completed_desc.setStyleSheet("color: gray;")
        completed_desc.setWordWrap(True)
        completed_group.addWidget(completed_desc)

        completed_row = QHBoxLayout()
        self.completed_input = QLineEdit()
        self.completed_input.setPlaceholderText("No folder selected")
        self.completed_input.setReadOnly(True)
        completed_row.addWidget(self.completed_input)

        completed_btn = QPushButton("Browse...")
        completed_btn.clicked.connect(self._browse_completed_photos)
        completed_row.addWidget(completed_btn)
        completed_group.addLayout(completed_row)

        return completed_group

    def _create_button_section(self) -> QHBoxLayout:
        """Create the dialog buttons section."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setDefault(True)
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.continue_btn)

        return button_layout

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.setWindowTitle(f"Welcome to {__app_name__}")
        self.setMinimumWidth(550)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        layout.addWidget(self._create_welcome_section())
        layout.addLayout(self._create_new_photos_section())
        layout.addLayout(self._create_completed_photos_section())
        layout.addStretch()
        layout.addLayout(self._create_button_section())

    def _browse_new_photos(self) -> None:
        """Browse for new photos directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select New Photos Folder",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self._new_photos_dir = Path(directory)
            self.new_photos_input.setText(directory)
            self._update_continue_button()

    def _browse_completed_photos(self) -> None:
        """Browse for completed photos directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Completed Photos Folder",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self._completed_photos_dir = Path(directory)
            self.completed_input.setText(directory)
            self._update_continue_button()

    def _update_continue_button(self) -> None:
        """Enable continue button when both directories are selected."""
        self.continue_btn.setEnabled(
            self._new_photos_dir is not None and self._completed_photos_dir is not None
        )

    def get_new_photos_dir(self) -> Path | None:
        """Get the selected new photos directory."""
        return self._new_photos_dir

    def get_completed_photos_dir(self) -> Path | None:
        """Get the selected completed photos directory."""
        return self._completed_photos_dir
