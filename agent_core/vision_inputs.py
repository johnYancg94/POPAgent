"""Helpers for user-supplied multimodal image inputs."""

from __future__ import annotations
import base64
from pathlib import Path
from typing import Iterable


_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def media_type_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise ValueError(f"Unsupported image type: {suffix or '(none)'}")
    return media_type


def image_payload_from_file(path: str) -> dict[str, str]:
    file_path = Path(path)
    media_type = media_type_for_path(str(file_path))
    data = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return {"media_type": media_type, "data": data}


def collect_enabled_image_payloads(items: Iterable) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    for item in items:
        if not getattr(item, "is_enabled", False):
            continue
        media_type = getattr(item, "media_type", "")
        image_base64 = getattr(item, "image_base64", "")
        if not media_type or not image_base64:
            continue
        payloads.append({"media_type": media_type, "data": image_base64})
    return payloads
