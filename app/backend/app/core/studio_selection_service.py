from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field, field_validator

from .rawprep_contract import build_directory_layout
from .studio_paths import resolve_output_path, resolve_output_root


try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Pillow < 9 fallback
    RESAMPLE_LANCZOS = Image.LANCZOS


class StudioSelectionControls(BaseModel):
    threshold: int = 128
    expand_pixels: int = 0
    feather_radius: int = 4

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, value: int) -> int:
        return max(0, min(255, int(value)))

    @field_validator("expand_pixels")
    @classmethod
    def validate_expand_pixels(cls, value: int) -> int:
        return max(-32, min(32, int(value)))

    @field_validator("feather_radius")
    @classmethod
    def validate_feather_radius(cls, value: int) -> int:
        return max(0, min(32, int(value)))


class StudioSelectionState(BaseModel):
    session_id: str
    output_root: str
    selection_root: str
    state_path: str
    source_mask_path: str
    source_asset_path: str | None = None
    current_mask_path: str
    preview_path: str
    controls: StudioSelectionControls = Field(default_factory=StudioSelectionControls)
    width: int
    height: int
    selected_pixels: int
    total_pixels: int
    coverage_ratio: float
    bounding_box: list[int] | None = None
    summary: str
    ready: bool = True
    updated_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def selection_root_for(*, session_id: str, output_root: str) -> Path:
    layout = build_directory_layout(output_root, session_id)
    return Path(layout.ai_dir) / "selection"


def selection_state_path_for(selection_root: Path) -> Path:
    return selection_root / "selection_state.json"


def _normalize_payload_paths(payload: dict[str, object], *, output_root: str) -> dict[str, object]:
    normalized = dict(payload)
    normalized["output_root"] = str(resolve_output_root(output_root))
    for key in (
        "selection_root",
        "state_path",
        "source_mask_path",
        "source_asset_path",
        "current_mask_path",
        "preview_path",
    ):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = str(resolve_output_path(value, output_root=output_root))
    return normalized


def load_session_selection_state(session_id: str, *, output_root: str = "outputs") -> StudioSelectionState:
    selection_root = selection_root_for(session_id=session_id, output_root=output_root)
    state_path = selection_state_path_for(selection_root)
    if not state_path.exists():
        raise FileNotFoundError(f"Selection state was not found for session: {session_id}")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    normalized = _normalize_payload_paths(payload, output_root=output_root)
    return StudioSelectionState(**normalized)


def _resolve_session_path(path: str | None, *, output_root: str, label: str) -> Path | None:
    if not path:
        return None
    try:
        target = resolve_output_path(path, output_root=output_root)
    except ValueError as exc:
        raise ValueError(f"{label} 경로는 현재 output root 안에 있어야 합니다.") from exc
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"{label} 파일을 찾지 못했습니다: {target}")
    return target


def _load_mask_grayscale(mask_path: Path) -> Image.Image:
    with Image.open(mask_path) as image:
        working = ImageOps.exif_transpose(image)
        if "A" in working.getbands():
            return working.getchannel("A").convert("L")
        return working.convert("L")


def _load_asset_rgb(asset_path: Path | None) -> Image.Image | None:
    if asset_path is None:
        return None
    with Image.open(asset_path) as image:
        working = ImageOps.exif_transpose(image).convert("RGB")
        return working.copy()


def _mask_filter_size(radius_pixels: int) -> int:
    return max(3, abs(radius_pixels) * 2 + 1)


def _refine_selection_mask(
    source_mask: Image.Image,
    *,
    controls: StudioSelectionControls,
    target_size: tuple[int, int] | None = None,
) -> Image.Image:
    working = source_mask.convert("L")
    if target_size is not None and working.size != target_size:
        working = working.resize(target_size, RESAMPLE_LANCZOS)

    thresholded = working.point(lambda pixel: 255 if pixel >= controls.threshold else 0, mode="L")

    if controls.expand_pixels > 0:
        thresholded = thresholded.filter(ImageFilter.MaxFilter(_mask_filter_size(controls.expand_pixels)))
    elif controls.expand_pixels < 0:
        thresholded = thresholded.filter(ImageFilter.MinFilter(_mask_filter_size(controls.expand_pixels)))

    if controls.feather_radius > 0:
        thresholded = thresholded.filter(ImageFilter.GaussianBlur(radius=controls.feather_radius))

    return thresholded


