"""EXIF metadata utilities for reading and writing photo captions."""

import html
import re
from datetime import datetime
from pathlib import Path

import piexif
from PIL import Image

# IPTC record markers
IPTC_CAPTION_TAG = 0x78  # 2:120 - Caption/Abstract


def _decode_html_entities(text: str) -> str:
    """Decode HTML entities like &amp; to their character equivalents."""
    return html.unescape(text)


def _extract_iptc_caption(iptc_data: bytes) -> str | None:
    """Extract caption from IPTC data block."""
    # IPTC format: 0x1c (marker) + record + dataset + size (1 or 2 bytes) + data
    i = 0
    while i < len(iptc_data) - 4:
        if iptc_data[i] == 0x1C:
            record = iptc_data[i + 1]
            dataset = iptc_data[i + 2]
            size_byte = iptc_data[i + 3]

            # Size can be 1 byte (if < 128) or 2 bytes (if high bit set)
            if size_byte & 0x80:
                # Extended size - 2 bytes
                size = ((size_byte & 0x7F) << 8) + iptc_data[i + 4]
                data_start = i + 5
            else:
                # Single byte size
                size = size_byte
                data_start = i + 4

            if record == 0x02 and dataset == IPTC_CAPTION_TAG:  # Record 2, Caption/Abstract
                caption_bytes = iptc_data[data_start : data_start + size]
                try:
                    return caption_bytes.decode("utf-8", errors="replace").strip()
                except Exception:
                    return caption_bytes.decode("latin-1", errors="replace").strip()

            i = data_start + size
        else:
            i += 1
    return None


