"""Upload validation for the disease-risk image endpoint (Module 21).

Mirrors the care Module 16's validation audit (``api/validation.py``)
already established for `/fields`/`/feedback`: real checks, not just
trusting the client's `Content-Type` header or filename extension.
"""
from __future__ import annotations

import io

from agro_mirai.api.errors import ApiError

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(file_storage) -> bytes:
    """Reads and validates an uploaded image ``FileStorage``.

    Checks (in order): present, under the size cap, and actually decodes
    as a real image via Pillow (``Image.open(...).verify()``) — magic-byte/
    content sniffing, not extension/Content-Type trust. Returns the raw
    bytes on success so the caller can write them to a temp file without
    re-reading the stream. Raises ``ApiError`` (400) on any violation.
    """
    if file_storage is None or file_storage.filename == "":
        raise ApiError(400, "BAD_REQUEST", "image file is required")

    data = file_storage.read()
    if not data:
        raise ApiError(400, "BAD_REQUEST", "image file is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)}MB size limit",
        )

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover — Pillow is a required dependency
        raise RuntimeError("Pillow is required for image upload validation") from exc

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            fmt = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise ApiError(400, "BAD_REQUEST", "file is not a valid image") from None

    if fmt not in _ALLOWED_FORMATS:
        raise ApiError(
            400,
            "BAD_REQUEST",
            f"unsupported image format {fmt!r}; allowed: {', '.join(sorted(_ALLOWED_FORMATS))}",
        )

    return data
