"""EXIF metadata utilities for reading and writing photo captions."""

import contextlib
import html
import io
import os
import re
import shutil
import struct
import tempfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.ExifTags import IFD, Base

# IPTC record markers
IPTC_CAPTION_TAG = 0x78  # 2:120 - Caption/Abstract

# HEIF files cannot have metadata edited without re-encoding, so they are
# converted to JPEG once (see convert_heif_to_jpeg) instead of written in place.
HEIF_EXTENSIONS = frozenset({".heic", ".heif"})

# Hidden folder (inside the photo's folder) that receives converted originals
ORIGINALS_DIR_NAME = ".originals"

# Suffix for in-progress writes; must not be a supported image extension
_TEMP_SUFFIX = ".captmp"

_EXIF_HEADER = b"Exif\x00\x00"
_JPEG_MAX_SEGMENT_PAYLOAD = 65533
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_WEBP_EXIF_FLAG = 0x08
_WEBP_ALPHA_FLAG = 0x10
_HEIF_JPEG_QUALITY = 95


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


def _read_caption(img: Image.Image) -> str | None:
    """Read the caption from an open image (EXIF, then IPTC, then XMP)."""
    exif = img.getexif()
    exif_ifd = exif.get_ifd(IFD.Exif)

    raw_comment = exif_ifd.get(Base.UserComment)
    if isinstance(raw_comment, bytes):
        caption = _decode_user_comment(raw_comment)
        clean = caption.strip("\x00 \t\n\r")
        if clean:
            return _decode_html_entities(clean)
    elif isinstance(raw_comment, str):
        clean = raw_comment.strip("\x00 \t\n\r")
        if clean:
            return _decode_html_entities(clean)

    # Try IPTC (stored in photoshop info)
    photoshop = img.info.get("photoshop")
    if isinstance(photoshop, dict):
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

    return None


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
    try:
        with Image.open(image_path) as img:
            return _read_caption(img)
    except Exception:
        return None


def _build_exif(img: Image.Image, caption: str) -> bytes:
    """Return the image's EXIF block with UserComment set, as b"Exif\\0\\0" + TIFF."""
    exif = img.getexif()
    exif.get_ifd(IFD.Exif)[Base.UserComment] = _encode_user_comment(caption)
    return exif.tobytes()


