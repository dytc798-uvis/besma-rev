from io import BytesIO

from PIL import Image

from app.core.image_storage import resized_jpeg_bytes


def test_resized_jpeg_bytes_bounds_long_edge_and_reduces_payload():
    source = BytesIO()
    Image.new("RGB", (4200, 2800), "white").save(source, "PNG")
    result = resized_jpeg_bytes(source.getvalue(), max_long_edge=2000, quality=88)
    with Image.open(BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.size == (2000, 1333)
    assert len(result) < len(source.getvalue())