def _selection_coverage(mask: Image.Image) -> tuple[int, int, float, list[int] | None]:
    normalized = mask.convert("L")
    binary = normalized.point(lambda pixel: 255 if pixel >= 16 else 0, mode="L")
    histogram = binary.histogram()
    selected_pixels = int(histogram[255]) if len(histogram) > 255 else 0
    total_pixels = binary.width * binary.height
    coverage_ratio = selected_pixels / total_pixels if total_pixels else 0.0
    bbox = binary.getbbox()
    return selected_pixels, total_pixels, coverage_ratio, list(bbox) if bbox else None


def _build_selection_preview(mask: Image.Image, *, source_asset: Image.Image | None) -> Image.Image:
    normalized_mask = mask.convert("L")
    if source_asset is None:
        monochrome = ImageOps.colorize(normalized_mask, black="#203040", white="#f5fbff")
        return monochrome.convert("RGB")

    source = source_asset.convert("RGB")
    dimmed = Image.blend(source, ImageOps.grayscale(source).convert("RGB"), 0.58)
    preview = Image.composite(source, dimmed, normalized_mask)
    outline = normalized_mask.point(lambda pixel: 255 if pixel >= 20 else 0, mode="L").filter(ImageFilter.FIND_EDGES)
    outline = outline.point(lambda pixel: 255 if pixel >= 28 else 0, mode="L")
    accent = Image.new("RGB", preview.size, "#5aa3ff")
    return Image.composite(accent, preview, outline)


def apply_session_selection_state(
    session_id: str,
    *,
    output_root: str = "outputs",
    source_mask_path: str,
    source_asset_path: str | None = None,
    controls: StudioSelectionControls | None = None,
) -> StudioSelectionState:
    resolved_output_root = str(resolve_output_root(output_root))
    resolved_controls = controls or StudioSelectionControls()
    resolved_mask_path = _resolve_session_path(source_mask_path, output_root=resolved_output_root, label="선택 마스크")
    if resolved_mask_path is None:
        raise ValueError("선택 마스크 경로가 필요합니다.")
    resolved_asset_path = _resolve_session_path(source_asset_path, output_root=resolved_output_root, label="작업 소스")

    source_mask = _load_mask_grayscale(resolved_mask_path)
    source_asset = _load_asset_rgb(resolved_asset_path)
    refined_mask = _refine_selection_mask(
        source_mask,
        controls=resolved_controls,
        target_size=source_asset.size if source_asset is not None else None,
    )
    selected_pixels, total_pixels, coverage_ratio, bounding_box = _selection_coverage(refined_mask)
    if selected_pixels <= 0:
        raise ValueError("선택 범위가 너무 작습니다. 임계값을 낮추거나 확장 값을 조정해 주세요.")

    preview = _build_selection_preview(refined_mask, source_asset=source_asset)
    selection_root = selection_root_for(session_id=session_id, output_root=resolved_output_root)
    selection_root.mkdir(parents=True, exist_ok=True)
    current_mask_path = selection_root / "current_selection_mask.png"
    preview_path = selection_root / "current_selection_preview.png"
    state_path = selection_state_path_for(selection_root)

    refined_mask.save(current_mask_path, format="PNG")
    preview.save(preview_path, format="PNG")

    summary = (
        f"선택 범위 {coverage_ratio * 100:.1f}% | "
        f"임계값 {resolved_controls.threshold} | "
        f"확장/수축 {resolved_controls.expand_pixels:+d}px | "
        f"경계 부드럽게 {resolved_controls.feather_radius}px"
    )
    state = StudioSelectionState(
        session_id=session_id,
        output_root=resolved_output_root,
        selection_root=str(selection_root),
        state_path=str(state_path),
        source_mask_path=str(resolved_mask_path),
        source_asset_path=str(resolved_asset_path) if resolved_asset_path is not None else None,
        current_mask_path=str(current_mask_path),
        preview_path=str(preview_path),
        controls=resolved_controls,
        width=refined_mask.width,
        height=refined_mask.height,
        selected_pixels=selected_pixels,
        total_pixels=total_pixels,
        coverage_ratio=coverage_ratio,
        bounding_box=bounding_box,
        summary=summary,
        updated_at=utc_now_iso(),
    )
    state_path.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return state
