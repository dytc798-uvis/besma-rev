from __future__ import annotations

import io

from PIL import Image

from app.core.upload_processing import build_images_pdf, process_uploaded_image


def _make_image_bytes(*, size: tuple[int, int], color: tuple[int, int, int], image_format: str) -> bytes:
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    image.save(out, format=image_format)
    return out.getvalue()


def test_process_uploaded_image_resizes_photo_and_generates_pdf():
    raw = _make_image_bytes(size=(4032, 3024), color=(180, 120, 90), image_format="JPEG")

    asset = process_uploaded_image(
        raw,
        source_name="mobile_photo.jpg",
        content_type="image/jpeg",
        generate_pdf=True,
    )

    assert asset.optimized_ext == ".jpg"
    assert asset.width <= 1600
    assert asset.height <= 1600
    assert asset.pdf_bytes is not None
    assert asset.pdf_bytes.startswith(b"%PDF")


def test_process_uploaded_image_keeps_screenshot_like_asset_as_png():
    raw = _make_image_bytes(size=(2400, 1350), color=(255, 255, 255), image_format="PNG")

    asset = process_uploaded_image(
        raw,
        source_name="screen_capture.png",
        content_type="image/png",
        generate_pdf=False,
    )

    assert asset.is_screenshot_like is True
    assert asset.optimized_ext == ".png"
    assert asset.width <= 1920
    assert asset.height <= 1920


def test_build_images_pdf_creates_multi_page_bundle():
    first = _make_image_bytes(size=(1200, 800), color=(200, 50, 50), image_format="JPEG")
    second = _make_image_bytes(size=(1200, 800), color=(50, 50, 200), image_format="JPEG")

    bundle = build_images_pdf([first, second])

    assert bundle.startswith(b"%PDF")
    assert len(bundle) > 1000
