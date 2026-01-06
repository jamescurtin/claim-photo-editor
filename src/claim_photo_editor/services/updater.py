"""Auto-update functionality for checking GitHub releases."""

import logging
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests
from packaging import version

from claim_photo_editor import __github_repo__, __version__

logger = logging.getLogger(__name__)


class UpdateChecker:
    """Checks for application updates from GitHub releases."""

    GITHUB_API_URL = f"https://api.github.com/repos/{__github_repo__}/releases/latest"
    TIMEOUT = 10  # seconds

    def __init__(self) -> None:
        """Initialize the update checker."""
        self.current_version = __version__
        self._latest_release: dict | None = None

    def check_for_updates(self) -> tuple[bool, str | None]:
        """
        Check if a newer version is available.

        Returns:
            Tuple of (update_available, latest_version).
        """
        try:
            response = requests.get(
                self.GITHUB_API_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            self._latest_release = response.json()

            tag_name = self._latest_release.get("tag_name", "")
            # Remove 'v' prefix if present
            latest_version = tag_name.lstrip("v")

            if self._is_newer_version(latest_version):
                return True, latest_version

            return False, latest_version

        except requests.RequestException as e:
            logger.warning(f"Failed to check for updates: {e}")
            return False, None

    def _is_newer_version(self, latest: str) -> bool:
        """
        Compare versions to determine if latest is newer.

        Args:
            latest: The latest version string.

        Returns:
            True if latest is newer than current.
        """
        try:
            result: bool = version.parse(latest) > version.parse(self.current_version)
            return result
        except version.InvalidVersion:
            return False

    def get_download_url(self) -> str | None:
        """
        Get the download URL for the latest macOS release.

        Returns:
            Download URL for the macOS asset, or None if not found.
        """
        if not self._latest_release:
            return None

        assets = self._latest_release.get("assets", [])
        for asset in assets:
            name = asset.get("name", "").lower()
            if "macos" in name or name.endswith(".dmg"):
                url: str | None = asset.get("browser_download_url")
                return url

        return None

    def get_release_notes(self) -> str:
        """
        Get the release notes for the latest version.

        Returns:
            Release notes as a string.
        """
        if not self._latest_release:
            return ""

        body: str = self._latest_release.get("body", "")
        return body

    def download_and_install(
        self, progress_callback: Callable[[int, int], Any] | None = None
    ) -> bool:
        """
        Download and install the latest update.

        Args:
            progress_callback: Optional callback for download progress (received, total).

        Returns:
            True if successful, False otherwise.
        """
        download_url = self.get_download_url()
        if not download_url:
            logger.error("No download URL available")
            return False

        try:
            # Download the update
            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            # Determine file extension
            if download_url.endswith(".dmg"):
                suffix = ".dmg"
            elif download_url.endswith(".zip"):
                suffix = ".zip"
            else:
                suffix = ".dmg"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

                tmp_path = Path(tmp_file.name)

            # Install the update
            return self._install_update(tmp_path)

        except requests.RequestException as e:
            logger.error(f"Failed to download update: {e}")
            return False

    def _install_update(self, download_path: Path) -> bool:
        """
        Install the downloaded update.

        Args:
            download_path: Path to the downloaded file.

        Returns:
            True if successful, False otherwise.
        """
        if sys.platform != "darwin":
            logger.error("Auto-update only supported on macOS")
            return False

        try:
            if download_path.suffix == ".dmg":
                return self._install_from_dmg(download_path)
            elif download_path.suffix == ".zip":
                return self._install_from_zip(download_path)
            else:
                logger.error(f"Unsupported file type: {download_path.suffix}")
                return False
        finally:
            # Clean up download - ignore errors if file is already gone
            download_path.unlink(missing_ok=True)

    def _install_from_dmg(self, dmg_path: Path) -> bool:
        """Install update from a DMG file."""
        try:
            # Mount the DMG
            mount_result = subprocess.run(
                ["hdiutil", "attach", str(dmg_path), "-nobrowse", "-quiet"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Find the mount point
            mount_point = None
            for line in mount_result.stdout.strip().split("\n"):
                if "/Volumes/" in line:
                    match = re.search(r"/Volumes/[^\t\n]+", line)
                    if match:
                        mount_point = Path(match.group())
                        break

            if not mount_point:
                logger.error("Could not find DMG mount point")
                return False

            try:
                # Find the .app bundle
                app_path = None
                for item in mount_point.iterdir():
                    if item.suffix == ".app":
                        app_path = item
                        break

                if not app_path:
                    logger.error("Could not find .app in DMG")
                    return False

                # Get current app location
                current_app = self._get_current_app_path()
                if not current_app:
                    logger.error("Could not determine current app location")
                    return False

                # Copy new app to Applications
                dest_app = current_app.parent / app_path.name
                subprocess.run(
                    ["rm", "-rf", str(dest_app)],
                    check=True,
                )
                subprocess.run(
                    ["cp", "-R", str(app_path), str(dest_app)],
                    check=True,
                )

                # Relaunch the app
                self._relaunch_app(dest_app)
                return True

            finally:
                # Unmount the DMG
                subprocess.run(
                    ["hdiutil", "detach", str(mount_point), "-quiet"],
                    check=False,
                    capture_output=True,
                )

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install from DMG: {e}")
            return False

    def _install_from_zip(self, zip_path: Path) -> bool:
        """Install update from a ZIP file."""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)

                # Extract ZIP
                subprocess.run(
                    ["unzip", "-q", str(zip_path), "-d", str(tmp_path)],
                    check=True,
                )

                # Find the .app bundle
                app_path = None
                for item in tmp_path.iterdir():
                    if item.suffix == ".app":
                        app_path = item
                        break

                if not app_path:
                    logger.error("Could not find .app in ZIP")
                    return False

                # Get current app location
                current_app = self._get_current_app_path()
                if not current_app:
                    logger.error("Could not determine current app location")
                    return False

                # Copy new app
                dest_app = current_app.parent / app_path.name
                subprocess.run(
                    ["rm", "-rf", str(dest_app)],
                    check=True,
                )
                subprocess.run(
                    ["cp", "-R", str(app_path), str(dest_app)],
                    check=True,
                )

                # Relaunch the app
                self._relaunch_app(dest_app)
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install from ZIP: {e}")
            return False

    def _get_current_app_path(self) -> Path | None:
        """Get the path to the current .app bundle."""
        # Check if running from an app bundle
        executable = Path(sys.executable)

        # Look for .app in the path
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent

        # Fallback to /Applications
        return Path("/Applications/Claim Photo Editor.app")

    def _relaunch_app(self, app_path: Path) -> None:
        """Relaunch the application."""
        subprocess.Popen(
            ["open", "-n", str(app_path)],
            start_new_session=True,
        )
        sys.exit(0)