def _splice_jpeg_exif(data: bytes, exif: bytes) -> bytes:
    """Replace the Exif APP1 segment of a JPEG without touching the image data."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("Not a JPEG file")
    if len(exif) > _JPEG_MAX_SEGMENT_PAYLOAD:
        raise ValueError("EXIF block too large for a JPEG APP1 segment")

    segments: list[bytes] = []
    exif_index: int | None = None
    pos = 2
    while True:
        if pos + 4 > len(data) or data[pos] != 0xFF:
            raise ValueError("Malformed JPEG marker")
        # Skip fill bytes before the marker code
        while data[pos + 1] == 0xFF:
            pos += 1
        marker = data[pos + 1]
        if marker == 0xDA:  # SOS - compressed image data follows
            break
        if marker == 0xD9:  # EOI
            raise ValueError("JPEG has no image data")
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:  # Standalone markers
            segments.append(data[pos : pos + 2])
            pos += 2
            continue
        end = pos + 2 + struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        segment = data[pos:end]
        if marker == 0xE1 and segment[4:10] == _EXIF_HEADER:
            if exif_index is None:
                exif_index = len(segments)
        else:
            segments.append(segment)
        pos = end

    if exif_index is None:
        # Exif belongs right after SOI, or after a leading JFIF APP0
        has_jfif = bool(segments) and segments[0][1] == 0xE0 and segments[0][4:9] == b"JFIF\x00"
        exif_index = 1 if has_jfif else 0
    segments.insert(exif_index, b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif)

    # Everything from SOS to end of file is copied verbatim
    return b"\xff\xd8" + b"".join(segments) + data[pos:]


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    """Build a PNG chunk with its CRC."""
    crc = zlib.crc32(chunk_type + payload)
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _splice_png_exif(data: bytes, exif: bytes) -> bytes:
    """Replace the eXIf chunk of a PNG without touching the image data."""
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("Not a PNG file")

    new_chunk = _png_chunk(b"eXIf", exif.removeprefix(_EXIF_HEADER))
    out = [_PNG_SIGNATURE]
    inserted = False
    pos = len(_PNG_SIGNATURE)
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise ValueError("Truncated PNG chunk")
        if chunk_type != b"eXIf":
            # eXIf must precede the image data
            if chunk_type == b"IDAT" and not inserted:
                out.append(new_chunk)
                inserted = True
            out.append(data[pos:end])
        pos = end

    if not inserted:
        raise ValueError("PNG has no image data")
    return b"".join(out)


def _riff_chunk(fourcc: bytes, payload: bytes) -> bytes:
    """Build a RIFF chunk, padded to an even length."""
    padding = b"\x00" if len(payload) % 2 else b""
    return fourcc + struct.pack("<I", len(payload)) + payload + padding


def _splice_webp_exif(data: bytes, exif: bytes, size: tuple[int, int], has_alpha: bool) -> bytes:
    """Replace the EXIF chunk of a WebP without touching the image data."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("Not a WebP file")

    chunks: list[tuple[bytes, bytes]] = []
    riff_end = min(len(data), 8 + struct.unpack("<I", data[4:8])[0])
    pos = 12
    while pos + 8 <= riff_end:
        fourcc = data[pos : pos + 4]
        length = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        payload = data[pos + 8 : pos + 8 + length]
        if len(payload) != length:
            raise ValueError("Truncated WebP chunk")
        if fourcc != b"EXIF":
            chunks.append((fourcc, payload))
        pos += 8 + length + (length % 2)
    if not chunks:
        raise ValueError("WebP has no image data")

    if chunks[0][0] == b"VP8X":
        flags_header = bytearray(chunks[0][1])
        flags_header[0] |= _WEBP_EXIF_FLAG
        chunks[0] = (b"VP8X", bytes(flags_header))
    else:
        # Simple format (VP8/VP8L only): metadata requires the extended header
        flags = _WEBP_EXIF_FLAG | (_WEBP_ALPHA_FLAG if has_alpha else 0)
        width, height = size
        header = (
            bytes([flags, 0, 0, 0])
            + (width - 1).to_bytes(3, "little")
            + (height - 1).to_bytes(3, "little")
        )
        chunks.insert(0, (b"VP8X", header))

    # EXIF goes after the image data and before XMP
    xmp_index = next((i for i, (f, _) in enumerate(chunks) if f == b"XMP "), len(chunks))
    chunks.insert(xmp_index, (b"EXIF", exif.removeprefix(_EXIF_HEADER)))

    body = b"WEBP" + b"".join(_riff_chunk(f, p) for f, p in chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _resave_tiff(img: Image.Image, exif: bytes) -> bytes:
    """Re-save a TIFF with new EXIF, failing unless the pixels are unchanged."""
    if getattr(img, "n_frames", 1) > 1:
        raise ValueError("Multi-page TIFF is not supported")

    # Saved uncompressed: Pillow's libtiff path (used for every compression
    # scheme) cannot write the EXIF sub-IFD. Pixels stay identical either way.
    save_kwargs: dict[str, Any] = {"exif": exif, "compression": "raw"}
    icc_profile = img.info.get("icc_profile")
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    buffer = io.BytesIO()
    img.save(buffer, format="TIFF", **save_kwargs)
    new_data = buffer.getvalue()

    with Image.open(io.BytesIO(new_data)) as check:
        if (check.mode, check.size, check.tobytes()) != (img.mode, img.size, img.tobytes()):
            raise ValueError("TIFF re-save would change pixel data")
    return new_data


def _fsync_directory(directory: Path) -> None:
    """Flush a directory entry to disk (best effort; not supported everywhere)."""
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _atomic_write(target: Path, data: bytes, caption: str, mode_source: Path) -> None:
    """
    Write image bytes to target so a crash never leaves a partial file.

    The data goes to a temp file in the same directory, is flushed to disk and
    checked (opens as an image, caption reads back), then atomically replaces
    the target. On any failure the target is left untouched.
    """
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=_TEMP_SUFFIX, dir=target.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(mode_source, temp_path)

        with Image.open(temp_path) as check:
            written = check.getexif().get_ifd(IFD.Exif).get(Base.UserComment)
        if written != _encode_user_comment(caption):
            raise ValueError("Caption did not read back after write")

        temp_path.replace(target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    _fsync_directory(target.parent)


def set_caption(image_path: Path, caption: str) -> bool:
    """
    Write a caption to an image's EXIF UserComment field.

    Only the metadata changes: JPEG, PNG and WebP have their EXIF block spliced
    in without decoding the image, and TIFF is re-saved only if the pixels are
    unchanged. HEIF is refused (use convert_heif_to_jpeg). The file is replaced
    atomically, so a failed or interrupted save leaves the original intact.

    Args:
        image_path: Path to the image file.
        caption: The caption text to save.

    Returns:
        True if successful, False otherwise.
    """
    try:
        data = image_path.read_bytes()
        with Image.open(io.BytesIO(data)) as img:
            exif = _build_exif(img, caption)
            if img.format == "JPEG":
                new_data = _splice_jpeg_exif(data, exif)
            elif img.format == "PNG":
                new_data = _splice_png_exif(data, exif)
            elif img.format == "WEBP":
                has_alpha = img.mode in ("RGBA", "LA")
                new_data = _splice_webp_exif(data, exif, img.size, has_alpha)
            elif img.format == "TIFF":
                new_data = _resave_tiff(img, exif)
            else:
                return False

        _atomic_write(image_path, new_data, caption, mode_source=image_path)
        return True

    except Exception:
        return False


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """Return a path in directory that no existing file uses, ignoring case."""
    existing = {p.name.lower() for p in directory.iterdir()}
    name = f"{stem}{suffix}"
    counter = 1
    while name.lower() in existing:
        name = f"{stem}-{counter}{suffix}"
        counter += 1
    return directory / name


def convert_heif_to_jpeg(image_path: Path, caption: str) -> Path:
    """
    Convert a HEIC/HEIF photo to JPEG once, with the caption set.

    This is the only lossy step a HEIF photo goes through; later caption edits
    on the JPEG are lossless. The JPEG keeps the EXIF (orientation baked into
    the pixels), ICC profile, XMP and file timestamps. The original is moved
    into the hidden ORIGINALS_DIR_NAME folder only after the JPEG is in place,
    so an interruption can leave a duplicate but never lose the photo.

    Args:
        image_path: Path to the HEIC/HEIF file.
        caption: The caption text to save.

    Returns:
        Path of the new JPEG file.
    """
    expected_size = get_image_dimensions(image_path)
    with Image.open(image_path) as img:
        if img.format != "HEIF":
            raise ValueError(f"Not a HEIF file: {image_path}")
        # pillow-heif applies the rotation and resets EXIF Orientation to 1
        if img.size != expected_size:
            raise ValueError("Decoded HEIF size does not match its orientation")

        exif = img.getexif()
        exif[Base.Orientation] = 1
        exif.get_ifd(IFD.Exif)[Base.UserComment] = _encode_user_comment(caption)

        save_kwargs: dict[str, Any] = {
            "quality": _HEIF_JPEG_QUALITY,
            "subsampling": 0,
            "exif": exif.tobytes(),
        }
        for key in ("icc_profile", "xmp"):
            value = img.info.get(key)
            if value:
                save_kwargs[key] = value

        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", **save_kwargs)

    jpeg_path = _unique_path(image_path.parent, image_path.stem, ".jpg")
    _atomic_write(jpeg_path, buffer.getvalue(), caption, mode_source=image_path)

    # The JPEG now holds the caption. Later steps are best effort: failing here
    # must not make the caller retry and write a second JPEG.
    try:
        shutil.copystat(image_path, jpeg_path)
        originals_dir = image_path.parent / ORIGINALS_DIR_NAME
        originals_dir.mkdir(exist_ok=True)
        image_path.rename(_unique_path(originals_dir, image_path.stem, image_path.suffix))
    except OSError as e:
        print(f"Converted {image_path.name} but could not move the original aside: {e}")

    return jpeg_path


def get_timestamp(image_path: Path) -> datetime | None:
    """
    Read the timestamp from an image's EXIF DateTimeOriginal field.

    Args:
        image_path: Path to the image file.

    Returns:
        The timestamp as a datetime object, or None if not available.
    """
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            exif_ifd = exif.get_ifd(IFD.Exif)

            # Try DateTimeOriginal first, then DateTimeDigitized
            for tag in [Base.DateTimeOriginal, Base.DateTimeDigitized]:
                raw_date = exif_ifd.get(tag)
                if raw_date is not None:
                    if isinstance(raw_date, bytes):
                        raw_date = raw_date.decode("utf-8", errors="ignore")
                    try:
                        return datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue

            # Fallback to 0th IFD DateTime
            raw_date = exif.get(Base.DateTime)
            if raw_date is not None:
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
        with Image.open(image_path) as img:
            exif = img.getexif()
            orientation: int = exif.get(Base.Orientation, 1)
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
        orientation: int = img.getexif().get(Base.Orientation, 1)
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
