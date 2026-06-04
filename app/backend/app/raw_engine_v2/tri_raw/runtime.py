from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import import_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps
import tifffile

from app.core.raw_restoration_policy import (
    DEFAULT_RAW_RESTORATION_GOAL,
    normalize_raw_restoration_goal,
    raw_restoration_goal_policy,
)
from app.raw_engine_v2.shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA

from .frontier_eval import build_tri_raw_frontier_eval
from .learned_adapter import materialize_tri_raw_learned_adapter
from .planner import TriRawFoundationPlan


MODULE_STATUS = "phase1_runtime_wiring"
TRI_RAW_BASELINE_RUNTIME_BACKEND = "tri_raw_baseline_v1"
TRI_RAW_FRONTIER_CONTRACT_ID = "tri_raw_frontier_v1"
TRI_RAW_RUNTIME_BACKEND = TRI_RAW_BASELINE_RUNTIME_BACKEND
RAWPY_BACKEND_KEY = "rawpy"
COMPANION_BACKEND_KEY = "companion_preview"
PREVIEWABLE_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
RawRestorationGoal = Literal["truth_preserving", "aggressive_restore"]


@dataclass(frozen=True)
class TriRawPreviewRuntimeResult:
    backend: str
    preview_path: str
    scene_linear_path: str
    noise_map_path: str
    motion_map_path: str
    diagnostics_manifest_path: str
    recommended_label: str
    recommended_artifact_path: str
    selected_reference_index: int
    selected_reference_raw_path: str
    selected_reference_preview_path: str
    restoration_goal: RawRestorationGoal = DEFAULT_RAW_RESTORATION_GOAL
    restoration_goal_policy: dict[str, Any] = field(default_factory=dict)
    baseline_backend: str = TRI_RAW_BASELINE_RUNTIME_BACKEND
    frontier_contract: dict[str, Any] = field(default_factory=dict)
    merged_hdr_path: str | None = None
    denoised_result_path: str | None = None
    aggressive_restore_candidate_path: str | None = None
    confidence_map_path: str | None = None
    confidence_preview_path: str | None = None
    ghost_risk_map_path: str | None = None
    highlight_map_path: str | None = None
    shadow_map_path: str | None = None
    deghost_mask_path: str | None = None
    hdr_gain_map_path: str | None = None
    noise_suppression_map_path: str | None = None
    alignment_offset_map_path: str | None = None
    alignment_residual_map_path: str | None = None
    alignment_vector_field_path: str | None = None
    alignment_refinement_map_path: str | None = None
    reference_selection: list[dict[str, Any]] = field(default_factory=list)
    candidate_scores: list[dict[str, Any]] = field(default_factory=list)
    fallback_strategy: dict[str, Any] = field(default_factory=dict)
    frontier_eval: dict[str, Any] = field(default_factory=dict)
    frontier_eval_path: str | None = None
    learned_adapter: dict[str, Any] = field(default_factory=dict)
    alignment_summary: dict[str, Any] = field(default_factory=dict)
    alignment_vector_summary: dict[str, Any] = field(default_factory=dict)
    alignment_guard_summary: dict[str, Any] = field(default_factory=dict)
    alignment_refinement_summary: dict[str, Any] = field(default_factory=dict)
    confidence_summary: dict[str, Any] = field(default_factory=dict)
    joint_denoise_summary: dict[str, Any] = field(default_factory=dict)
    deghost_summary: dict[str, Any] = field(default_factory=dict)
    hdr_summary: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None
    motion_overlay_summary: str | None = None
    motion_overlay_coverage: float | None = None
    capture_summary: dict[str, Any] = field(default_factory=dict)
    bracket_coverage: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def _resolve_companion_preview(raw_path: Path) -> Path | None:
    for suffix in PREVIEWABLE_SUFFIXES:
        candidate = raw_path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def _decode_preview_with_rawpy(raw_path: str) -> Image.Image | None:
    try:
        rawpy = import_module("rawpy")
    except Exception:
        return None

    try:
        with rawpy.imread(raw_path) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=True,
                output_bps=8,
                user_flip=0,
            )
    except Exception:
        return None
    return Image.fromarray(rgb, mode="RGB")


def _load_preview_proxy(raw_path: str) -> tuple[Image.Image, str] | None:
    resolved_raw = Path(raw_path)
    companion = _resolve_companion_preview(resolved_raw)
    if companion is not None:
        with Image.open(companion) as image:
            return ImageOps.exif_transpose(image).convert("RGB").copy(), COMPANION_BACKEND_KEY

    decoded = _decode_preview_with_rawpy(raw_path)
    if decoded is not None:
        return decoded, RAWPY_BACKEND_KEY
    return None


def _save_preview(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=95)


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _save_heatmap(array: np.ndarray, path: Path, *, black: str = "#111827", white: str = "#f9fafb") -> None:
    grayscale = Image.fromarray(np.clip(array * 255.0, 0.0, 255.0).astype(np.uint8), mode="L")
    _save_png(ImageOps.colorize(grayscale, black=black, white=white), path)


