from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps


def resized_jpeg_bytes(
    content: bytes,
    *,
    max_long_edge: int = 2000,
    quality: int = 88,
) -> bytes:
    """Normalize orientation and return a bounded, web-friendly JPEG."""
    with Image.open(BytesIO(content)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((max_long_edge, max_long_edge), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "JPEG", quality=quality, optimize=True, progressive=True)
    return output.getvalue()
