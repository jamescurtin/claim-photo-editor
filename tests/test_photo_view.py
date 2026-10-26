"""Tests for caption auto-save in the photo view."""

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from claim_photo_editor.models.photo import Photo
from claim_photo_editor.utils.exif import get_caption
from claim_photo_editor.views.photo_view import PhotoView


@pytest.fixture
def photos(photo_directory: Path) -> list[Photo]:
    """Return the three photos of the test folder."""
    return Photo.from_directory(photo_directory / "Estimate Photos" / "TestFolder1")


@pytest.fixture
def view(qtbot: QtBot, photos: list[Photo]) -> PhotoView:
    """Create a photo view showing the first photo, wired to navigate like the app."""
    photo_view = PhotoView()
    qtbot.addWidget(photo_view)
    index = [0]

    def navigate(direction: int) -> None:
        if photo_view.set_photo(photos[index[0] + direction]):
            index[0] += direction

    photo_view.navigate_requested.connect(navigate)
    photo_view.set_photo(photos[0])
    return photo_view


class TestPendingCaptionSave:
    """A caption typed just before leaving the photo must be saved."""

    def test_next_before_autosave(self, view: PhotoView, photos: list[Photo]) -> None:
        """Test that clicking Next before the auto-save timer fires keeps the caption."""
        view.caption_input.setText("Water damage")

        view.next_btn.click()

        assert view.get_photo() is photos[1]
        assert get_caption(photos[0].path) == "Water damage"
        assert get_caption(photos[1].path) is None
        assert view.caption_input.text() == ""

    def test_back_before_autosave(self, qtbot: QtBot, view: PhotoView, photos: list[Photo]) -> None:
        """Test that returning to the grid before the timer fires keeps the caption."""
        view.caption_input.setText("Ceiling stain")

        with qtbot.waitSignal(view.closed, timeout=100):
            view._request_close()

        assert get_caption(photos[0].path) == "Ceiling stain"

    def test_set_photo_flushes(self, view: PhotoView, photos: list[Photo]) -> None:
        """Test that switching photos directly (e.g. from the grid) keeps the caption."""
        view.caption_input.setText("Roof")

        assert view.set_photo(photos[2]) is True

        assert get_caption(photos[0].path) == "Roof"

    def test_failed_save_blocks_navigation(
        self, view: PhotoView, photos: list[Photo], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the view stays on the photo when the pending save fails."""
        monkeypatch.setattr("claim_photo_editor.models.photo.set_caption", lambda *_args: False)
        view.caption_input.setText("Will fail")

        view.next_btn.click()

        assert view.get_photo() is photos[0]
        assert view.caption_input.text() == "Will fail"
        assert view.save_status_label.text() == "Error!"

    def test_failed_autosave_still_blocks_navigation(
        self,
        qtbot: QtBot,
        view: PhotoView,
        photos: list[Photo],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that an edit whose timer-driven save failed is not dropped later."""
        monkeypatch.setattr("claim_photo_editor.models.photo.set_caption", lambda *_args: False)
        view.caption_input.setText("Will fail")
        qtbot.waitUntil(lambda: view.save_status_label.text() == "Error!", timeout=2000)

        view.next_btn.click()
        view.next_btn.click()

        assert view.get_photo() is photos[0]
        assert view.flush_pending_save() is False

    def test_no_pending_edit(self, view: PhotoView, photos: list[Photo]) -> None:
        """Test that navigation without an edit writes nothing."""
        before = photos[0].path.read_bytes()

        view.next_btn.click()

        assert view.get_photo() is photos[1]
        assert photos[0].path.read_bytes() == before
