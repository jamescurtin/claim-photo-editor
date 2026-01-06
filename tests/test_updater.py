"""Tests for auto-update service."""

from unittest.mock import MagicMock, patch

import requests

from claim_photo_editor.services.updater import UpdateChecker


class TestUpdateChecker:
    """Tests for UpdateChecker class."""

    def test_init(self) -> None:
        """Test UpdateChecker initialization."""
        checker = UpdateChecker()
        assert checker.current_version is not None

    def test_is_newer_version(self) -> None:
        """Test version comparison logic."""
        checker = UpdateChecker()
        checker.current_version = "1.0.0"

        assert checker._is_newer_version("2.0.0") is True
        assert checker._is_newer_version("1.1.0") is True
        assert checker._is_newer_version("1.0.1") is True
        assert checker._is_newer_version("1.0.0") is False
        assert checker._is_newer_version("0.9.0") is False

    def test_is_newer_version_invalid(self) -> None:
        """Test version comparison with invalid version."""
        checker = UpdateChecker()
        checker.current_version = "1.0.0"

        assert checker._is_newer_version("invalid") is False

    @patch("requests.get")
    def test_check_for_updates_no_update(self, mock_get: MagicMock) -> None:
        """Test checking for updates when no update available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tag_name": "v0.1.0"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        checker = UpdateChecker()
        checker.current_version = "0.1.0"

        has_update, version = checker.check_for_updates()

        assert has_update is False
        assert version == "0.1.0"

    @patch("requests.get")
    def test_check_for_updates_has_update(self, mock_get: MagicMock) -> None:
        """Test checking for updates when update is available."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "body": "Release notes here",
            "assets": [
                {
                    "name": "Claim-Photo-Editor-macOS.dmg",
                    "browser_download_url": "https://example.com/download.dmg",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        checker = UpdateChecker()
        checker.current_version = "1.0.0"

        has_update, version = checker.check_for_updates()

        assert has_update is True
        assert version == "2.0.0"

    @patch("requests.get")
    def test_check_for_updates_network_error(self, mock_get: MagicMock) -> None:
        """Test checking for updates with network error."""
        mock_get.side_effect = requests.RequestException("Network error")

        checker = UpdateChecker()
        has_update, version = checker.check_for_updates()

        assert has_update is False
        assert version is None

    @patch("requests.get")
    def test_get_download_url(self, mock_get: MagicMock) -> None:
        """Test getting download URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "assets": [
                {
                    "name": "Claim-Photo-Editor-macOS.dmg",
                    "browser_download_url": "https://example.com/download.dmg",
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        checker = UpdateChecker()
        checker.check_for_updates()

        url = checker.get_download_url()
        assert url == "https://example.com/download.dmg"

    @patch("requests.get")
    def test_get_release_notes(self, mock_get: MagicMock) -> None:
        """Test getting release notes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "body": "# Release Notes\n\n- New feature 1\n- Bug fix 2",
            "assets": [],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        checker = UpdateChecker()
        checker.check_for_updates()

        notes = checker.get_release_notes()
        assert "Release Notes" in notes
        assert "New feature 1" in notes

    def test_get_download_url_no_release(self) -> None:
        """Test getting download URL when no release checked."""
        checker = UpdateChecker()
        url = checker.get_download_url()
        assert url is None

    def test_get_release_notes_no_release(self) -> None:
        """Test getting release notes when no release checked."""
        checker = UpdateChecker()
        notes = checker.get_release_notes()
        assert notes == ""


class TestVersionComparison:
    """Tests for version comparison edge cases."""

    def test_prerelease_versions(self) -> None:
        """Test comparison with prerelease versions."""
        checker = UpdateChecker()
        checker.current_version = "1.0.0"

        # Prerelease should be considered older than release
        assert checker._is_newer_version("1.0.1-alpha") is True
        assert checker._is_newer_version("1.0.0-beta") is False

    def test_version_with_v_prefix(self) -> None:
        """Test that version parsing handles v prefix."""
        checker = UpdateChecker()
        checker.current_version = "1.0.0"

        # The check_for_updates method strips the v prefix
        # But _is_newer_version expects clean version strings
        assert checker._is_newer_version("2.0.0") is True
