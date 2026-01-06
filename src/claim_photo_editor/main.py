"""Application entry point."""

import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from claim_photo_editor import __app_name__
from claim_photo_editor.app import MainWindow


def get_resource_path(relative_path: str) -> Path:
    """
    Get the path to a resource file, handling both development and PyInstaller bundles.

    Args:
        relative_path: Path relative to the resources directory.

    Returns:
        Absolute path to the resource file.
    """
    # Check if running as a PyInstaller bundle
    if getattr(sys, "frozen", False):
        # Running as bundled app
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base_path / "claim_photo_editor" / "resources" / relative_path
    else:
        # Running in development
        return Path(__file__).parent / "resources" / relative_path


def main() -> int:
    """Run the application."""
    try:
        app = QApplication(sys.argv)
        app.setApplicationName(__app_name__)
        app.setOrganizationName("jamescurtin")

        # Set application icon
        icon_path = get_resource_path("icon.svg")
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        window = MainWindow()
        window.show()

        exit_code: int = app.exec()
        return exit_code
    except Exception as e:
        # Log any startup errors for debugging
        error_msg = f"Application failed to start:\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)

        # Try to show a dialog if possible
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Startup Error")
            msg.setText(f"Failed to start application:\n{e}")
            msg.exec()
        except Exception:
            pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
