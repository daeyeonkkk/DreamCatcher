from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .studio_files import resolve_output_target
from .studio_paths import resolve_output_root

PREVIEWABLE_SUFFIXES = {
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
def resolve_preview_target(path: str, *, output_root: str) -> Path:
    target = resolve_output_target(path, output_root=output_root)
    if target.suffix.lower() not in PREVIEWABLE_SUFFIXES:
        raise ValueError(f"Preview is not supported for this file type: {target.suffix.lower()}")
    return target


def preview_cache_path(target: Path, *, output_root: str, max_edge: int) -> Path:
    root = resolve_output_root(output_root)
    cache_root = root / "_preview_cache"
    fingerprint = hashlib.sha256(
        f"{target}:{target.stat().st_mtime_ns}:{max_edge}".encode("utf-8")
    ).hexdigest()[:20]
    return cache_root / f"{fingerprint}.jpg"


def build_preview_image(path: str, *, output_root: str, max_edge: int = 1600) -> Path:
    if max_edge <= 0:
        raise ValueError("max_edge must be a positive integer.")

    target = resolve_preview_target(path, output_root=output_root)
    cache_path = preview_cache_path(target, output_root=output_root, max_edge=max_edge)
    if cache_path.exists():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(target) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            image.save(cache_path, format="JPEG", quality=88, optimize=True)
    except UnidentifiedImageError as exc:
        raise ValueError(f"Preview generation failed for unsupported image data: {target.name}") from exc

    return cache_path