def _extract_xmp_description(xmp_data: bytes) -> str | None:
    """Extract description from XMP data."""
    try:
        xmp_str = xmp_data.decode("utf-8", errors="replace")
        # Look for dc:description content
        # Pattern matches: <dc:description>...<rdf:li...>CAPTION</rdf:li>...</dc:description>
        match = re.search(
            r"<dc:description[^>]*>.*?<rdf:li[^>]*>([^<]+)</rdf:li>",
            xmp_str,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return None


def _decode_user_comment(data: bytes) -> str:
    """Decode EXIF UserComment field which may have a character code prefix."""
    if len(data) < 8:
        return data.decode("utf-8", errors="ignore").strip()

    # Check for character code prefix (8 bytes)
    prefix = data[:8]

    if prefix == b"UNICODE\x00":
        # UTF-16 encoded
        return data[8:].decode("utf-16", errors="ignore").strip()
    elif prefix == b"ASCII\x00\x00\x00":
        # ASCII encoded
        return data[8:].decode("ascii", errors="ignore").strip()
    elif prefix == b"JIS\x00\x00\x00\x00\x00":
        # JIS encoded (Japanese)
        return data[8:].decode("shift_jis", errors="ignore").strip()
    elif prefix == b"\x00\x00\x00\x00\x00\x00\x00\x00":
        # Undefined, try UTF-8
        return data[8:].decode("utf-8", errors="ignore").strip()
    else:
        # No prefix, try UTF-8
        return data.decode("utf-8", errors="ignore").strip()


def _encode_user_comment(text: str) -> bytes:
    """Encode a string for EXIF UserComment field with ASCII prefix."""
    # Use ASCII prefix for maximum compatibility
    prefix = b"ASCII\x00\x00\x00"
    return prefix + text.encode("ascii", errors="replace")


def get_caption(image_path: Path) -> str | None:
    """
    Read the caption from an image's metadata.

    Checks multiple sources in order of priority:
    1. EXIF UserComment field
    2. IPTC Caption/Abstract field
    3. XMP dc:description field

    Args:
        image_path: Path to the image file.

    Returns:
        The caption string, or None if no caption is set.
    """
    # Try EXIF UserComment first
    try:
        exif_dict = piexif.load(str(image_path))
        exif_data = exif_dict.get("Exif", {})

        if piexif.ExifIFD.UserComment in exif_data:
            raw_comment = exif_data[piexif.ExifIFD.UserComment]
            if isinstance(raw_comment, bytes):
                caption = _decode_user_comment(raw_comment)
                # Check if caption contains actual content (not just whitespace/nulls)
                if caption and caption.strip("\x00 \t\n\r"):
                    return _decode_html_entities(caption.strip("\x00 \t\n\r"))
            elif isinstance(raw_comment, str):
                caption = raw_comment.strip("\x00 \t\n\r")
                if caption:
                    return _decode_html_entities(caption)
    except Exception:
        pass

    # Try IPTC and XMP via PIL
    try:
        with Image.open(image_path) as img:
            # Try IPTC (stored in photoshop info)
            photoshop = img.info.get("photoshop")
            if isinstance(photoshop, dict):
                # IPTC is typically in key 1028
                iptc_data = photoshop.get(1028)
                if isinstance(iptc_data, bytes):
                    iptc_caption = _extract_iptc_caption(iptc_data)
                    if iptc_caption:
                        return _decode_html_entities(iptc_caption)

            # Try XMP
            xmp_data = img.info.get("xmp")
            if isinstance(xmp_data, bytes):
                xmp_caption = _extract_xmp_description(xmp_data)
                if xmp_caption:
                    return _decode_html_entities(xmp_caption)
    except Exception:
        pass

    return None


def set_caption(image_path: Path, caption: str) -> bool:
    """
    Write a caption to an image's EXIF UserComment field.

    Args:
        image_path: Path to the image file.
        caption: The caption text to save.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Load existing EXIF data or create new
        try:
            exif_dict = piexif.load(str(image_path))
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # Ensure Exif dict exists
        if "Exif" not in exif_dict:
            exif_dict["Exif"] = {}

        # Set the UserComment field
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = _encode_user_comment(caption)

        # Dump to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Open and save image with new EXIF
        with Image.open(image_path) as img:
            # Preserve original format
            img_format = img.format or "JPEG"

            # Save with EXIF data
            img.save(str(image_path), format=img_format, exif=exif_bytes, quality=95)

        return True

    except Exception:
        return False


def get_timestamp(image_path: Path) -> datetime | None:
    """
    Read the timestamp from an image's EXIF DateTimeOriginal field.

    Args:
        image_path: Path to the image file.

    Returns:
        The timestamp as a datetime object, or None if not available.
    """
    try:
        exif_dict = piexif.load(str(image_path))
        exif_data = exif_dict.get("Exif", {})

        # Try DateTimeOriginal first, then DateTimeDigitized
        for tag in [piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized]:
            if tag in exif_data:
                raw_date = exif_data[tag]
                if isinstance(raw_date, bytes):
                    raw_date = raw_date.decode("utf-8", errors="ignore")

                # Parse EXIF date format: "YYYY:MM:DD HH:MM:SS"
                try:
                    return datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue

        # Fallback to 0th IFD DateTime
        zeroth = exif_dict.get("0th", {})
        if piexif.ImageIFD.DateTime in zeroth:
            raw_date = zeroth[piexif.ImageIFD.DateTime]
            if isinstance(raw_date, bytes):
                raw_date = raw_date.decode("utf-8", errors="ignore")
            try:
                return datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass

    except Exception:
        pass

    # Fallback to file modification time
    try:
        stat = image_path.stat()
        return datetime.fromtimestamp(stat.st_mtime)
    except Exception:
        return None


def get_image_orientation(image_path: Path) -> int:
    """
    Get the EXIF orientation of an image.

    Args:
        image_path: Path to the image file.

    Returns:
        EXIF orientation value (1-8), or 1 if not found.
    """
    try:
        exif_dict = piexif.load(str(image_path))
        zeroth = exif_dict.get("0th", {})
        orientation: int = zeroth.get(piexif.ImageIFD.Orientation, 1)
        return orientation
    except Exception:
        return 1


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """
    Get the dimensions of an image, accounting for EXIF orientation.

    Args:
        image_path: Path to the image file.

    Returns:
        Tuple of (width, height) in pixels.
    """
    with Image.open(image_path) as img:
        width, height = img.size

        # Check orientation - some orientations swap width/height
        orientation = get_image_orientation(image_path)
        if orientation in (5, 6, 7, 8):
            width, height = height, width

        return width, height


def is_landscape(image_path: Path) -> bool:
    """
    Check if an image is in landscape orientation.

    Args:
        image_path: Path to the image file.

    Returns:
        True if width > height, False otherwise.
    """
    width, height = get_image_dimensions(image_path)
    return width > height
