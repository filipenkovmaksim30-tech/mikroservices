from dataclasses import dataclass
from io import BytesIO
import warnings

from PIL import Image, ImageOps


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidProductImageError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class ProcessedProductImage:
    large: bytes
    thumbnail: bytes

def _encode_webp(source: Image.Image, max_side: int) -> bytes:
    image = source.copy()
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    output = BytesIO()

    image.save(output, format="WEBP", quality=82, method=4)
    return output.getvalue()


def proccess_product_image(data: bytes):
    if not data or len(data) > MAX_FILE_BYTES:
        raise InvalidProductImageError("Image must be between 1 byte and 5 MB")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(data)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise InvalidProductImageError(
                        "Only JPEG, PNG and WebP images are allowed"
                    )
                if source.width * source.height > MAX_PIXELS:
                    raise InvalidProductImageError(
                        "Image must not exceed 12 megapixels"
                    )
                if getattr(source, "n_frames", 1) != 1:
                    raise InvalidProductImageError(
                        "Animated images are not supported in the photo gallery"
                    )

                source.load()

                oriented = ImageOps.exif_transpose(source)

                has_alpha = (
                    "A" in oriented.getbands()
                    or "transparency" in oriented.info
                )

                converted = oriented.convert("RGBA" if has_alpha else "RGB")

                clean = Image.new(converted.mode, converted.size)
                clean.paste(converted)

                return ProcessedProductImage(
                    large=_encode_webp(clean, 1600),
                    thumbnail=_encode_webp(clean, 400),
                )
    except InvalidProductImageError:
        raise
    except (
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidProductImageError("Invalid or damaged image") from exc