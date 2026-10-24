"""Image validation, quality checks and normalisation for multimodal input.

Handles the edge cases required by the test plan: wrong file types, empty uploads,
oversized files, corrupted / truncated ("incomplete") images, tiny images, and
dark / low-contrast / blurry photos (reported as warnings, not errors).
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF", "MPO"}
MIN_SIDE_PX = 64
MAX_SIDE_PX = 1600  # downscale before sending to the model


class ImageValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ProcessedImage:
    data_url: str
    jpeg_bytes: bytes
    width: int
    height: int
    original_format: str
    warnings: list[str] = field(default_factory=list)


def process_image(raw: bytes, filename: str = "", max_mb: float = 8.0) -> ProcessedImage:
    if not raw:
        raise ImageValidationError("empty_image", "The uploaded image is empty.")
    if len(raw) > max_mb * 1024 * 1024:
        raise ImageValidationError(
            "image_too_large", f"Image is {len(raw) / 1048576:.1f} MB; the limit is {max_mb:g} MB."
        )

    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = (probe.format or "").upper()
        probe.verify()  # structural check
        img = Image.open(io.BytesIO(raw))
        img.load()  # full decode - raises on truncated/incomplete data
    except UnidentifiedImageError:
        raise ImageValidationError(
            "unsupported_image", f"'{filename or 'file'}' is not a recognised image. Use JPG, PNG or WEBP."
        )
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageValidationError(
            "corrupted_image",
            "The image appears to be corrupted or incomplete (upload interrupted?). Please re-upload it.",
        ) from exc

    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError("unsupported_image", f"Image format {fmt or 'unknown'} is not supported.")

    if getattr(img, "is_animated", False):
        img.seek(0)
    width, height = img.size
    if min(width, height) < MIN_SIDE_PX:
        raise ImageValidationError(
            "image_too_small",
            f"Image is only {width}x{height}px; at least {MIN_SIDE_PX}px per side is needed for analysis.",
        )

    img = img.convert("RGB")
    warnings = quality_warnings(img)

    if max(width, height) > MAX_SIDE_PX:
        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    jpeg = buf.getvalue()
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return ProcessedImage(data_url, jpeg, img.width, img.height, fmt, warnings)


def quality_warnings(img: Image.Image) -> list[str]:
    """Cheap heuristics so the AI (and the user) know when an image is unreliable."""
    warnings: list[str] = []
    small = img.copy()
    small.thumbnail((512, 512))
    gray = small.convert("L")
    stat = ImageStat.Stat(gray)
    brightness, contrast = stat.mean[0], stat.stddev[0]
    if brightness < 40:
        warnings.append("Image is very dark; hazards or cracks may be missed.")
    elif brightness > 225:
        warnings.append("Image is over-exposed; fine details may be lost.")
    if contrast < 18:
        warnings.append("Image has very low contrast; analysis confidence is reduced.")
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    if edges < 4 and contrast >= 18:
        warnings.append("Image looks blurry or out of focus.")
    w, h = img.size
    if min(w, h) < 300:
        warnings.append(f"Low resolution ({w}x{h}px); small details may not be visible.")
    return warnings
