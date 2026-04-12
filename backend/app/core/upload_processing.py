from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".gif"}
SCREENSHOT_HINTS = ("screenshot", "screen", "capture", "캡처", "스크린샷")


@dataclass(frozen=True)
class ProcessedImageAsset:
    original_bytes: bytes
    original_ext: str
    optimized_bytes: bytes
    optimized_ext: str
    pdf_bytes: bytes | None
    is_screenshot_like: bool
    width: int
    height: int


def is_image_upload(source_name: str | None, content_type: str | None) -> bool:
    ext = Path(source_name or "upload.bin").suffix.lower()
    content_type_value = (content_type or "").lower()
    return ext in IMAGE_EXTENSIONS or content_type_value.startswith("image/")


def process_uploaded_image(
    content: bytes,
    *,
    source_name: str | None,
    content_type: str | None,
    generate_pdf: bool,
) -> ProcessedImageAsset:
    try:
        from PIL import Image, ImageOps
    except Exception as exc:  # pragma: no cover - dependency contract
        raise RuntimeError("Image upload optimization requires Pillow dependency") from exc

    source_ext = Path(source_name or "upload.bin").suffix.lower() or ".bin"
    image = Image.open(io.BytesIO(content))
    image = ImageOps.exif_transpose(image)

    is_screenshot_like = _is_screenshot_like(image=image, source_name=source_name)
    max_edge = 1920 if is_screenshot_like else 1600
    image = _resize_image(image, max_edge=max_edge)
    normalized = _normalize_image_mode(image)

    optimized_ext = ".png" if is_screenshot_like else ".jpg"
    optimized_bytes = _encode_optimized_image(normalized, optimized_ext=optimized_ext, screenshot_like=is_screenshot_like)
    pdf_bytes = build_images_pdf([optimized_bytes], image_ext=optimized_ext) if generate_pdf else None

    return ProcessedImageAsset(
        original_bytes=content,
        original_ext=source_ext,
        optimized_bytes=optimized_bytes,
        optimized_ext=optimized_ext,
        pdf_bytes=pdf_bytes,
        is_screenshot_like=is_screenshot_like,
        width=normalized.width,
        height=normalized.height,
    )


def build_images_pdf(images: Iterable[bytes], *, image_ext: str | None = None) -> bytes:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - dependency contract
        raise RuntimeError("PDF generation requires Pillow dependency") from exc

    pil_images: list[Image.Image] = []
    for raw in images:
        img = Image.open(io.BytesIO(raw))
        if img.mode != "RGB":
            img = img.convert("RGB")
        pil_images.append(img)

    if not pil_images:
        raise ValueError("at least one image is required")

    out = io.BytesIO()
    first, rest = pil_images[0], pil_images[1:]
    first.save(out, format="PDF", save_all=True, append_images=rest, resolution=150.0)
    return out.getvalue()


def _is_screenshot_like(*, image, source_name: str | None) -> bool:
    lower_name = (source_name or "").lower()
    if any(hint in lower_name for hint in SCREENSHOT_HINTS):
        return True
    source_format = (getattr(image, "format", "") or "").upper()
    if source_format == "PNG":
        return True
    return False


def _resize_image(image, *, max_edge: int):
    if image.width <= max_edge and image.height <= max_edge:
        return image
    try:
        from PIL import Image

        resample = Image.Resampling.LANCZOS
    except AttributeError:  # pragma: no cover - pillow compatibility
        from PIL import Image

        resample = Image.LANCZOS  # type: ignore[attr-defined]
    image.thumbnail((max_edge, max_edge), resample)
    return image


def _normalize_image_mode(image):
    try:
        from PIL import Image
    except Exception:  # pragma: no cover - dependency contract
        return image
    if image.mode in {"RGB", "L"}:
        return image if image.mode == "RGB" else image.convert("RGB")
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in getattr(image, "info", {})):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _encode_optimized_image(image, *, optimized_ext: str, screenshot_like: bool) -> bytes:
    out = io.BytesIO()
    if optimized_ext == ".png":
        image.save(out, format="PNG", optimize=True, compress_level=8)
    else:
        image.save(
            out,
            format="JPEG",
            quality=82,
            optimize=True,
            progressive=True,
            subsampling=0 if screenshot_like else 2,
        )
    return out.getvalue()