def _write_float_map(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(path, np.asarray(array, dtype=np.float32))


def _smooth_scalar_map(array: np.ndarray, *, passes: int = 1) -> np.ndarray:
    smoothed = np.asarray(array, dtype=np.float32)
    for _ in range(max(passes, 0)):
        padded = np.pad(smoothed, ((1, 1), (1, 1)), mode="edge")
        smoothed = (
            padded[:-2, :-2]
            + padded[:-2, 1:-1]
            + padded[:-2, 2:]
            + padded[1:-1, :-2]
            + padded[1:-1, 1:-1]
            + padded[1:-1, 2:]
            + padded[2:, :-2]
            + padded[2:, 1:-1]
            + padded[2:, 2:]
        ) / 9.0
    return smoothed.astype(np.float32)


def _resize_to(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()
    return image.resize(size, Image.Resampling.LANCZOS)


def _image_to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def _array_to_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(array * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _luminance(array: np.ndarray) -> np.ndarray:
    return np.dot(array[..., :3], np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))


def _detail_energy(gray: np.ndarray) -> float:
    grad_x = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0.0
    grad_y = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0.0
    return float(grad_x + grad_y)


def _clip_ratio(gray: np.ndarray, *, high: bool) -> float:
    threshold = 0.98 if high else 0.02
    if gray.size == 0:
        return 0.0
    if high:
        return float(np.mean(gray >= threshold))
    return float(np.mean(gray <= threshold))


def _stability_score(gray: np.ndarray, other_arrays: list[np.ndarray]) -> float:
    if not other_arrays:
        return 1.0
    diffs = [float(np.mean(np.abs(gray - other))) for other in other_arrays]
    mean_diff = float(sum(diffs) / len(diffs))
    return max(0.0, 1.0 - (mean_diff * 3.0))


def _position_score(index: int, total: int, preferred_index: int) -> float:
    if total <= 1:
        return 1.0
    distance = abs(index - preferred_index)
    return max(0.0, 1.0 - (distance / max(total - 1, 1)))


def _well_exposed_weight(gray: np.ndarray) -> np.ndarray:
    return np.exp(-4.0 * np.square(gray - 0.5)) + 0.05


def _exposure_fuse(arrays: list[np.ndarray], *, frame_biases: list[float] | None = None) -> np.ndarray:
    gray_arrays = [_luminance(array) for array in arrays]
    biases = frame_biases or [1.0] * len(arrays)
    weights = [_well_exposed_weight(gray) * float(bias) for gray, bias in zip(gray_arrays, biases)]
    weight_sum = np.sum(weights, axis=0, dtype=np.float32)
    weight_sum = np.maximum(weight_sum, 1e-6)
    fused = np.zeros_like(arrays[0], dtype=np.float32)
    for array, weight in zip(arrays, weights):
        fused += array * (weight[..., None] / weight_sum[..., None])
    return np.clip(fused, 0.0, 1.0)


def _write_noise_map(image: Image.Image, path: Path) -> None:
    grayscale = image.convert("L")
    baseline = grayscale.filter(ImageFilter.GaussianBlur(radius=1.6))
    noise_map = ImageChops.difference(grayscale, baseline)
    _save_png(ImageOps.autocontrast(noise_map), path)


def _write_motion_map(reference_image: Image.Image, candidate_images: list[Image.Image], path: Path) -> tuple[float, str]:
    reference_gray = reference_image.convert("L")
    if not candidate_images:
        motion = Image.new("L", reference_gray.size, 0)
        _save_png(motion, path)
        return 0.0, "사용 가능한 프레임이 한 장뿐이라 움직임 범위는 사실상 0입니다."

    diffs = [
        np.asarray(ImageChops.difference(reference_gray, candidate.convert("L")), dtype=np.float32) / 255.0
        for candidate in candidate_images
    ]
    mean_diff = np.mean(diffs, axis=0, dtype=np.float32)
    coverage = float(np.mean(mean_diff >= 0.12))
    motion = Image.fromarray(np.clip(mean_diff * 255.0 * 2.4, 0.0, 255.0).astype(np.uint8), mode="L")
    _save_png(ImageOps.colorize(motion, black="#111827", white="#ffb347"), path)
    summary = (
        "움직임 감시 기준으로는 거의 정적인 브라켓입니다."
        if coverage < 0.04
        else "움직임 감시가 브라켓 안의 일부 이동 구역을 강조합니다."
        if coverage < 0.12
        else "움직임 감시가 큰 이동을 보여 주므로 전체 병합보다 보수 병합이 더 안전합니다."
    )
    return coverage, summary


def _confidence_holdout_maps(
    gray_arrays: list[np.ndarray],
    *,
    reference_index: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    stack = np.stack(gray_arrays, axis=0).astype(np.float32)
    reference = stack[reference_index]
    exposure_weights = np.stack([_well_exposed_weight(gray) for gray in gray_arrays], axis=0).astype(np.float32)
    similarity = np.exp(-8.0 * np.abs(stack - reference[None, ...])).astype(np.float32)
    weighted = exposure_weights * similarity
    weighted_sum = np.maximum(np.sum(weighted, axis=0), 1e-6)
    normalized = weighted / weighted_sum
    dominant_share = np.max(normalized, axis=0)
    luminance_std = np.std(stack, axis=0).astype(np.float32)
    consensus = np.exp(-8.0 * luminance_std).astype(np.float32)
    motion_risk = np.clip(
        1.0 - np.exp(-7.0 * np.mean(np.abs(stack - reference[None, ...]), axis=0)),
        0.0,
        1.0,
    ).astype(np.float32)
    confidence = np.clip(
        (dominant_share * 0.48) + (consensus * 0.34) + ((1.0 - motion_risk) * 0.18),
        0.0,
        1.0,
    ).astype(np.float32)
    ghost_risk = np.clip((motion_risk * 0.74) + ((1.0 - dominant_share) * 0.26), 0.0, 1.0).astype(np.float32)
    merge_strength = np.clip(confidence * (1.0 - ghost_risk), 0.0, 1.0).astype(np.float32)
    confidence_summary = {
        "mean_confidence": round(float(np.mean(confidence)), 4),
        "high_confidence_coverage": round(float(np.mean(confidence >= 0.72)), 4),
        "ghost_risk_coverage": round(float(np.mean(ghost_risk >= 0.42)), 4),
        "reference_holdout_coverage": round(float(np.mean(merge_strength <= 0.30)), 4),
        "merge_support_coverage": round(float(np.mean(merge_strength >= 0.60)), 4),
    }
    return confidence, ghost_risk, merge_strength, confidence_summary


def _highlight_shadow_maps(gray_arrays: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    stack = np.stack(gray_arrays, axis=0).astype(np.float32)
    brightest = np.max(stack, axis=0)
    darkest = np.min(stack, axis=0)
    spread = np.clip((brightest - darkest) * 2.8, 0.0, 1.0)
    highlight_map = np.clip(((brightest - 0.82) / 0.18), 0.0, 1.0) * spread
    shadow_map = np.clip(((0.18 - darkest) / 0.18), 0.0, 1.0) * spread
    return highlight_map.astype(np.float32), shadow_map.astype(np.float32)


def _detail_map(gray: np.ndarray) -> np.ndarray:
    grad_x = np.zeros_like(gray, dtype=np.float32)
    grad_y = np.zeros_like(gray, dtype=np.float32)
    if gray.shape[1] > 1:
        grad_x[:, 1:] = np.abs(np.diff(gray, axis=1))
    if gray.shape[0] > 1:
        grad_y[1:, :] = np.abs(np.diff(gray, axis=0))
    detail = grad_x + grad_y
    scale = float(np.percentile(detail, 95)) if detail.size else 0.0
    if scale <= 1e-6:
        return np.zeros_like(gray, dtype=np.float32)
    return np.clip(detail / scale, 0.0, 1.0).astype(np.float32)


def _soft_blur_array(array: np.ndarray, *, radius: float = 1.1) -> np.ndarray:
    image = _array_to_image(array)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return _image_to_array(blurred)


def _downsample_gray(gray: np.ndarray, *, max_edge: int = 512) -> tuple[np.ndarray, float]:
    height, width = gray.shape[:2]
    longest = max(height, width)
    if longest <= max_edge:
        return gray.astype(np.float32), 1.0
    scale = longest / float(max_edge)
    resized = Image.fromarray(np.clip(gray * 255.0, 0.0, 255.0).astype(np.uint8), mode="L").resize(
        (max(1, int(round(width / scale))), max(1, int(round(height / scale)))),
        Image.Resampling.BILINEAR,
    )
    return np.asarray(resized, dtype=np.float32) / 255.0, scale


def _estimate_phase_correlation_shift(
    reference_gray: np.ndarray,
    candidate_gray: np.ndarray,
) -> tuple[int, int, float]:
    reference_small, scale = _downsample_gray(reference_gray)
    candidate_small, _ = _downsample_gray(candidate_gray)
    reference_centered = reference_small - float(np.mean(reference_small))
    candidate_centered = candidate_small - float(np.mean(candidate_small))
    cross_power = np.fft.fft2(reference_centered) * np.conj(np.fft.fft2(candidate_centered))
    cross_power /= np.maximum(np.abs(cross_power), 1e-8)
    correlation = np.fft.ifft2(cross_power)
    magnitude = np.abs(correlation)
    y, x = np.unravel_index(int(np.argmax(magnitude)), magnitude.shape)
    if x > reference_small.shape[1] // 2:
        x -= reference_small.shape[1]
    if y > reference_small.shape[0] // 2:
        y -= reference_small.shape[0]
    dx = int(round(float(x) * scale))
    dy = int(round(float(y) * scale))
    confidence = float(np.max(magnitude) / max(float(np.mean(magnitude)), 1e-6))
    return dx, dy, confidence


def _translate_array_with_edge_padding(array: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = array.shape[:2]
    pad_x = abs(dx)
    pad_y = abs(dy)
    pad_spec = ((pad_y, pad_y), (pad_x, pad_x)) if array.ndim == 2 else ((pad_y, pad_y), (pad_x, pad_x), (0, 0))
    padded = np.pad(array, pad_spec, mode="edge")
    start_y = pad_y - dy
    start_x = pad_x - dx
    if array.ndim == 2:
        return padded[start_y:start_y + height, start_x:start_x + width]
    return padded[start_y:start_y + height, start_x:start_x + width, :]


def _tile_window(center: float, length: int, radius: int) -> tuple[int, int]:
    start = max(0, int(round(center - radius)))
    end = min(length, int(round(center + radius)))
    if end - start >= 24:
        return start, end
    deficit = 24 - (end - start)
    start = max(0, start - (deficit // 2))
    end = min(length, end + (deficit - (deficit // 2)))
    return start, end


def _tent_basis(length: int, centers: np.ndarray) -> np.ndarray:
    if len(centers) == 1:
        return np.ones((1, length), dtype=np.float32)
    coordinates = np.arange(length, dtype=np.float32)
    spacing = max(float(centers[1] - centers[0]), 1.0)
    weights = []
    for center in centers:
        weight = np.clip(1.0 - (np.abs(coordinates - center) / spacing), 0.0, 1.0)
        weights.append(weight.astype(np.float32))
    stacked = np.stack(weights, axis=0)
    return stacked / np.maximum(np.sum(stacked, axis=0, keepdims=True), 1e-6)


def _estimate_piecewise_tile_offsets(
    reference_gray: np.ndarray,
    candidate_gray: np.ndarray,
    *,
    grid_rows: int = 3,
    grid_cols: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    height, width = reference_gray.shape[:2]
    centers_x = np.linspace(0, width - 1, num=grid_cols, dtype=np.float32)
    centers_y = np.linspace(0, height - 1, num=grid_rows, dtype=np.float32)
    patch_radius_x = max(16, int(round(width / max(grid_cols * 2, 6))))
    patch_radius_y = max(16, int(round(height / max(grid_rows * 2, 6))))
    max_local_shift = max(2, int(round(min(height, width) * 0.08)))

    tiles: list[dict[str, Any]] = []
    active_magnitudes: list[float] = []
    confidences: list[float] = []
    for row, center_y in enumerate(centers_y):
        y0, y1 = _tile_window(float(center_y), height, patch_radius_y)
        for col, center_x in enumerate(centers_x):
            x0, x1 = _tile_window(float(center_x), width, patch_radius_x)
            reference_patch = reference_gray[y0:y1, x0:x1]
            candidate_patch = candidate_gray[y0:y1, x0:x1]

            local_dx = 0
            local_dy = 0
            confidence = 1.0
            active = False
            rejection_reason = "flat_tile"
            detail_score = _detail_energy(reference_patch)
            if reference_patch.size >= 24 * 24 and detail_score >= 0.0025:
                estimate_dx, estimate_dy, confidence = _estimate_phase_correlation_shift(reference_patch, candidate_patch)
                estimate_dx = int(np.clip(estimate_dx, -max_local_shift, max_local_shift))
                estimate_dy = int(np.clip(estimate_dy, -max_local_shift, max_local_shift))
                magnitude = float(np.hypot(estimate_dx, estimate_dy))
                if confidence >= 2.25 and magnitude >= 1.0:
                    local_dx = estimate_dx
                    local_dy = estimate_dy
                    active = True
                    rejection_reason = "accepted"
                    active_magnitudes.append(magnitude)
                    confidences.append(float(confidence))
                else:
                    rejection_reason = "low_confidence"

            tiles.append(
                {
                    "row": row,
                    "col": col,
                    "center_x": round(float(center_x), 2),
                    "center_y": round(float(center_y), 2),
                    "window": {"x0": x0, "x1": x1, "y0": y0, "y1": y1},
                    "local_dx": int(local_dx),
                    "local_dy": int(local_dy),
                    "offset_magnitude": round(float(np.hypot(local_dx, local_dy)), 3),
                    "confidence": round(float(confidence), 4),
                    "detail_score": round(float(detail_score), 5),
                    "active": active,
                    "rejection_reason": rejection_reason,
                }
            )

    summary = {
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "active_tile_count": len(active_magnitudes),
        "max_local_offset": round(max(active_magnitudes), 3) if active_magnitudes else 0.0,
        "mean_local_offset": round(float(np.mean(active_magnitudes)), 3) if active_magnitudes else 0.0,
        "mean_active_confidence": round(float(np.mean(confidences)), 4) if confidences else 0.0,
    }
    return tiles, summary


def _apply_piecewise_alignment(
    candidate_array: np.ndarray,
    tiles: list[dict[str, Any]],
    *,
    grid_rows: int,
    grid_cols: int,
) -> np.ndarray:
    if not tiles:
        return candidate_array.astype(np.float32)

    height, width = candidate_array.shape[:2]
    centers_x = np.linspace(0, width - 1, num=grid_cols, dtype=np.float32)
    centers_y = np.linspace(0, height - 1, num=grid_rows, dtype=np.float32)
    basis_x = _tent_basis(width, centers_x)
    basis_y = _tent_basis(height, centers_y)
    accumulated = np.zeros_like(candidate_array, dtype=np.float32)
    accumulated_weight = np.zeros((height, width, 1), dtype=np.float32)

    for tile in tiles:
        row = int(tile.get("row") or 0)
        col = int(tile.get("col") or 0)
        local_dx = int(tile.get("local_dx") or 0)
        local_dy = int(tile.get("local_dy") or 0)
        weight = (basis_y[row][:, None] * basis_x[col][None, :]).astype(np.float32)
        translated = _translate_array_with_edge_padding(candidate_array, local_dx, local_dy).astype(np.float32)
        accumulated += translated * weight[..., None]
        accumulated_weight += weight[..., None]

    return np.clip(accumulated / np.maximum(accumulated_weight, 1e-6), 0.0, 1.0).astype(np.float32)


def _piecewise_alignment_offset_map(
    frame_offsets: list[dict[str, Any]],
    *,
    height: int,
    width: int,
) -> np.ndarray:
    if not frame_offsets:
        return np.zeros((height, width), dtype=np.float32)

    map_accumulator = np.zeros((height, width), dtype=np.float32)
    for frame in frame_offsets:
        local_alignment = frame.get("local_alignment")
        if not isinstance(local_alignment, dict):
            continue
        grid_rows = int(local_alignment.get("grid_rows") or 0)
        grid_cols = int(local_alignment.get("grid_cols") or 0)
        tiles = local_alignment.get("tiles")
        if grid_rows <= 0 or grid_cols <= 0 or not isinstance(tiles, list):
            continue
        centers_x = np.linspace(0, width - 1, num=grid_cols, dtype=np.float32)
        centers_y = np.linspace(0, height - 1, num=grid_rows, dtype=np.float32)
        basis_x = _tent_basis(width, centers_x)
        basis_y = _tent_basis(height, centers_y)
        field = np.zeros((height, width), dtype=np.float32)
        for tile in tiles:
            if not isinstance(tile, dict):
                continue
            row = int(tile.get("row") or 0)
            col = int(tile.get("col") or 0)
            if row >= grid_rows or col >= grid_cols:
                continue
            magnitude = float(tile.get("offset_magnitude") or 0.0)
            weight = (basis_y[row][:, None] * basis_x[col][None, :]).astype(np.float32)
            field += weight * magnitude
        map_accumulator = np.maximum(map_accumulator, field)
    return np.clip(map_accumulator / max(float(np.max(map_accumulator)), 1.0), 0.0, 1.0).astype(np.float32)


def _alignment_residual_map(
    gray_arrays: list[np.ndarray],
    *,
    reference_index: int,
) -> np.ndarray:
    residuals = [
        np.abs(gray - gray_arrays[reference_index]).astype(np.float32)
        for index, gray in enumerate(gray_arrays)
        if index != reference_index
    ]
    if not residuals:
        return np.zeros_like(gray_arrays[reference_index], dtype=np.float32)
    merged = np.mean(np.stack(residuals, axis=0), axis=0)
    percentile = float(np.percentile(merged, 95))
    scale = percentile if percentile > 1e-6 else float(np.max(merged))
    scale = scale if scale > 1e-6 else 1.0
    return np.clip(merged / scale, 0.0, 1.0).astype(np.float32)


def _piecewise_alignment_vector_field(
    frame_offsets: list[dict[str, Any]],
    *,
    height: int,
    width: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    vector_fields: list[np.ndarray] = []
    max_abs_dx = 0.0
    max_abs_dy = 0.0
    active_frames: list[int] = []

    for frame in frame_offsets:
        global_dx = float(frame.get("dx") or 0.0)
        global_dy = float(frame.get("dy") or 0.0)
        dx_field = np.full((height, width), global_dx, dtype=np.float32)
        dy_field = np.full((height, width), global_dy, dtype=np.float32)

        local_alignment = frame.get("local_alignment")
        if isinstance(local_alignment, dict):
            grid_rows = int(local_alignment.get("grid_rows") or 0)
            grid_cols = int(local_alignment.get("grid_cols") or 0)
            tiles = local_alignment.get("tiles")
            if grid_rows > 0 and grid_cols > 0 and isinstance(tiles, list):
                centers_x = np.linspace(0, width - 1, num=grid_cols, dtype=np.float32)
                centers_y = np.linspace(0, height - 1, num=grid_rows, dtype=np.float32)
                basis_x = _tent_basis(width, centers_x)
                basis_y = _tent_basis(height, centers_y)
                local_dx_field = np.zeros((height, width), dtype=np.float32)
                local_dy_field = np.zeros((height, width), dtype=np.float32)
                for tile in tiles:
                    if not isinstance(tile, dict):
                        continue
                    row = int(tile.get("row") or 0)
                    col = int(tile.get("col") or 0)
                    if row >= grid_rows or col >= grid_cols:
                        continue
                    weight = (basis_y[row][:, None] * basis_x[col][None, :]).astype(np.float32)
                    local_dx_field += weight * float(tile.get("local_dx") or 0.0)
                    local_dy_field += weight * float(tile.get("local_dy") or 0.0)
                dx_field += local_dx_field
                dy_field += local_dy_field
                if int(local_alignment.get("active_tile_count") or 0) > 0:
                    active_frames.append(int(frame.get("frame_index") or 0))

        field = np.stack([dx_field, dy_field], axis=-1).astype(np.float32)
        vector_fields.append(field)
        max_abs_dx = max(max_abs_dx, float(np.max(np.abs(dx_field))))
        max_abs_dy = max(max_abs_dy, float(np.max(np.abs(dy_field))))

    if not vector_fields:
        payload = np.zeros((0, height, width, 2), dtype=np.float32)
    else:
        payload = np.stack(vector_fields, axis=0).astype(np.float32)

    return payload, {
        "layout": "frame,y,x,xy",
        "frame_count": int(payload.shape[0]),
        "components": ["dx_pixels", "dy_pixels"],
        "active_frames": active_frames,
        "max_abs_dx": round(max_abs_dx, 3),
        "max_abs_dy": round(max_abs_dy, 3),
    }


def _alignment_guard_summary(
    *,
    alignment_summary: dict[str, Any],
    alignment_vector_field: np.ndarray,
    alignment_vector_summary: dict[str, Any],
    alignment_residual: np.ndarray,
) -> dict[str, Any]:
    piecewise_local_alignment = alignment_summary.get("piecewise_local_alignment") or {}
    active_frame_count = int(piecewise_local_alignment.get("active_frame_count") or 0)
    max_local_offset = float(piecewise_local_alignment.get("max_local_offset") or 0.0)
    max_global_offset = float(alignment_summary.get("max_offset") or 0.0)
    max_abs_dx = float(alignment_vector_summary.get("max_abs_dx") or 0.0)
    max_abs_dy = float(alignment_vector_summary.get("max_abs_dy") or 0.0)

    if alignment_vector_field.size:
        vector_magnitudes = np.linalg.norm(alignment_vector_field, axis=-1).astype(np.float32)
        vector_peak_map = np.max(vector_magnitudes, axis=0).astype(np.float32)
        vector_mean_magnitude = float(np.mean(vector_magnitudes))
        vector_hotspot_coverage = float(np.mean(vector_peak_map >= 1.6))
        vector_watch_coverage = float(np.mean(vector_peak_map >= 0.8))
    else:
        vector_mean_magnitude = 0.0
        vector_hotspot_coverage = 0.0
        vector_watch_coverage = 0.0

    residual_mean = float(np.mean(alignment_residual)) if alignment_residual.size else 0.0
    residual_watch_coverage = float(np.mean(alignment_residual >= 0.38)) if alignment_residual.size else 0.0
    residual_hotspot_coverage = float(np.mean(alignment_residual >= 0.58)) if alignment_residual.size else 0.0

    pressure_score = min(
        1.0,
        (min(active_frame_count / 2.0, 1.0) * 0.18)
        + (min(max_local_offset / 8.0, 1.0) * 0.28)
        + (min(max(max_abs_dx, max_abs_dy) / 18.0, 1.0) * 0.14)
        + (min(vector_mean_magnitude / 4.5, 1.0) * 0.14)
        + (min(vector_hotspot_coverage / 0.16, 1.0) * 0.10)
        + (min(residual_hotspot_coverage / 0.18, 1.0) * 0.10)
        + (min(residual_mean / 0.28, 1.0) * 0.06),
    )
    guarded_merge_required = (
        pressure_score >= 0.38
        or (active_frame_count >= 1 and max_local_offset >= 5.0)
        or vector_hotspot_coverage >= 0.10
        or residual_hotspot_coverage >= 0.12
    )
    if residual_hotspot_coverage >= 0.12:
        primary_signal = "residual_hotspots"
    elif max_local_offset >= 5.0:
        primary_signal = "piecewise_local_offsets"
    elif vector_hotspot_coverage >= 0.10:
        primary_signal = "vector_field_hotspots"
    elif max_global_offset >= 4.0:
        primary_signal = "global_alignment_shift"
    else:
        primary_signal = "stable"

    severity = (
        "high"
        if pressure_score >= 0.62
        else "medium"
        if pressure_score >= 0.32 or guarded_merge_required
        else "low"
    )
    return {
        "severity": severity,
        "guarded_merge_required": guarded_merge_required,
        "pressure_score": round(pressure_score, 4),
        "primary_signal": primary_signal,
        "active_frame_count": active_frame_count,
        "max_local_offset": round(max_local_offset, 3),
        "max_global_offset": round(max_global_offset, 3),
        "vector_mean_magnitude": round(vector_mean_magnitude, 4),
        "vector_hotspot_coverage": round(vector_hotspot_coverage, 4),
        "vector_watch_coverage": round(vector_watch_coverage, 4),
        "residual_mean": round(residual_mean, 4),
        "residual_watch_coverage": round(residual_watch_coverage, 4),
        "residual_hotspot_coverage": round(residual_hotspot_coverage, 4),
    }


def _alignment_refinement_bridge(
    *,
    alignment_vector_field: np.ndarray,
    alignment_residual: np.ndarray,
    confidence_map: np.ndarray,
    ghost_risk_map: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    if alignment_vector_field.size:
        vector_magnitudes = np.linalg.norm(alignment_vector_field, axis=-1).astype(np.float32)
        vector_peak_map = np.max(vector_magnitudes, axis=0).astype(np.float32)
        vector_scale = float(np.percentile(vector_peak_map, 95))
        if vector_scale <= 1e-6:
            vector_scale = float(np.max(vector_peak_map))
        if vector_scale <= 1e-6:
            vector_scale = 1.0
        normalized_vector_peak = np.clip(vector_peak_map / vector_scale, 0.0, 1.0).astype(np.float32)
    else:
        normalized_vector_peak = np.zeros_like(alignment_residual, dtype=np.float32)

    residual_smoothed = _smooth_scalar_map(alignment_residual, passes=2)
    confidence_deficit = np.clip(1.0 - confidence_map, 0.0, 1.0).astype(np.float32)
    refinement_map = np.clip(
        (normalized_vector_peak * 0.42)
        + (residual_smoothed * 0.32)
        + (confidence_deficit * 0.16)
        + (ghost_risk_map * 0.10),
        0.0,
        1.0,
    ).astype(np.float32)
    guarded_holdout_map = np.clip(
        refinement_map * (0.65 + (ghost_risk_map * 0.35)),
        0.0,
        1.0,
    ).astype(np.float32)
    return guarded_holdout_map, {
        "backend": "prior_residual_refinement_bridge_v1",
        "learned_backend_available": False,
        "consumes_alignment_vector_field": True,
        "consumes_alignment_residual": True,
        "consumes_confidence_map": True,
        "guides_guarded_fusion": True,
        "mean_refinement_weight": round(float(np.mean(guarded_holdout_map)), 4),
        "hotspot_coverage": round(float(np.mean(guarded_holdout_map >= 0.55)), 4),
        "guarded_holdout_coverage": round(float(np.mean(guarded_holdout_map >= 0.68)), 4),
        "vector_peak_watch_coverage": round(float(np.mean(normalized_vector_peak >= 0.5)), 4),
        "residual_watch_coverage": round(float(np.mean(residual_smoothed >= 0.38)), 4),
    }


def _align_proxy_arrays(
    arrays: list[np.ndarray],
    *,
    reference_index: int,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    reference_gray = _luminance(arrays[reference_index])
    aligned = list(arrays)
    frame_offsets: list[dict[str, Any]] = []
    max_offset = 0.0
    for index, candidate in enumerate(arrays):
        if index == reference_index:
            frame_offsets.append(
                {
                    "frame_index": index,
                    "dx": 0,
                    "dy": 0,
                    "offset_magnitude": 0.0,
                    "confidence": 1.0,
                    "is_reference": True,
                }
            )
            continue

        candidate_gray = _luminance(candidate)
        dx, dy, confidence = _estimate_phase_correlation_shift(reference_gray, candidate_gray)
        globally_aligned_candidate = np.clip(_translate_array_with_edge_padding(candidate, dx, dy), 0.0, 1.0).astype(np.float32)
        tile_offsets, local_alignment = _estimate_piecewise_tile_offsets(
            reference_gray,
            _luminance(globally_aligned_candidate),
        )
        aligned_candidate = (
            _apply_piecewise_alignment(
                globally_aligned_candidate,
                tile_offsets,
                grid_rows=int(local_alignment["grid_rows"]),
                grid_cols=int(local_alignment["grid_cols"]),
            )
            if int(local_alignment["active_tile_count"]) > 0
            else globally_aligned_candidate
        )
        aligned[index] = np.clip(aligned_candidate, 0.0, 1.0).astype(np.float32)
        offset_magnitude = float(np.hypot(dx, dy))
        max_offset = max(max_offset, offset_magnitude)
        frame_offsets.append(
            {
                "frame_index": index,
                "dx": dx,
                "dy": dy,
                "offset_magnitude": round(offset_magnitude, 3),
                "confidence": round(confidence, 4),
                "is_reference": False,
                "local_alignment": {
                    **local_alignment,
                    "enabled": bool(local_alignment["active_tile_count"]),
                    "tiles": tile_offsets,
                },
            }
        )

    return aligned, {
        "backend": "phase_correlation_piecewise_preview_offsets_v2",
        "reference_frame_index": reference_index,
        "frames": frame_offsets,
        "max_offset": round(max_offset, 3),
        "has_nonzero_offsets": any((entry.get("dx") or entry.get("dy")) for entry in frame_offsets),
        "piecewise_local_alignment": {
            "active_frame_count": sum(
                1
                for entry in frame_offsets
                if isinstance(entry.get("local_alignment"), dict) and int(entry["local_alignment"].get("active_tile_count") or 0) > 0
            ),
            "max_local_offset": round(
                max(
                    (
                        float(entry["local_alignment"].get("max_local_offset") or 0.0)
                        for entry in frame_offsets
                        if isinstance(entry.get("local_alignment"), dict)
                    ),
                    default=0.0,
                ),
                3,
            ),
        },
    }


def _frame_noise_biases(plan: TriRawFoundationPlan) -> tuple[list[float], dict[str, Any]]:
    profiles = plan.frame_noise_profiles or []
    if not profiles:
        return [1.0] * len(plan.source_paths), {"noise_weight_biases": [1.0] * len(plan.source_paths)}

    raw_levels: list[float] = []
    for profile in profiles:
        read = float(profile.get("read_noise_scale") or 0.0)
        row = float(profile.get("row_noise_scale") or 0.0)
        shot = float(profile.get("shot_noise_scale") or 0.0)
        confidence = max(0.25, float(profile.get("confidence") or 0.5))
        level = max((read * 1.0) + (row * 0.8) + (shot * 0.6), 1e-8) / confidence
        raw_levels.append(level)

    inverse = [1.0 / level for level in raw_levels]
    peak = max(inverse) if inverse else 1.0
    biases = [round(value / peak, 4) for value in inverse]
    quietest_index = int(plan.noise_summary.get("quietest_frame_index") or 0)
    return biases, {
        "noise_weight_biases": biases,
        "noise_levels": [round(level, 8) for level in raw_levels],
        "quietest_frame_index": quietest_index,
    }


def _joint_denoise_stage(
    *,
    merged_array: np.ndarray,
    gray_arrays: list[np.ndarray],
    plan: TriRawFoundationPlan,
    frame_noise_biases: list[float],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    merged_gray = _luminance(merged_array)
    detail = _detail_map(merged_gray)
    low_detail = 1.0 - detail
    shadow_bias = np.clip((0.42 - merged_gray) / 0.42, 0.0, 1.0)
    noise_strength = 1.0 - float(sum(frame_noise_biases) / max(len(frame_noise_biases), 1))
    frame_mean_spread = float(np.mean(np.std(np.stack(gray_arrays, axis=0), axis=0)))
    suppression_map = np.clip(
        (shadow_bias * 0.42)
        + (low_detail * 0.30)
        + (noise_strength * 0.40)
        - min(frame_mean_spread * 2.0, 0.18),
        0.0,
        0.72,
    ).astype(np.float32)
    blurred = _soft_blur_array(merged_array, radius=1.0 + (noise_strength * 0.7))
    denoised = np.clip(
        (merged_array * (1.0 - suppression_map[..., None])) + (blurred * suppression_map[..., None]),
        0.0,
        1.0,
    ).astype(np.float32)
    summary = {
        "strategy": "preview_noise_aware_joint_denoise_v1",
        "mean_suppression": round(float(np.mean(suppression_map)), 4),
        "strong_suppression_coverage": round(float(np.mean(suppression_map >= 0.38)), 4),
        "shadow_weighted_coverage": round(float(np.mean(shadow_bias >= 0.22)), 4),
        "low_detail_coverage": round(float(np.mean(low_detail >= 0.45)), 4),
        "frame_noise_biases": [round(float(value), 4) for value in frame_noise_biases],
        "quietest_frame_index": int(plan.noise_summary.get("quietest_frame_index") or 0),
    }
    return denoised, suppression_map, summary


def _deghost_holdout_map(
    confidence_map: np.ndarray,
    ghost_risk_map: np.ndarray,
) -> np.ndarray:
    return np.clip((ghost_risk_map * 0.74) + ((1.0 - confidence_map) * 0.26), 0.0, 1.0).astype(np.float32)


def _hdr_gain_map(
    merged_array: np.ndarray,
    reference_array: np.ndarray,
    *,
    highlight_map: np.ndarray,
    shadow_map: np.ndarray,
) -> np.ndarray:
    merged_luma = _luminance(merged_array)
    reference_luma = _luminance(reference_array)
    gain = np.abs(merged_luma - reference_luma)
    return np.clip((gain * 2.8) + (highlight_map * 0.45) + (shadow_map * 0.35), 0.0, 1.0).astype(np.float32)


def _deghost_summary(
    *,
    deghost_mask: np.ndarray,
    ghost_risk_map: np.ndarray,
    motion_coverage: float,
    recommended_label: str,
    alignment_refinement_map: np.ndarray | None = None,
    alignment_refinement_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdout_coverage = float(np.mean(deghost_mask >= 0.35))
    merge_coverage = float(np.mean((1.0 - deghost_mask) >= 0.45))
    ghost_risk_coverage = float(np.mean(ghost_risk_map >= 0.42))
    summary = {
        "strategy": (
            "reference_holdout_masked_fusion"
            if holdout_coverage >= 0.18 or motion_coverage >= 0.10
            else "low_motion_guided_merge"
        ),
        "holdout_coverage": round(holdout_coverage, 4),
        "merge_coverage": round(merge_coverage, 4),
        "ghost_risk_coverage": round(ghost_risk_coverage, 4),
        "motion_coverage": round(motion_coverage, 4),
        "selected_preview_label": recommended_label,
    }
    if alignment_refinement_map is not None:
        summary["alignment_holdout_coverage"] = round(float(np.mean(alignment_refinement_map >= 0.55)), 4)
    if alignment_refinement_summary:
        summary["alignment_refinement_backend"] = alignment_refinement_summary.get("backend")
    return summary


def _hdr_summary(
    *,
    hdr_gain_map: np.ndarray,
    highlight_map: np.ndarray,
    shadow_map: np.ndarray,
    ev_span: float,
    recommended_label: str,
) -> dict[str, Any]:
    gain_coverage = float(np.mean(hdr_gain_map >= 0.12))
    highlight_recovery_coverage = float(np.mean(highlight_map >= 0.10))
    shadow_lift_coverage = float(np.mean(shadow_map >= 0.10))
    return {
        "strategy": "preview_exposure_fusion_bridge",
        "ev_span": round(ev_span, 3),
        "hdr_gain_coverage": round(gain_coverage, 4),
        "highlight_recovery_coverage": round(highlight_recovery_coverage, 4),
        "shadow_lift_coverage": round(shadow_lift_coverage, 4),
        "selected_preview_label": recommended_label,
        "hdr_worth_it": ev_span >= 1.25,
    }


def _srgb_channel_to_linear(value: int) -> int:
    normalized = max(0.0, min(1.0, float(value) / 255.0))
    if normalized <= 0.04045:
        linear = normalized / 12.92
    else:
        linear = ((normalized + 0.055) / 1.055) ** 2.4
    return int(round(linear * 255.0))


def _write_scene_linear_fallback(image: Image.Image, path: Path) -> None:
    lut = [_srgb_channel_to_linear(index) for index in range(256)] * len(image.getbands())
    linearized = image.point(lut)
    path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(path, np.asarray(linearized.convert("RGB"), dtype=np.uint8), photometric="rgb")


def _capture_summary(plan: TriRawFoundationPlan, *, preferred_index: int) -> dict[str, Any]:
    exposure_seconds = [
        float(value)
        for value in (plan.bracket_metadata.get("exposure_seconds") or [])
        if isinstance(value, (int, float))
    ]
    ev_span = 0.0
    capture_warnings: list[str] = []
    if len(exposure_seconds) >= 2 and min(exposure_seconds) > 0:
        ev_span = float(np.log2(max(exposure_seconds) / min(exposure_seconds)))
    if ev_span < 1.25:
        capture_warnings.append("ev_span_narrow")
    if plan.bracket_metadata.get("exposure_order") == "unordered":
        capture_warnings.append("input_order_differs_from_ev_rank")

    spacing_values = []
    ordered = sorted(exposure_seconds)
    for left, right in zip(ordered, ordered[1:]):
        if left > 0 and right > 0:
            spacing_values.append(float(np.log2(right / left)))
    ev_spacing_quality = "balanced"
    if spacing_values:
        spacing_range = max(spacing_values) - min(spacing_values)
        if spacing_range > 0.35:
            ev_spacing_quality = "irregular"
            capture_warnings.append("ev_spacing_irregular")
        elif ev_span < 1.25:
            ev_spacing_quality = "narrow"
        elif ev_span >= 2.0:
            ev_spacing_quality = "wide"
    elif ev_span < 1.25:
        ev_spacing_quality = "narrow"

    return {
        "ev_span": round(ev_span, 3),
        "ev_spacing_quality": ev_spacing_quality,
        "anchor_index_hint": preferred_index,
        "order_quality": plan.bracket_metadata.get("exposure_order"),
        "capture_warnings": capture_warnings,
    }


def _build_reference_selection(
    plan: TriRawFoundationPlan,
    proxy_paths: list[str],
    gray_arrays: list[np.ndarray],
    *,
    preferred_index: int,
) -> tuple[int, list[dict[str, Any]]]:
    requested_index = preferred_index
    entries: list[dict[str, Any]] = []
    scored: list[tuple[int, float]] = []

    for index, gray in enumerate(gray_arrays):
        highlight_coverage = _clip_ratio(gray, high=True)
        shadow_coverage = _clip_ratio(gray, high=False)
        highlight_preservation = max(0.0, 1.0 - (highlight_coverage * 3.0))
        shadow_visibility = max(0.0, float(np.mean(gray)))
        shadow_noise_risk = max(0.0, 1.0 - (shadow_visibility * 2.0))
        shadow_safety = max(0.0, 1.0 - (shadow_coverage * 2.0) - (shadow_noise_risk * 0.25))
        detail = min(1.0, _detail_energy(gray) * 10.0)
        stability = _stability_score(gray, [other for i, other in enumerate(gray_arrays) if i != index])
        position_component = _position_score(index, len(gray_arrays), preferred_index)
        total_score = (
            (highlight_preservation * 0.24)
            + (shadow_safety * 0.20)
            + (detail * 0.24)
            + (stability * 0.20)
            + (position_component * 0.12)
        )
        score_components = {
            "highlight_watch_component": round(highlight_preservation, 4),
            "shadow_watch_component": round(shadow_safety, 4),
            "diagnostic_stability_component": round(stability, 4),
            "edge_component": round(detail, 4),
            "position_component": round(position_component, 4),
            "motion_region_component": round(stability, 4),
        }
        entry = {
            "raw_path": plan.source_paths[index],
            "preview_path": proxy_paths[index],
            "metadata_index": index,
            "total_score": round(total_score, 4),
            "diagnostics": {
                "highlight_watch_path": None,
                "shadow_watch_path": None,
                "metrics": {
                    "highlight_coverage": round(highlight_coverage, 4),
                    "highlight_preservation": round(highlight_preservation, 4),
                    "highlight_detail_focus": round(detail, 4),
                    "shadow_coverage": round(shadow_coverage, 4),
                    "shadow_visibility": round(shadow_visibility, 4),
                    "shadow_noise_risk": round(shadow_noise_risk, 4),
                    "shadow_safety": round(shadow_safety, 4),
                },
                "summary": {
                    "highlight": "highlight-safe" if highlight_preservation >= 0.75 else "highlight-pressure",
                    "shadow": "shadow-safe" if shadow_safety >= 0.72 else "shadow-noise-risk",
                },
            },
            "score_components": score_components,
        }
        entries.append(entry)
        scored.append((index, total_score))

    selected_index = requested_index if 0 <= requested_index < len(gray_arrays) else max(scored, key=lambda item: item[1])[0]
    return selected_index, entries


def _candidate_score_components(
    array: np.ndarray,
    *,
    candidate_label: str,
    ev_span: float,
    motion_coverage: float,
    alignment_guard_summary: dict[str, Any],
) -> dict[str, float]:
    gray = _luminance(array)
    detail_component = min(1.0, _detail_energy(gray) * 8.0)
    clip_component = max(0.0, 1.0 - (_clip_ratio(gray, high=True) * 4.0))
    shadow_component = max(0.0, 1.0 - (_clip_ratio(gray, high=False) * 3.0))
    contrast_component = min(1.0, float(np.std(gray)) * 4.0)
    highlight_component = max(0.0, 1.0 - (_clip_ratio(gray, high=True) * 3.0))
    coverage_bonus = max(0.0, min(0.12, (ev_span - 1.25) * 0.08))
    hdr_rescue_bonus = max(0.0, min(0.16, (ev_span - 1.5) * 0.10))
    coverage_penalty = max(0.0, min(0.16, (1.2 - ev_span) * 0.18))
    motion_region_penalty = max(0.0, min(0.18, motion_coverage * 0.9))
    pressure_score = float(alignment_guard_summary.get("pressure_score") or 0.0)
    vector_hotspot_coverage = float(alignment_guard_summary.get("vector_hotspot_coverage") or 0.0)
    residual_hotspot_coverage = float(alignment_guard_summary.get("residual_hotspot_coverage") or 0.0)
    guarded_merge_required = bool(alignment_guard_summary.get("guarded_merge_required"))
    base_alignment_pressure = min(
        0.28,
        (pressure_score * 0.16)
        + (vector_hotspot_coverage * 0.10)
        + (residual_hotspot_coverage * 0.14),
    )
    if candidate_label == "merged":
        alignment_guard_penalty = base_alignment_pressure if guarded_merge_required else base_alignment_pressure * 0.35
        alignment_guard_bonus = 0.0
    elif candidate_label == "hybrid":
        alignment_guard_penalty = base_alignment_pressure * 0.30
        alignment_guard_bonus = (
            min(0.12, (pressure_score * 0.08) + (residual_hotspot_coverage * 0.05))
            if ev_span >= 1.2
            else 0.0
        )
    else:
        alignment_guard_penalty = base_alignment_pressure * (0.12 if ev_span < 1.2 else 0.18)
        alignment_guard_bonus = min(0.08, pressure_score * (0.05 if ev_span < 1.2 else 0.02))
    return {
        "detail_component": round(detail_component, 4),
        "clip_component": round(clip_component, 4),
        "shadow_component": round(shadow_component, 4),
        "contrast_component": round(contrast_component, 4),
        "highlight_component": round(highlight_component, 4),
        "coverage_bonus": round(coverage_bonus, 4),
        "hdr_rescue_bonus": round(hdr_rescue_bonus, 4),
        "coverage_penalty": round(coverage_penalty, 4),
        "motion_region_penalty": round(motion_region_penalty, 4),
        "alignment_guard_bonus": round(alignment_guard_bonus, 4),
        "alignment_guard_penalty": round(alignment_guard_penalty, 4),
    }


def _candidate_total_score(score_components: dict[str, float], *, region_bonus: float = 0.0) -> float:
    total = (
        (score_components["detail_component"] * 0.26)
        + (score_components["clip_component"] * 0.22)
        + (score_components["shadow_component"] * 0.16)
        + (score_components["contrast_component"] * 0.10)
        + (score_components["highlight_component"] * 0.12)
        + score_components["coverage_bonus"]
        + score_components["hdr_rescue_bonus"]
        + score_components.get("alignment_guard_bonus", 0.0)
        + region_bonus
        - score_components["coverage_penalty"]
        - score_components["motion_region_penalty"]
        - score_components.get("alignment_guard_penalty", 0.0)
    )
    return round(total, 4)


def _select_recommended_candidate(
    *,
    ev_span: float,
    motion_coverage: float,
    alignment_guard_summary: dict[str, Any],
) -> tuple[str, str | None]:
    if ev_span < 1.2:
        return "best_single", "narrow_bracket"
    if motion_coverage >= 0.12:
        return "hybrid", "motion_guard"
    if bool(alignment_guard_summary.get("guarded_merge_required")):
        return "hybrid", "alignment_guard"
    return "merged", None


def _fallback_strategy_payload(
    *,
    recommended_label: str,
    fallback_reason: str | None,
    ev_span: float,
    motion_coverage: float,
    alignment_guard_summary: dict[str, Any],
    confidence_summary: dict[str, Any],
) -> dict[str, Any]:
    triggered_rules: list[str] = []
    if ev_span < 1.2:
        triggered_rules.append("narrow_bracket_holdout")
    if motion_coverage >= 0.12:
        triggered_rules.append("motion_guard_holdout")
    if bool(alignment_guard_summary.get("guarded_merge_required")):
        triggered_rules.append("alignment_guard_holdout")
    if float(confidence_summary.get("mean_confidence") or 0.0) < 0.58:
        triggered_rules.append("low_confidence_guard")

    selected_action = {
        "best_single": "reference_frame_holdout",
        "hybrid": "guarded_fusion_holdout",
        "merged": "exposure_fusion_merge",
    }[recommended_label]
    default_reason = {
        "best_single": "narrow_bracket",
        "hybrid": "motion_guard",
        "merged": "full_merge",
    }[recommended_label]

    rules = [
        {
            "id": "narrow_bracket_holdout",
            "condition": "ev_span < 1.2",
            "action": "병합보다 선택된 기준 프레임을 우선합니다",
        },
        {
            "id": "motion_guard_holdout",
            "condition": "motion_coverage >= 0.12",
            "action": "보수 병합을 사용하고 위험 구역에서는 기준 프레임을 더 보존합니다",
        },
        {
            "id": "alignment_guard_holdout",
            "condition": "alignment_guard_summary.guarded_merge_required",
            "action": "거친 정렬 압력이나 잔차 집중 구역이 높게 남으면 전체 병합 우선순위를 낮춥니다",
        },
        {
            "id": "low_confidence_guard",
            "condition": "mean_confidence < 0.58",
            "action": "불안정 구역에서 기준 프레임 보존 비중을 높입니다",
        },
    ]
    return {
        "selected_action": selected_action,
        "selected_reason": fallback_reason or default_reason,
        "triggered_rules": triggered_rules or ["full_merge_allowed"],
        "rules": rules,
        "inputs": {
            "ev_span": round(ev_span, 3),
            "motion_coverage": round(motion_coverage, 4),
            "mean_confidence": confidence_summary.get("mean_confidence"),
            "reference_holdout_coverage": confidence_summary.get("reference_holdout_coverage"),
            "alignment_pressure_score": alignment_guard_summary.get("pressure_score"),
            "alignment_primary_signal": alignment_guard_summary.get("primary_signal"),
            "alignment_residual_hotspot_coverage": alignment_guard_summary.get("residual_hotspot_coverage"),
        },
    }


def _normalize_restoration_goal(restoration_goal: str) -> RawRestorationGoal:
    return normalize_raw_restoration_goal(restoration_goal)  # type: ignore[return-value]


def _restoration_goal_policy(
    restoration_goal: RawRestorationGoal,
    *,
    aggressive_candidate_path: str | None = None,
) -> dict[str, Any]:
    policy = raw_restoration_goal_policy(restoration_goal)
    return {
        "goal": policy.id,
        "label": policy.label,
        "delivery_default": policy.delivery_default,
        "candidate_enabled": policy.id == "aggressive_restore",
        "candidate_path": aggressive_candidate_path if policy.id == "aggressive_restore" else None,
        "approval_required": policy.requires_human_review,
        "requires_qwen_metric_golden_human_review": policy.requires_human_review,
        "risk": policy.risk,
        "approval": policy.approval,
        "review_gates": policy.review_gates,
        "summary": policy.summary,
    }


def _build_aggressive_restore_candidate(
    *,
    hybrid_array: np.ndarray,
    reference_array: np.ndarray,
    confidence_map: np.ndarray,
    ghost_risk_map: np.ndarray,
) -> Image.Image:
    smoothed = _array_to_image(hybrid_array).filter(ImageFilter.MedianFilter(size=3))
    sharpened = smoothed.filter(ImageFilter.UnsharpMask(radius=1.35, percent=165, threshold=1))
    sharpened_array = _image_to_array(sharpened)
    blur_array = _soft_blur_array(sharpened_array, radius=1.05)
    detail_boost = np.clip(sharpened_array + ((sharpened_array - blur_array) * 0.18), 0.0, 1.0)
    protection_map = np.clip((ghost_risk_map * 0.70) + ((1.0 - confidence_map) * 0.42), 0.0, 1.0)
    restored = np.clip(
        (detail_boost * (1.0 - protection_map[..., None])) + (reference_array * protection_map[..., None]),
        0.0,
        1.0,
    )
    return _array_to_image(restored)


def _frontier_contract_payload(
    plan: TriRawFoundationPlan,
    *,
    merged_hdr_path: Path,
    denoised_result_path: Path,
    confidence_map_path: Path,
    ghost_risk_map_path: Path,
    alignment_vector_field_path: Path,
) -> dict[str, Any]:
    return {
        "contract_id": TRI_RAW_FRONTIER_CONTRACT_ID,
        "active_backend": TRI_RAW_BASELINE_RUNTIME_BACKEND,
        "runtime_mode": "baseline_fallback_until_learned_adapter_ready",
        "accepted_frame_counts": [3, 9],
        "current_frame_count": len(plan.source_paths),
        "baseline_note": (
            "The current executable path is deterministic preview fusion; the Frontier contract fixes the "
            "evidence and I/O shape for learned RAW burst HDR/restoration adapters."
        ),
        "required_evidence": [
            "merged_hdr_path",
            "denoised_result_path",
            "confidence_map_path",
            "ghost_risk_map_path",
            "alignment_vector_field_path",
            "bootstrap_model_evidence",
        ],
        "outputs": {
            "merged_hdr_path": str(merged_hdr_path),
            "denoised_result_path": str(denoised_result_path),
            "confidence_map_path": str(confidence_map_path),
            "ghost_risk_map_path": str(ghost_risk_map_path),
            "alignment_vector_field_path": str(alignment_vector_field_path),
        },
        "research_refs": [
            "NTIRE 2025 Efficient Burst HDR and Restoration",
            "RASD Recursive Multi-Exposure Alignment",
            "RawFusion",
            "BracketIRE / IREANet",
        ],
        "data_refs": [
            "NTIRE 2025 Efficient Burst HDR and Restoration dataset",
            "RAWIR / NTIRE RAW Image Restoration",
            "BracketIRE",
        ],
    }


def materialize_tri_raw_preview_runtime(
    plan: TriRawFoundationPlan,
    *,
    requested_reference_policy: str = "auto",
    restoration_goal: str = DEFAULT_RAW_RESTORATION_GOAL,
) -> TriRawPreviewRuntimeResult | None:
    normalized_restoration_goal = _normalize_restoration_goal(restoration_goal)
    working_root = Path(plan.working_root)
    diagnostics_root = working_root / "diagnostics"
    proxy_root = diagnostics_root / "reference_proxies"

    proxy_images: list[Image.Image] = []
    proxy_paths: list[str] = []
    backends: list[str] = []
    for index, raw_path in enumerate(plan.source_paths):
        loaded = _load_preview_proxy(raw_path)
        if loaded is None:
            return None
        image, backend = loaded
        proxy_path = proxy_root / f"frame_{index + 1:02d}_preview.jpg"
        _save_preview(image, proxy_path)
        proxy_images.append(image)
        proxy_paths.append(str(proxy_path))
        backends.append(backend)

    if requested_reference_policy == "first":
        preferred_index = 0
    elif requested_reference_policy == "middle":
        preferred_index = min(len(proxy_images) // 2, len(proxy_images) - 1)
    elif requested_reference_policy == "last":
        preferred_index = len(proxy_images) - 1
    else:
        preferred_index = int(plan.reference_frame_index)

    reference_size = proxy_images[preferred_index].size
    resized_images = [_resize_to(image, reference_size) for image in proxy_images]
    resized_arrays = [_image_to_array(image) for image in resized_images]
    resized_gray_arrays = [_luminance(array) for array in resized_arrays]

    selected_reference_index, reference_selection = _build_reference_selection(
        plan,
        proxy_paths,
        resized_gray_arrays,
        preferred_index=preferred_index,
    )
    arrays, alignment_summary = _align_proxy_arrays(
        resized_arrays,
        reference_index=selected_reference_index,
    )
    gray_arrays = [_luminance(array) for array in arrays]
    aligned_images = [_array_to_image(array) for array in arrays]
    reference_image = aligned_images[selected_reference_index]
    reference_array = arrays[selected_reference_index]
    reference_preview_path = Path(working_root) / "selected_reference_preview.jpg"
    _save_preview(reference_image, reference_preview_path)

    capture_summary = _capture_summary(plan, preferred_index=selected_reference_index)
    motion_map_path = diagnostics_root / "motion_map.png"
    motion_coverage, motion_summary = _write_motion_map(
        reference_image,
        [image for index, image in enumerate(aligned_images) if index != selected_reference_index],
        motion_map_path,
    )
    alignment_offset_map = _piecewise_alignment_offset_map(
        alignment_summary.get("frames", []),
        height=reference_size[1],
        width=reference_size[0],
    )
    alignment_vector_field, alignment_vector_summary = _piecewise_alignment_vector_field(
        alignment_summary.get("frames", []),
        height=reference_size[1],
        width=reference_size[0],
    )
    alignment_residual = _alignment_residual_map(
        gray_arrays,
        reference_index=selected_reference_index,
    )
    alignment_offset_map_path = diagnostics_root / "alignment_offset_map.png"
    alignment_residual_map_path = diagnostics_root / "alignment_residual_map.png"
    alignment_vector_field_path = diagnostics_root / "alignment_vector_field.exr"
    alignment_refinement_map_path = diagnostics_root / "alignment_refinement_map.png"
    _save_heatmap(alignment_offset_map, alignment_offset_map_path, black="#08111f", white="#38bdf8")
    _save_heatmap(alignment_residual, alignment_residual_map_path, black="#111827", white="#fca5a5")
    _write_float_map(alignment_vector_field_path, alignment_vector_field)
    alignment_guard_summary = _alignment_guard_summary(
        alignment_summary=alignment_summary,
        alignment_vector_field=alignment_vector_field,
        alignment_vector_summary=alignment_vector_summary,
        alignment_residual=alignment_residual,
    )

    frame_noise_biases, noise_bias_summary = _frame_noise_biases(plan)
    merged_array = _exposure_fuse(arrays, frame_biases=frame_noise_biases)
    confidence_map, ghost_risk_map, merge_strength_map, confidence_summary = _confidence_holdout_maps(
        gray_arrays,
        reference_index=selected_reference_index,
    )
    highlight_map, shadow_map = _highlight_shadow_maps(gray_arrays)
    denoised_merged_array, noise_suppression_map, joint_denoise_summary = _joint_denoise_stage(
        merged_array=merged_array,
        gray_arrays=gray_arrays,
        plan=plan,
        frame_noise_biases=frame_noise_biases,
    )
    alignment_refinement_map, alignment_refinement_summary = _alignment_refinement_bridge(
        alignment_vector_field=alignment_vector_field,
        alignment_residual=alignment_residual,
        confidence_map=confidence_map,
        ghost_risk_map=ghost_risk_map,
    )
    adjusted_merge_strength_map = np.clip(
        merge_strength_map * (1.0 - (alignment_refinement_map * 0.38)),
        0.0,
        1.0,
    ).astype(np.float32)
    alignment_refinement_summary["merge_strength_suppression_mean"] = round(
        float(np.mean(np.clip(merge_strength_map - adjusted_merge_strength_map, 0.0, 1.0))),
        4,
    )
    _save_heatmap(alignment_refinement_map, alignment_refinement_map_path, black="#111827", white="#f59e0b")
    deghost_mask = np.clip(
        (_deghost_holdout_map(confidence_map, ghost_risk_map) * 0.78) + (alignment_refinement_map * 0.42),
        0.0,
        1.0,
    ).astype(np.float32)
    deghost_merge_strength = np.clip(
        (1.0 - deghost_mask) * (0.55 + (adjusted_merge_strength_map * 0.45)),
        0.0,
        1.0,
    ).astype(np.float32)
    hybrid_array = np.clip(
        (reference_array * (1.0 - deghost_merge_strength[..., None])) + (denoised_merged_array * deghost_merge_strength[..., None]),
        0.0,
        1.0,
    )
    merged_image = _array_to_image(denoised_merged_array)
    hybrid_image = _array_to_image(hybrid_array)
    merged_preview_path = Path(working_root) / "merged_preview.jpg"
    hybrid_preview_path = Path(working_root) / "guarded_preview.jpg"
    _save_preview(merged_image, merged_preview_path)
    _save_preview(hybrid_image, hybrid_preview_path)
    confidence_preview_path = diagnostics_root / "confidence_preview.png"
    confidence_map_path = diagnostics_root / "confidence_map.exr"
    ghost_risk_map_path = diagnostics_root / "ghost_risk_map.png"
    highlight_map_path = diagnostics_root / "highlight_map.png"
    shadow_map_path = diagnostics_root / "shadow_map.png"
    deghost_mask_path = diagnostics_root / "deghost_mask.png"
    hdr_gain_map_path = diagnostics_root / "hdr_gain_map.png"
    noise_suppression_map_path = diagnostics_root / "noise_suppression_map.png"
    _save_heatmap(confidence_map, confidence_preview_path, black="#0f172a", white="#93c5fd")
    _write_float_map(confidence_map_path, confidence_map)
    _save_heatmap(ghost_risk_map, ghost_risk_map_path, black="#0b1020", white="#f97316")
    _save_heatmap(highlight_map, highlight_map_path, black="#111827", white="#fde047")
    _save_heatmap(shadow_map, shadow_map_path, black="#111827", white="#86efac")
    _save_heatmap(deghost_mask, deghost_mask_path, black="#0b1020", white="#f87171")
    _save_heatmap(noise_suppression_map, noise_suppression_map_path, black="#111827", white="#a78bfa")

    ev_span = float(capture_summary.get("ev_span") or 0.0)
    recommended_label, fallback_reason = _select_recommended_candidate(
        ev_span=ev_span,
        motion_coverage=motion_coverage,
        alignment_guard_summary=alignment_guard_summary,
    )
    fallback_strategy = _fallback_strategy_payload(
        recommended_label=recommended_label,
        fallback_reason=fallback_reason,
        ev_span=ev_span,
        motion_coverage=motion_coverage,
        alignment_guard_summary=alignment_guard_summary,
        confidence_summary=confidence_summary,
    )
    candidate_images = {
        "best_single": reference_image,
        "merged": merged_image,
        "hybrid": hybrid_image,
    }
    candidate_paths = {
        "best_single": str(reference_preview_path),
        "merged": str(merged_preview_path),
        "hybrid": str(hybrid_preview_path),
    }
    candidate_arrays = {
        "best_single": reference_array,
        "merged": denoised_merged_array,
        "hybrid": hybrid_array,
    }
    learned_adapter_result = materialize_tri_raw_learned_adapter(
        plan,
        output_path=Path(working_root) / "learned_rawfusion.tiff",
        preview_path=Path(working_root) / "learned_rawfusion_preview.jpg",
    )
    learned_adapter = learned_adapter_result.to_dict()
    if learned_adapter_result.status == "materialized" and learned_adapter_result.preview_path:
        try:
            with Image.open(learned_adapter_result.preview_path) as learned_image:
                learned_candidate = _resize_to(ImageOps.exif_transpose(learned_image).convert("RGB"), reference_size)
            candidate_images["learned_rawfusion"] = learned_candidate
            candidate_paths["learned_rawfusion"] = str(learned_adapter_result.preview_path)
            candidate_arrays["learned_rawfusion"] = _image_to_array(learned_candidate)
        except Exception as exc:
            learned_adapter = {
                **learned_adapter,
                "status": "unavailable",
                "reason": "rawfusion_preview_load_failed",
                "error": str(exc),
            }
    aggressive_restore_candidate_path: str | None = None
    if normalized_restoration_goal == "aggressive_restore":
        aggressive_restore_path = Path(working_root) / "aggressive_restore_preview.jpg"
        aggressive_restore_image = _build_aggressive_restore_candidate(
            hybrid_array=hybrid_array,
            reference_array=reference_array,
            confidence_map=confidence_map,
            ghost_risk_map=ghost_risk_map,
        )
        _save_preview(aggressive_restore_image, aggressive_restore_path)
        candidate_images["aggressive_restore"] = aggressive_restore_image
        candidate_paths["aggressive_restore"] = str(aggressive_restore_path)
        candidate_arrays["aggressive_restore"] = _image_to_array(aggressive_restore_image)
        aggressive_restore_candidate_path = str(aggressive_restore_path)
    restoration_goal_policy = _restoration_goal_policy(
        normalized_restoration_goal,
        aggressive_candidate_path=aggressive_restore_candidate_path,
    )
    recommended_image = candidate_images[recommended_label]
    hdr_gain_map = _hdr_gain_map(
        denoised_merged_array,
        reference_array,
        highlight_map=highlight_map,
        shadow_map=shadow_map,
    )
    _save_heatmap(hdr_gain_map, hdr_gain_map_path, black="#111827", white="#60a5fa")
    deghost_summary = _deghost_summary(
        deghost_mask=deghost_mask,
        ghost_risk_map=ghost_risk_map,
        motion_coverage=motion_coverage,
        recommended_label=recommended_label,
        alignment_refinement_map=alignment_refinement_map,
        alignment_refinement_summary=alignment_refinement_summary,
    )
    joint_denoise_summary.update(noise_bias_summary)
    hdr_summary = _hdr_summary(
        hdr_gain_map=hdr_gain_map,
        highlight_map=highlight_map,
        shadow_map=shadow_map,
        ev_span=ev_span,
        recommended_label=recommended_label,
    )
    frontier_contract = _frontier_contract_payload(
        plan,
        merged_hdr_path=merged_preview_path,
        denoised_result_path=merged_preview_path,
        confidence_map_path=confidence_map_path,
        ghost_risk_map_path=ghost_risk_map_path,
        alignment_vector_field_path=alignment_vector_field_path,
    )
    frontier_contract["restoration_goal"] = normalized_restoration_goal
    frontier_contract["restoration_goal_policy"] = restoration_goal_policy
    preview_path = working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()["preview"]
    _save_preview(recommended_image, preview_path)

    scene_linear_path = working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths("tiff")["scene_linear"]
    _write_scene_linear_fallback(recommended_image, scene_linear_path)

    noise_map_path = diagnostics_root / "noise_map.png"
    _write_noise_map(recommended_image, noise_map_path)

    bracket_coverage = {
        "coverage_quality": "strong" if ev_span >= 2.0 else "medium" if ev_span >= 1.25 else "narrow",
        "hdr_worth_it": ev_span >= 1.25,
        "scene_class": "high_iso_noise_limited" if float(plan.noise_summary.get("peak_read_noise_scale") or 0.0) >= 0.00018 else "general",
        "scene_traits": [
            *(
                ["motion_detected"]
                if motion_coverage >= 0.06
                else []
            ),
            *(
                ["highlight_pressure"]
                if max(_clip_ratio(gray, high=True) for gray in gray_arrays) >= 0.04
                else []
            ),
        ],
        "highlight_headroom_fraction": round(max(_clip_ratio(gray, high=True) for gray in gray_arrays), 4),
        "shadow_headroom_luma": round(min(float(np.mean(gray)) for gray in gray_arrays), 4),
        "coverage_notes": [
            "TriRaw 미리보기 런타임은 학습 정렬과 HDR 병합이 올라오기 전까지 미리보기 프록시 기반 병합을 실행 가능한 연결 경로로 사용합니다."
        ],
    }

    candidate_scores: list[dict[str, Any]] = []
    for label, array in candidate_arrays.items():
        score_components = _candidate_score_components(
            array,
            candidate_label=label,
            ev_span=ev_span,
            motion_coverage=motion_coverage,
            alignment_guard_summary=alignment_guard_summary,
        )
        region_bonus = 0.04 if label == "merged" and ev_span >= 1.5 else 0.02 if label == "hybrid" else 0.0
        if label == "aggressive_restore":
            region_bonus = 0.01
        total_score = _candidate_total_score(
            score_components,
            region_bonus=region_bonus,
        )
        entry = {
            "label": label,
            "path": candidate_paths[label],
            "total_score": total_score,
            "score_components": score_components,
        }
        if label == "aggressive_restore":
            entry.update(
                {
                    "requires_review": True,
                    "delivery_default": False,
                    "risk_tags": ["hallucinated_texture", "edge_shift", "over_sharpening"],
                    "review_gate": "qwen_metric_golden_human_approval",
                }
            )
        candidate_scores.append(entry)

    frontier_eval_path = diagnostics_root / "frontier_eval.json"
    frontier_eval = build_tri_raw_frontier_eval(
        frame_count=len(plan.source_paths),
        recommended_label=recommended_label,
        candidate_scores=candidate_scores,
        confidence_summary=confidence_summary,
        joint_denoise_summary=joint_denoise_summary,
        deghost_summary=deghost_summary,
        hdr_summary=hdr_summary,
        alignment_guard_summary=alignment_guard_summary,
        alignment_refinement_summary=alignment_refinement_summary,
        fallback_strategy=fallback_strategy,
        capture_summary=capture_summary,
        artifact_paths={
            "merged_hdr_path": str(merged_preview_path),
            "denoised_result_path": str(merged_preview_path),
            "confidence_map_path": str(confidence_map_path),
            "ghost_risk_map_path": str(ghost_risk_map_path),
            "alignment_vector_field_path": str(alignment_vector_field_path),
            "aggressive_restore_candidate_path": aggressive_restore_candidate_path,
            "diagnostics_manifest_path": plan.diagnostics_manifest_path,
        },
    )
    frontier_eval_path.write_text(
        json.dumps(frontier_eval, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    diagnostics_payload = {
        "schema_id": PHASE0_ARTIFACT_SCHEMA.schema_id,
        "schema_version": PHASE0_ARTIFACT_SCHEMA.schema_version,
        "engine_key": plan.engine_key,
        "engine_version": plan.engine_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "materialization_status": "preview_fused",
        "runtime_backend": TRI_RAW_RUNTIME_BACKEND,
        "baseline_backend": TRI_RAW_BASELINE_RUNTIME_BACKEND,
        "restoration_goal": normalized_restoration_goal,
        "restoration_goal_policy": restoration_goal_policy,
        "frontier_contract": frontier_contract,
        "frontier_eval": frontier_eval,
        "frontier_eval_path": str(frontier_eval_path),
        "learned_adapter": learned_adapter,
        "required_artifacts": [
            {
                "key": "preview",
                "path": str(preview_path),
                "required": True,
                "exists": preview_path.is_file(),
            },
            {
                "key": "scene_linear",
                "path": str(scene_linear_path),
                "required": True,
                "exists": scene_linear_path.is_file(),
            },
            {
                "key": "report",
                "path": plan.report_path,
                "required": True,
                "exists": Path(plan.report_path).is_file(),
            },
            {
                "key": "diagnostics_manifest",
                "path": plan.diagnostics_manifest_path,
                "required": True,
                "exists": True,
            },
        ],
        "diagnostics": [
            {
                "key": "noise_map",
                "path": str(noise_map_path),
                "required": False,
                "exists": noise_map_path.is_file(),
            },
            {
                "key": "motion_map",
                "path": str(motion_map_path),
                "required": False,
                "exists": motion_map_path.is_file(),
            },
            {
                "key": "confidence_map",
                "path": str(confidence_map_path),
                "required": False,
                "exists": confidence_map_path.is_file(),
            },
            {
                "key": "confidence_preview",
                "path": str(confidence_preview_path),
                "required": False,
                "exists": confidence_preview_path.is_file(),
            },
            {
                "key": "ghost_risk_map",
                "path": str(ghost_risk_map_path),
                "required": False,
                "exists": ghost_risk_map_path.is_file(),
            },
            {
                "key": "highlight_map",
                "path": str(highlight_map_path),
                "required": False,
                "exists": highlight_map_path.is_file(),
            },
            {
                "key": "shadow_map",
                "path": str(shadow_map_path),
                "required": False,
                "exists": shadow_map_path.is_file(),
            },
            {
                "key": "deghost_mask",
                "path": str(deghost_mask_path),
                "required": False,
                "exists": deghost_mask_path.is_file(),
            },
            {
                "key": "hdr_gain_map",
                "path": str(hdr_gain_map_path),
                "required": False,
                "exists": hdr_gain_map_path.is_file(),
            },
            {
                "key": "noise_suppression_map",
                "path": str(noise_suppression_map_path),
                "required": False,
                "exists": noise_suppression_map_path.is_file(),
            },
            {
                "key": "alignment_offset_map",
                "path": str(alignment_offset_map_path),
                "required": False,
                "exists": alignment_offset_map_path.is_file(),
            },
            {
                "key": "alignment_residual_map",
                "path": str(alignment_residual_map_path),
                "required": False,
                "exists": alignment_residual_map_path.is_file(),
            },
            {
                "key": "alignment_vector_field",
                "path": str(alignment_vector_field_path),
                "required": False,
                "exists": alignment_vector_field_path.is_file(),
            },
            {
                "key": "alignment_refinement_map",
                "path": str(alignment_refinement_map_path),
                "required": False,
                "exists": alignment_refinement_map_path.is_file(),
            },
            {
                "key": "frontier_eval",
                "path": str(frontier_eval_path),
                "required": False,
                "exists": frontier_eval_path.is_file(),
            },
            {
                "key": "learned_adapter_output",
                "path": learned_adapter.get("output_path"),
                "required": False,
                "exists": Path(str(learned_adapter.get("output_path"))).is_file() if learned_adapter.get("output_path") else False,
            },
            {
                "key": "aggressive_restore_candidate",
                "path": aggressive_restore_candidate_path,
                "required": False,
                "exists": Path(aggressive_restore_candidate_path).is_file() if aggressive_restore_candidate_path else False,
            },
        ],
        "reference_selection": reference_selection,
        "candidate_scores": candidate_scores,
        "merged_hdr_path": str(merged_preview_path),
        "denoised_result_path": str(merged_preview_path),
        "aggressive_restore_candidate_path": aggressive_restore_candidate_path,
        "alignment_summary": alignment_summary,
        "alignment_vector_summary": alignment_vector_summary,
        "alignment_guard_summary": alignment_guard_summary,
        "alignment_refinement_summary": alignment_refinement_summary,
        "motion_overlay_coverage": round(motion_coverage, 4),
        "motion_overlay_summary": motion_summary,
        "confidence_summary": confidence_summary,
        "joint_denoise_summary": joint_denoise_summary,
        "deghost_summary": deghost_summary,
        "hdr_summary": hdr_summary,
        "capture_summary": capture_summary,
        "bracket_coverage": bracket_coverage,
        "fallback_strategy": fallback_strategy,
    }
    Path(plan.diagnostics_manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(plan.diagnostics_manifest_path).write_text(
        json.dumps(diagnostics_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    runtime_backend_summary = (
        COMPANION_BACKEND_KEY
        if all(backend == COMPANION_BACKEND_KEY for backend in backends)
        else RAWPY_BACKEND_KEY
        if all(backend == RAWPY_BACKEND_KEY for backend in backends)
        else "mixed_preview_sources"
    )
    notes = [
        "TriRaw 미리보기 런타임이 미리보기 프록시에서 실행 가능한 브라켓 결과를 만들었습니다.",
        "이 경로는 Studio/runtime 연결과 보수적인 브라켓 안내용이며, 최종 학습형 HDR 병합 목표 자체는 아닙니다.",
    ]
    if fallback_reason == "narrow_bracket":
        notes.append("브라켓 EV 폭이 좁아 더 강한 병합보다 선택된 기준 프레임을 우선했습니다.")
    elif fallback_reason == "motion_guard":
        notes.append("움직임 범위가 보호 기준을 넘어 보수적 혼합 미리보기를 선택했습니다.")
    if confidence_summary["reference_holdout_coverage"] >= 0.20:
        notes.append("기준 프레임 보존 구역이 불안정한 영역을 덮어 움직이는 피사체가 anchor 프레임에 더 가깝게 유지됐습니다.")
    if hdr_summary["hdr_gain_coverage"] >= 0.12:
        notes.append("노출 병합이 일부 구역에서 선택된 기준 프레임보다 더 넓은 톤 여유를 복원했습니다.")
    if joint_denoise_summary["strong_suppression_coverage"] >= 0.10:
        notes.append("노이즈 인지 joint denoise가 보수 병합 점수화 전에 저디테일 그림자 구역을 부드럽게 눌렀습니다.")
    if alignment_summary["has_nonzero_offsets"]:
        notes.append("미리보기 프록시를 먼저 전역 정렬한 뒤, 신뢰도 점수화와 보수 병합 전에 거친 구간별 지역 오프셋으로 한 번 더 다듬었습니다.")
    if float(alignment_summary.get("piecewise_local_alignment", {}).get("max_local_offset") or 0.0) >= 1.0:
        notes.append("구간별 정렬이 지역 오프셋 압력을 드러내, 정렬 진단에 오프셋과 잔차 감시 맵을 함께 남깁니다.")
    if int(alignment_vector_summary.get("frame_count") or 0) >= 3:
        notes.append("이후 학습형 정렬기가 현재의 거친 오프셋 prior를 재사용할 수 있도록 정식 정렬 벡터 필드를 함께 기록합니다.")
    if bool(alignment_guard_summary.get("guarded_merge_required")):
        notes.append("정렬 압력이 이제 전체 병합 허용 전에 보수 병합 점수와 대체 경로 선택에 직접 반영됩니다.")
    if float(alignment_refinement_summary.get("guarded_holdout_coverage") or 0.0) >= 0.08:
        notes.append("선행 오프셋·잔차 정제 브리지가 정렬 불일치 집중 구역을 표시하고, 그 구역에서는 보수 병합이 기준 프레임 쪽으로 더 붙도록 유도합니다.")
    if normalized_restoration_goal == "aggressive_restore" and aggressive_restore_candidate_path:
        notes.append("공격적 복원 후보를 별도 산출물로 만들었습니다. Qwen·metric·golden set·사람 승인 전에는 최종 납품 기준으로 자동 승격하지 않습니다.")

    return TriRawPreviewRuntimeResult(
        backend=runtime_backend_summary,
        preview_path=str(preview_path),
        scene_linear_path=str(scene_linear_path),
        noise_map_path=str(noise_map_path),
        motion_map_path=str(motion_map_path),
        confidence_map_path=str(confidence_map_path),
        confidence_preview_path=str(confidence_preview_path),
        ghost_risk_map_path=str(ghost_risk_map_path),
        highlight_map_path=str(highlight_map_path),
        shadow_map_path=str(shadow_map_path),
        deghost_mask_path=str(deghost_mask_path),
        hdr_gain_map_path=str(hdr_gain_map_path),
        noise_suppression_map_path=str(noise_suppression_map_path),
        alignment_offset_map_path=str(alignment_offset_map_path),
        alignment_residual_map_path=str(alignment_residual_map_path),
        alignment_vector_field_path=str(alignment_vector_field_path),
        alignment_refinement_map_path=str(alignment_refinement_map_path),
        diagnostics_manifest_path=plan.diagnostics_manifest_path,
        recommended_label=recommended_label,
        recommended_artifact_path=candidate_paths[recommended_label],
        selected_reference_index=selected_reference_index,
        selected_reference_raw_path=plan.source_paths[selected_reference_index],
        selected_reference_preview_path=str(reference_preview_path),
        restoration_goal=normalized_restoration_goal,
        restoration_goal_policy=restoration_goal_policy,
        baseline_backend=TRI_RAW_BASELINE_RUNTIME_BACKEND,
        frontier_contract=frontier_contract,
        merged_hdr_path=str(merged_preview_path),
        denoised_result_path=str(merged_preview_path),
        aggressive_restore_candidate_path=aggressive_restore_candidate_path,
        reference_selection=reference_selection,
        candidate_scores=candidate_scores,
        fallback_strategy=fallback_strategy,
        frontier_eval=frontier_eval,
        frontier_eval_path=str(frontier_eval_path),
        learned_adapter=learned_adapter,
        alignment_summary=alignment_summary,
        alignment_vector_summary=alignment_vector_summary,
        alignment_guard_summary=alignment_guard_summary,
        alignment_refinement_summary=alignment_refinement_summary,
        confidence_summary=confidence_summary,
        joint_denoise_summary=joint_denoise_summary,
        deghost_summary=deghost_summary,
        hdr_summary=hdr_summary,
        fallback_reason=fallback_reason,
        motion_overlay_summary=motion_summary,
        motion_overlay_coverage=round(motion_coverage, 4),
        capture_summary=capture_summary,
        bracket_coverage=bracket_coverage,
        notes=tuple(notes),
    )
