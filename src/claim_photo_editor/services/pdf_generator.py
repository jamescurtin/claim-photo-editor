"""PDF contact sheet generation service."""

import contextlib
import io
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import landscape, letter, portrait
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from claim_photo_editor.config import ImageQuality, Orientation

if TYPE_CHECKING:
    from collections.abc import Callable

    from claim_photo_editor.config import PDFSettings
    from claim_photo_editor.models.photo import Photo


class PDFGenerator:
    """Generates PDF contact sheets from photos."""

    def __init__(self, settings: "PDFSettings") -> None:
        """
        Initialize the PDF generator with settings.

        Args:
            settings: PDF generation settings.
        """
        self.settings = settings

    def _get_page_size(self) -> tuple[float, float]:
        """Get the page size based on orientation."""
        if self.settings.orientation == Orientation.LANDSCAPE:
            page_size: tuple[float, float] = landscape(letter)
        else:
            page_size = portrait(letter)
        return page_size

    def _get_image_quality(self) -> int:
        """Get JPEG quality based on settings."""
        quality_map = {
            ImageQuality.LOW: 50,
            ImageQuality.MEDIUM: 70,
            ImageQuality.HIGH: 90,
        }
        return quality_map.get(self.settings.image_quality, 70)

    def _resize_image_for_pdf(
        self, image_path: Path, max_width: float, max_height: float
    ) -> io.BytesIO:
        """
        Resize an image for PDF inclusion with optimized file size.

        Args:
            image_path: Path to the source image.
            max_width: Maximum width in points.
            max_height: Maximum height in points.

        Returns:
            BytesIO buffer containing the resized JPEG image.
        """
        with Image.open(image_path) as original_img:
            # Convert to RGB if necessary
            if original_img.mode in ("RGBA", "P"):
                processed_img = original_img.convert("RGB")
            else:
                processed_img = original_img.copy()

            # Apply EXIF orientation
            with contextlib.suppress(Exception):
                processed_img = ImageOps.exif_transpose(processed_img)

            # Calculate target size based on DPI
            target_width = int(max_width * self.settings.dpi / 72)
            target_height = int(max_height * self.settings.dpi / 72)

            # Calculate scaling to fit within bounds while preserving aspect ratio
            img_width, img_height = processed_img.size
            width_ratio = target_width / img_width
            height_ratio = target_height / img_height
            scale = min(width_ratio, height_ratio)

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            # Resize image
            resized_img = processed_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save to buffer
            buffer = io.BytesIO()
            resized_img.save(
                buffer, format="JPEG", quality=self._get_image_quality(), optimize=True
            )
            buffer.seek(0)

            return buffer

    def _calculate_optimal_rotation(
        self, photo: "Photo", cell_width: float, cell_height: float
    ) -> bool:
        """
        Determine if an image should be rotated to maximize size.

        Args:
            photo: The photo to check.
            cell_width: Available cell width.
            cell_height: Available cell height (for image only, not caption).

        Returns:
            True if the image should be rotated 90 degrees.
        """
        img_width, img_height = photo.width, photo.height

        # Calculate scale without rotation
        scale_normal = min(cell_width / img_width, cell_height / img_height)
        area_normal = (img_width * scale_normal) * (img_height * scale_normal)

        # Calculate scale with rotation
        scale_rotated = min(cell_width / img_height, cell_height / img_width)
        area_rotated = (img_height * scale_rotated) * (img_width * scale_rotated)

        return area_rotated > area_normal

    def _get_font_size_for_caption(
        self, caption: str, max_width: float, max_height: float, c: canvas.Canvas
    ) -> float:
        """
        Calculate optimal font size for a caption to fit within bounds.

        Args:
            caption: The caption text.
            max_width: Maximum width for the caption.
            max_height: Maximum height for the caption.
            c: Canvas for font metrics.

        Returns:
            Optimal font size in points.
        """
        font_name = self.settings.font_family

        # Start with a reasonable font size and decrease if needed
        for font_size in range(12, 4, -1):
            c.setFont(font_name, font_size)

            # Calculate text width
            text_width = c.stringWidth(caption, font_name, font_size)

            # Check if text fits
            if text_width <= max_width and font_size <= max_height:
                return float(font_size)

        return 6.0  # Minimum font size

    def _draw_photo_cell(
        self,
        c: canvas.Canvas,
        photo: "Photo",
        cell_x: float,
        cell_y: float,
        cell_width: float,
        image_height: float,
        caption_height: float,
    ) -> None:
        """Draw a single photo cell with image and caption."""
        should_rotate = self._calculate_optimal_rotation(photo, cell_width - 8, image_height)

        # Load and resize image
        img_buffer = self._resize_image_for_pdf(photo.path, cell_width - 8, image_height)
        img_reader = ImageReader(img_buffer)
        img_width_actual, img_height_actual = img_reader.getSize()

        # Calculate scaled dimensions to fit cell
        if should_rotate:
            w_ratio = (cell_width - 8) / img_height_actual
            h_ratio = image_height / img_width_actual
            scale = min(w_ratio, h_ratio)
            draw_width = img_height_actual * scale
            draw_height = img_width_actual * scale
        else:
            w_ratio = (cell_width - 8) / img_width_actual
            h_ratio = image_height / img_height_actual
            scale = min(w_ratio, h_ratio)
            draw_width = img_width_actual * scale
            draw_height = img_height_actual * scale

        # Center image in cell
        img_x = cell_x + (cell_width - draw_width) / 2
        img_y = cell_y + caption_height + 4 + (image_height - draw_height) / 2

        # Draw image
        if should_rotate:
            c.saveState()
            c.translate(img_x + draw_width / 2, img_y + draw_height / 2)
            c.rotate(90)
            c.drawImage(
                img_reader,
                -draw_height / 2,
                -draw_width / 2,
                width=draw_height,
                height=draw_width,
            )
            c.restoreState()
        else:
            c.drawImage(img_reader, img_x, img_y, width=draw_width, height=draw_height)

        # Draw caption
        caption = photo.caption or ""
        font_size = self._get_font_size_for_caption(caption, cell_width - 8, caption_height, c)
        c.setFont(self.settings.font_family, font_size)

        # Center caption below image
        text_width = c.stringWidth(caption, self.settings.font_family, font_size)
        text_x = cell_x + (cell_width - text_width) / 2
        text_y = cell_y + 4

        c.drawString(text_x, text_y, caption)

    def generate(
        self,
        photos: list["Photo"],
        output_path: Path,
        progress_callback: "Callable[[int, int], None] | None" = None,
    ) -> None:
        """
        Generate a PDF contact sheet from photos.

        Only photos with captions are included.

        Args:
            photos: List of Photo objects.
            output_path: Path for the output PDF.
            progress_callback: Optional callback(current, total) for progress updates.
        """
        captioned_photos = [p for p in photos if p.has_caption]
        if not captioned_photos:
            raise ValueError("No captioned photos to include in PDF")

        total_photos = len(captioned_photos)

        page_width, page_height = self._get_page_size()

        # Calculate margins and layout
        margin_top = self.settings.margin_top * inch
        margin_left = self.settings.margin_left * inch
        available_width = page_width - margin_left - self.settings.margin_right * inch
        available_height = page_height - margin_top - self.settings.margin_bottom * inch

        rows, cols = self.settings.rows, self.settings.columns
        cell_width = available_width / cols
        cell_height = available_height / rows
        caption_height = min(cell_height * 0.15, 20)
        image_height = cell_height - caption_height - 4

        c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
        photos_per_page = rows * cols
        processed = 0

        for page_num in range((len(captioned_photos) + photos_per_page - 1) // photos_per_page):
            if page_num > 0:
                c.showPage()

            start_idx = page_num * photos_per_page
            page_photos = captioned_photos[start_idx : start_idx + photos_per_page]

            for idx, photo in enumerate(page_photos):
                row, col = idx // cols, idx % cols
                cell_x = margin_left + col * cell_width
                cell_y = page_height - margin_top - (row + 1) * cell_height

                self._draw_photo_cell(
                    c, photo, cell_x, cell_y, cell_width, image_height, caption_height
                )

                processed += 1
                if progress_callback:
                    progress_callback(processed, total_photos)

        c.save()

    @staticmethod
    def get_default_filename(folder_name: str) -> str:
        """
        Get the default PDF filename for a folder.

        Args:
            folder_name: Name of the photo folder.

        Returns:
            Default PDF filename.
        """
        return f"{folder_name} Photos.pdf"
