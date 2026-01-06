"""Sidebar widget for folder navigation."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    """Sidebar widget showing folder structure for navigation."""

    folder_selected = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the sidebar."""
        super().__init__(parent)
        self._setup_ui()
        self._estimate_dir: Path | None = None

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QLabel("Folders")
        header.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(header)

        # Tree widget for folders
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        # Only use itemClicked for user-initiated selection
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        self.setMinimumWidth(200)
        self.setMaximumWidth(300)

    def set_estimate_directory(self, path: Path) -> None:
        """
        Set the Estimate Photos directory and refresh the folder list.

        Args:
            path: Path to the Estimate Photos directory.
        """
        self._estimate_dir = path
        self.refresh()

    def refresh(self) -> None:
        """Refresh the folder list from the filesystem."""
        # Remember current selection to restore after refresh
        current_selection = self.get_selected_folder()

        self.tree.clear()

        if not self._estimate_dir or not self._estimate_dir.exists():
            return

        # Add subfolders
        folders = sorted(
            [f for f in self._estimate_dir.iterdir() if f.is_dir()],
            key=lambda f: f.name.lower(),
        )

        for folder in folders:
            item = QTreeWidgetItem([folder.name])
            item.setData(0, Qt.ItemDataRole.UserRole, folder)
            self.tree.addTopLevelItem(item)

        # Restore selection if folder still exists
        if current_selection:
            self.select_folder(current_selection)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handle folder item click."""
        folder_path = item.data(0, Qt.ItemDataRole.UserRole)
        if folder_path:
            self.folder_selected.emit(folder_path)

    def select_folder(self, folder_path: Path) -> None:
        """
        Programmatically select a folder in the tree.

        Args:
            folder_path: Path to the folder to select.
        """
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item and item.data(0, Qt.ItemDataRole.UserRole) == folder_path:
                self.tree.setCurrentItem(item)
                break

    def get_selected_folder(self) -> Path | None:
        """Get the currently selected folder path."""
        item = self.tree.currentItem()
        if item:
            folder_path: Path | None = item.data(0, Qt.ItemDataRole.UserRole)
            return folder_path
        return None
