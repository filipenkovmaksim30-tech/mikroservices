from io import BytesIO

import pytest
from PIL import Image

from catalog_service.media.image_processing import (
    MAX_FILE_BYTES,
    InvalidProductImageError,
    process_product_image,
)


def image_bytes(format_name: str, size: tuple[int, int] = (80, 40)) -> bytes:
    image = Image.new("RGB", size, "red")
    output = BytesIO()
    image.save(output, format=format_name)
    return output.getvalue()


def test_jpeg_becomes_two_webp_versions_without_upscaling() -> None:
    result = process_product_image(image_bytes("JPEG"))

    for data in (result.large, result.thumbnail):
        with Image.open(BytesIO(data)) as image:
            assert image.format == "WEBP"
            assert image.size == (80, 40)


def test_large_image_is_resized_to_both_limits() -> None:
    result = process_product_image(image_bytes("PNG", (2000, 1000)))

    with Image.open(BytesIO(result.large)) as large:
        assert large.size == (1600, 800)
    with Image.open(BytesIO(result.thumbnail)) as thumbnail:
        assert thumbnail.size == (400, 200)


def test_png_transparency_survives_conversion() -> None:
    source = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
    output = BytesIO()
    source.save(output, format="PNG")

    result = process_product_image(output.getvalue())

    with Image.open(BytesIO(result.thumbnail)) as thumbnail:
        assert thumbnail.mode == "RGBA"
        assert thumbnail.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(
    "data",
    [b"", b"not an image", b"x" * (MAX_FILE_BYTES + 1)],
    ids=["empty", "invalid", "oversized"],
)
def test_empty_invalid_or_oversized_input_is_rejected(data: bytes) -> None:
    with pytest.raises(InvalidProductImageError):
        process_product_image(data)


def test_more_than_twelve_megapixels_is_rejected() -> None:
    with pytest.raises(InvalidProductImageError, match="12 megapixels"):
        process_product_image(image_bytes("PNG", (4000, 3001)))


def test_animated_webp_is_rejected() -> None:
    first = Image.new("RGB", (4, 4), "red")
    second = Image.new("RGB", (4, 4), "blue")
    output = BytesIO()
    first.save(output, format="WEBP", save_all=True, append_images=[second], duration=100)

    with pytest.raises(InvalidProductImageError, match="Animated images"):
        process_product_image(output.getvalue())
