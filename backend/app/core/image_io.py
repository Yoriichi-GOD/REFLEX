from __future__ import annotations

import hashlib
from io import BytesIO
import struct

import cv2
import numpy as np
from PIL import Image

from app.config import MAX_EDGE, MAX_PIXELS, MAX_UPLOAD_BYTES


class ImageInputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ImageInputError("UNSUPPORTED_FORMAT", "Use a valid PNG, JPEG, or WebP image.")


def _encoded_dimensions(data: bytes, mime: str) -> tuple[int, int]:
    if mime == "image/png":
        if len(data) < 24:
            raise ImageInputError("UNSUPPORTED_FORMAT", "PNG header is incomplete.")
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if mime == "image/webp":
        chunk = data[12:16]
        if chunk == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            b1, b2, b3, b4 = data[21:25]
            width = 1 + b1 + ((b2 & 0x3F) << 8)
            height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
            return width, height
        if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        raise ImageInputError("UNSUPPORTED_FORMAT", "Unsupported or incomplete WebP header.")
    position = 2
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        segment_length = int.from_bytes(data[position:position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in frame_markers and segment_length >= 7:
            height, width = struct.unpack(">HH", data[position + 3:position + 7])
            return width, height
        position += segment_length
    raise ImageInputError("UNSUPPORTED_FORMAT", "JPEG dimensions could not be read from its header.")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_image(data: bytes) -> tuple[np.ndarray, dict]:
    if not data:
        raise ImageInputError("EMPTY_FILE", "Choose a non-empty image file.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageInputError("UPLOAD_TOO_LARGE", f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    mime = image_mime(data)
    header_width, header_height = _encoded_dimensions(data, mime)
    if header_width < 1 or header_height < 1 or header_width > MAX_EDGE or header_height > MAX_EDGE or header_width * header_height > MAX_PIXELS:
        raise ImageInputError("IMAGE_DIMENSIONS_EXCEEDED", f"Image dimensions are limited to {MAX_EDGE}px per edge and {MAX_PIXELS:,} pixels.")
    raw = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise ImageInputError("UNSUPPORTED_FORMAT", "OpenCV could not decode this image. Use PNG, JPEG, or WebP.")
    if raw.ndim not in (2, 3) or (raw.ndim == 3 and raw.shape[2] not in (1, 3, 4)):
        raise ImageInputError("UNSUPPORTED_CHANNELS", "Use a grayscale, RGB, or RGBA image.")
    height, width = raw.shape[:2]
    if width > MAX_EDGE or height > MAX_EDGE or width * height > MAX_PIXELS:
        raise ImageInputError("IMAGE_DIMENSIONS_EXCEEDED", f"Image dimensions are limited to {MAX_EDGE}px per edge and {MAX_PIXELS:,} pixels.")
    bit_depth = int(raw.dtype.itemsize * 8)
    if raw.dtype == np.uint16:
        low, high = np.percentile(raw, [0.5, 99.5]).astype(float)
        scale = 255.0 / max(1.0, high - low)
        raw = np.clip((raw.astype(np.float32) - low) * scale, 0, 255).astype(np.uint8)
    elif raw.dtype != np.uint8:
        raise ImageInputError("UNSUPPORTED_BIT_DEPTH", "Image must use 8-bit or 16-bit integer pixels.")
    try:
        with Image.open(BytesIO(data)) as metadata_image:
            orientation = int(metadata_image.getexif().get(274, 1))
    except Exception:
        orientation = 1
    orientation_ops = {
        2: lambda img: cv2.flip(img, 1),
        3: lambda img: cv2.rotate(img, cv2.ROTATE_180),
        4: lambda img: cv2.flip(img, 0),
        5: lambda img: cv2.transpose(img),
        6: lambda img: cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
        7: lambda img: cv2.flip(cv2.transpose(img), -1),
        8: lambda img: cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }
    if orientation in orientation_ops:
        raw = orientation_ops[orientation](raw)
    if raw.ndim == 2:
        image = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
    elif raw.shape[2] == 1:
        image = cv2.cvtColor(raw[:, :, 0], cv2.COLOR_GRAY2BGR)
    elif raw.shape[2] == 4:
        alpha = raw[:, :, 3:4].astype(np.float32) / 255.0
        rgb = raw[:, :, :3].astype(np.float32)
        image = np.clip(rgb * alpha + 127.0 * (1.0 - alpha), 0, 255).astype(np.uint8)
    else:
        image = raw
    original_height, original_width = raw.shape[:2]
    return image, {"width": int(original_width), "height": int(original_height), "encoded_width": int(width), "encoded_height": int(height), "exif_orientation": orientation, "source_bit_depth": bit_depth, "source_bytes": len(data)}


def encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("OpenCV failed to encode an image artifact.")
    return encoded.tobytes()
