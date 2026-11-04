"""Bounded, local image decoding; only normalized PNG bytes are ever previewed."""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import Problem
from .security import digest
from .storage import put_immutable, read_artifact

MAX_PIXELS = 6_000_000


def prepare_image(raw: bytes, content_type: str, organization_id: str) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                expected = {"image/png": "PNG", "image/jpeg": "JPEG"}[content_type]
                if original.format != expected or getattr(original, "n_frames", 1) != 1:
                    raise ValueError("Upload a single PNG or JPEG matching its declared MIME type.")
                if original.width * original.height > MAX_PIXELS or max(original.size) > 4096:
                    raise ValueError("Local image limits are 6 million pixels and 4096 pixels per edge.")
                original.load()
                oriented = ImageOps.exif_transpose(original)
                if oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    image = Image.new("RGB", rgba.size, "white")
                    image.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    image = oriented.convert("RGB")
                # A new pixel buffer strips EXIF, ICC, comments and other untrusted metadata.
                clean = Image.frombytes("RGB", image.size, image.tobytes())
                pixels = list(clean.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
                bits = sum(
                    (pixels[row * 9 + col] > pixels[row * 9 + col + 1]) << (row * 8 + col)
                    for row in range(8)
                    for col in range(8)
                )
                output = io.BytesIO()
                clean.save(output, format="PNG")
                thumbnail = clean.copy()
                thumbnail.thumbnail((640, 640))
                thumb = io.BytesIO()
                thumbnail.save(thumb, format="PNG")
                return {
                    "width": clean.width,
                    "height": clean.height,
                    "artifact": put_immutable(organization_id, output.getvalue(), "image/png"),
                    "thumbnail": put_immutable(organization_id, thumb.getvalue(), "image/png"),
                    "dhash": f"{bits:016x}",
                    "source_sha256": digest(raw),
                    "normalization": "EXIF orientation applied; RGB PNG; metadata stripped",
                }
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise Problem(422, "INVALID_IMAGE", str(error)) from None


def upload_samples(upload) -> list[dict]:
    from .recipes import parse_jsonl

    if upload.content_type.startswith("image/"):
        if not upload.media:
            raise Problem(409, "IMAGE_NOT_VERIFIED", "The image has not been decoded and verified.")
        return [{"image": upload.media}]
    return parse_jsonl(
        read_artifact(
            {
                "key": upload.object_key,
                "version_id": upload.object_version,
                "sha256": upload.expected_sha256,
                "bytes": upload.expected_bytes,
            }
        )
    )
