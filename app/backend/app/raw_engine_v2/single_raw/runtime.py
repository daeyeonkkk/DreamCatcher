from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Mapping

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat
from app.raw_engine_v2.shared.lens_correction import (
    apply_lens_correction_to_preview,
    apply_lens_correction_to_scene_linear,
    lens_correction_plan_from_mapping,
    merge_lens_correction_reports,
)


MODULE_STATUS = "phase1_runtime_wiring"
RAWPY_BACKEND_KEY = "rawpy"
SCENE_LINEAR_OUTPUT_FORMAT = "tiff"
SingleRawExecutionMode = Literal["fast", "hq", "safe"]


@dataclass(frozen=True)
class SingleRawSensorDecodeResult:
    backend: str
    execution_mode: SingleRawExecutionMode
    runtime_profile: str
    input_preview_path: str
    recovery_baseline_path: str | None
    preview_path: str
    scene_linear_path: str
    scene_linear_format: str
    noise_map_path: str
    lowlight_map_path: str
    width: int
    height: int
    channels: int
    dtype: str
    noise_report: dict[str, Any] = field(default_factory=dict)
    lens_correction_report: dict[str, Any] = field(default_factory=dict)
    recovery_report: dict[str, Any] = field(default_factory=dict)
    artifact_guardrail: dict[str, Any] = field(default_factory=dict)
    artifact_suppression: dict[str, Any] = field(default_factory=dict)
    fallback_decision: dict[str, Any] = field(default_factory=dict)
    timing_report: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def resolve_sensor_decode_backend() -> str | None:
    try:
        import_module("rawpy")
    except Exception:
        return None
    return RAWPY_BACKEND_KEY


def _import_runtime_support() -> tuple[Any, Any]:
    numpy = import_module("numpy")
    tifffile = import_module("tifffile")
    return numpy, tifffile


def build_single_raw_runtime_profile(
    execution_mode: SingleRawExecutionMode,
) -> dict[str, Any]:
    if execution_mode == "safe":
        return {
            "profile_key": "sensor_safe_guarded_v1",
            "demosaic_algorithm": "AHD",
            "fbdd_noise_reduction": "Light",
            "median_filter_passes": 1,
            "highlight_mode": "Blend",
            "exp_preserve_highlights": 0.35,
            "bright": 1.0,
            "preview_guardrail": "safe_preview_soften_v1",
            "shadow_lift_strength": 0.0,
            "highlight_rolloff_strength": 0.02,
            "texture_guard_strength": 0.22,
            "saturation_guard_strength": 0.065,
            "contrast_guard_strength": 0.04,
            "summary": "Guardrail-first decode with mild denoise and highlight preservation.",
        }
    if execution_mode == "hq":
        return {
            "profile_key": "sensor_hq_recovery_v1",
            "demosaic_algorithm": "DCB",
            "fbdd_noise_reduction": "Full",
            "median_filter_passes": 1,
            "highlight_mode": "ReconstructDefault",
            "exp_preserve_highlights": 0.5,
            "bright": 1.0,
            "preview_guardrail": "hq_preview_hold_v1",
            "shadow_lift_strength": 0.14,
            "highlight_rolloff_strength": 0.08,
            "texture_guard_strength": 0.1,
            "saturation_guard_strength": 0.02,
            "contrast_guard_strength": 0.01,
            "summary": "Recovery-first decode with heavier denoise and highlight reconstruction bias.",
        }
    return {
        "profile_key": "sensor_fast_preview_v1",
        "demosaic_algorithm": "AHD",
        "fbdd_noise_reduction": "Off",
        "median_filter_passes": 0,
        "highlight_mode": "Clip",
        "exp_preserve_highlights": 0.0,
        "bright": 1.0,
        "preview_guardrail": "fast_preview_direct_v1",
        "shadow_lift_strength": 0.0,
        "highlight_rolloff_strength": 0.0,
        "texture_guard_strength": 0.0,
        "saturation_guard_strength": 0.0,
        "contrast_guard_strength": 0.0,
        "summary": "Latency-first decode that gets to an editable baseline quickly.",
    }


def _resolve_rawpy_enum(rawpy_module: Any, namespace: str, member: str) -> Any:
    enum_namespace = getattr(rawpy_module, namespace, None)
    if enum_namespace is None:
        raise AttributeError(f"rawpy is missing enum namespace {namespace}")
    return getattr(enum_namespace, member)


def build_rawpy_postprocess_kwargs(rawpy_module: Any, execution_mode: SingleRawExecutionMode) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = build_single_raw_runtime_profile(execution_mode)
    highlight_mode_member = profile["highlight_mode"]
    rawpy_kwargs = {
        "use_camera_wb": True,
        "no_auto_bright": True,
        "gamma": (1.0, 1.0),
        "output_bps": 16,
        "user_flip": 0,
        "bright": float(profile["bright"]),
        "demosaic_algorithm": _resolve_rawpy_enum(rawpy_module, "DemosaicAlgorithm", str(profile["demosaic_algorithm"])),
        "fbdd_noise_reduction": _resolve_rawpy_enum(rawpy_module, "FBDDNoiseReductionMode", str(profile["fbdd_noise_reduction"])),
        "median_filter_passes": int(profile["median_filter_passes"]),
        "exp_preserve_highlights": float(profile["exp_preserve_highlights"]),
        "highlight_mode": _resolve_rawpy_enum(rawpy_module, "HighlightMode", str(highlight_mode_member)),
    }
    summary = {
        "execution_mode": execution_mode,
        "profile_key": profile["profile_key"],
        "demosaic_algorithm": profile["demosaic_algorithm"],
        "fbdd_noise_reduction": profile["fbdd_noise_reduction"],
        "median_filter_passes": profile["median_filter_passes"],
        "highlight_mode": highlight_mode_member,
        "exp_preserve_highlights": profile["exp_preserve_highlights"],
        "bright": profile["bright"],
        "preview_guardrail": profile["preview_guardrail"],
        "shadow_lift_strength": profile["shadow_lift_strength"],
        "highlight_rolloff_strength": profile["highlight_rolloff_strength"],
        "texture_guard_strength": profile["texture_guard_strength"],
        "saturation_guard_strength": profile["saturation_guard_strength"],
        "contrast_guard_strength": profile["contrast_guard_strength"],
        "summary": profile["summary"],
    }
    return rawpy_kwargs, summary


def _decode_with_rawpy(raw_path: str, *, execution_mode: SingleRawExecutionMode = "fast") -> tuple[Any, dict[str, Any]]:
    rawpy = import_module("rawpy")
    postprocess_kwargs, runtime_profile = build_rawpy_postprocess_kwargs(rawpy, execution_mode)
    with rawpy.imread(raw_path) as raw:
        scene_linear = raw.postprocess(**postprocess_kwargs)
        details = {
            "black_level_per_channel": [float(value) for value in getattr(raw, "black_level_per_channel", ())],
            "camera_white_level_per_channel": [
                float(value) for value in (getattr(raw, "camera_white_level_per_channel", None) or ())
            ],
            "white_level": float(getattr(raw, "white_level", 0) or 0),
            "color_desc": getattr(raw, "color_desc", b"").decode("ascii", errors="ignore") or None,
            "raw_pattern": (
                raw.raw_pattern.tolist() if getattr(raw, "raw_pattern", None) is not None else None
            ),
            "sizes": {
                "raw_width": int(getattr(raw.sizes, "raw_width", 0)),
                "raw_height": int(getattr(raw.sizes, "raw_height", 0)),
                "width": int(getattr(raw.sizes, "width", 0)),
                "height": int(getattr(raw.sizes, "height", 0)),
            },
            "runtime_profile": runtime_profile,
        }
    return scene_linear, details


def _crop_scene_linear(scene_linear: Any, *, crop_margin_ratio: float) -> Any:
    if crop_margin_ratio <= 0:
        return scene_linear

    numpy, _ = _import_runtime_support()
    cropped = numpy.asarray(scene_linear)
    if cropped.ndim < 2:
        return cropped

    height = int(cropped.shape[0])
    width = int(cropped.shape[1])
    margin_x = int(width * crop_margin_ratio / 2)
    margin_y = int(height * crop_margin_ratio / 2)
    if width - (margin_x * 2) < 32 or height - (margin_y * 2) < 32:
        return cropped
    return cropped[margin_y : height - margin_y, margin_x : width - margin_x]


def _normalize_scene_linear_channels(scene_linear: Any) -> Any:
    numpy, _ = _import_runtime_support()
    normalized = numpy.asarray(scene_linear)
    if normalized.ndim != 3:
        raise ValueError("SingleRaw sensor decode must produce an HxWxC image")
    if normalized.shape[2] == 4:
        normalized = normalized[:, :, :3]
    if normalized.shape[2] != 3:
        raise ValueError("SingleRaw sensor decode expects exactly 3 RGB channels after normalization")
    return numpy.ascontiguousarray(normalized)


def _write_scene_linear_tiff(scene_linear: Any, target_path: Path) -> None:
    _, tifffile = _import_runtime_support()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(target_path, scene_linear, photometric="rgb")


def _build_preview_from_scene_linear(scene_linear: Any) -> Image.Image:
    numpy, _ = _import_runtime_support()
    array = numpy.asarray(scene_linear)
    if array.dtype.kind not in {"f", "u", "i"}:
        raise ValueError(f"Unsupported scene-linear dtype for preview conversion: {array.dtype}")

    max_value = float(array.max()) if array.size else 0.0
    if max_value <= 0:
        max_value = 1.0
    normalized = numpy.clip(array.astype(numpy.float32) / max_value, 0.0, 1.0)
    preview = numpy.power(normalized, 1.0 / 2.2)
    preview_uint8 = numpy.clip(preview * 255.0 + 0.5, 0.0, 255.0).astype(numpy.uint8)
    return Image.fromarray(preview_uint8, mode="RGB")


def _apply_single_raw_base_guardrail(preview_image: Image.Image, *, execution_mode: SingleRawExecutionMode) -> Image.Image:
    profile = build_single_raw_runtime_profile(execution_mode)
    if execution_mode == "safe":
        softened = preview_image.filter(ImageFilter.GaussianBlur(radius=0.45))
        guarded = Image.blend(preview_image, softened, alpha=float(profile["texture_guard_strength"]))
        guarded = ImageEnhance.Color(guarded).enhance(1.0 - float(profile["saturation_guard_strength"]))
        guarded = ImageEnhance.Contrast(guarded).enhance(1.0 - float(profile["contrast_guard_strength"]))
        guarded = ImageEnhance.Brightness(guarded).enhance(0.992)
        return guarded
    if execution_mode == "hq":
        softened = preview_image.filter(ImageFilter.GaussianBlur(radius=0.25))
        guarded = Image.blend(preview_image, softened, alpha=float(profile["texture_guard_strength"]))
        guarded = ImageEnhance.Color(guarded).enhance(1.0 - float(profile["saturation_guard_strength"]))
        guarded = ImageEnhance.Contrast(guarded).enhance(1.0 - float(profile["contrast_guard_strength"]))
        return guarded
    return preview_image


def apply_single_raw_preview_guardrail(preview_image: Image.Image, *, execution_mode: SingleRawExecutionMode) -> Image.Image:
    profile = build_single_raw_runtime_profile(execution_mode)
    guarded = _apply_single_raw_base_guardrail(preview_image, execution_mode=execution_mode)
    if execution_mode != "hq":
        return guarded
    guarded = _apply_single_raw_tone_recovery(
        guarded,
        shadow_lift_strength=float(profile["shadow_lift_strength"]),
        highlight_rolloff_strength=float(profile["highlight_rolloff_strength"]),
    )
    return _apply_single_raw_lowlight_recovery(
        guarded,
        recovery_strength=float(profile["shadow_lift_strength"]),
    )


def apply_single_raw_preview_holdout(preview_image: Image.Image, *, execution_mode: SingleRawExecutionMode) -> Image.Image:
    if execution_mode != "safe":
        return preview_image
    held = preview_image.filter(ImageFilter.GaussianBlur(radius=0.8))
    held = Image.blend(preview_image, held, alpha=0.34)
    held = ImageEnhance.Color(held).enhance(0.92)
    held = ImageEnhance.Contrast(held).enhance(0.94)
    held = ImageEnhance.Brightness(held).enhance(0.99)
    return held


def _build_lowlight_mask(image: Image.Image, *, threshold: int = 96) -> Image.Image:
    grayscale = image.convert("L")

    def remap(index: int) -> int:
        normalized = max(0.0, min(1.0, float(threshold - index) / max(1.0, float(threshold))))
        return int(round((normalized ** 1.7) * 255.0))

    mask = grayscale.point([remap(index) for index in range(256)])
    return mask.filter(ImageFilter.GaussianBlur(radius=3.2))


def _apply_single_raw_lowlight_recovery(
    preview_image: Image.Image,
    *,
    recovery_strength: float,
) -> Image.Image:
    if recovery_strength <= 0:
        return preview_image

    lowlight_mask = _build_lowlight_mask(preview_image)
    brightened = ImageEnhance.Brightness(preview_image).enhance(1.0 + (recovery_strength * 0.42))
    shaped = ImageEnhance.Contrast(brightened).enhance(1.0 + (recovery_strength * 0.18))
    detailed = shaped.filter(
        ImageFilter.UnsharpMask(
            radius=1.2,
            percent=max(40, int(round(90 + (recovery_strength * 220)))),
            threshold=2,
        )
    )
    return Image.composite(detailed, preview_image, lowlight_mask)


def _apply_single_raw_tone_recovery(
    preview_image: Image.Image,
    *,
    shadow_lift_strength: float,
    highlight_rolloff_strength: float,
) -> Image.Image:
    if shadow_lift_strength <= 0 and highlight_rolloff_strength <= 0:
        return preview_image

    def remap(index: int) -> int:
        normalized = float(index) / 255.0
        shadow_gain = max(0.0, shadow_lift_strength) * ((1.0 - normalized) ** 2.2)
        highlight_loss = max(0.0, highlight_rolloff_strength) * (normalized ** 3.0)
        remapped = normalized + (shadow_gain * (1.0 - normalized)) - (highlight_loss * normalized)
        remapped = max(0.0, min(1.0, remapped))
        return int(round(remapped * 255.0))

    lut = [remap(index) for index in range(256)]
    return preview_image.point(lut * len(preview_image.getbands()))


def _grayscale_percentile(image: Image.Image, percentile: float) -> int:
    histogram = image.histogram()
    total = sum(histogram)
    if total <= 0:
        return 0
    target = max(1.0, min(float(total), float(total) * percentile))
    cumulative = 0
    for index, count in enumerate(histogram):
        cumulative += count
        if cumulative >= target:
            return int(index)
    return max(0, len(histogram) - 1)


def _coverage_above_threshold(image: Image.Image, *, threshold: int) -> float:
    histogram = image.histogram()
    total = sum(histogram)
    if total <= 0:
        return 0.0
    coverage = sum(histogram[max(0, threshold) :]) / float(total)
    return round(coverage, 4)


def _coverage_below_threshold(image: Image.Image, *, threshold: int) -> float:
    histogram = image.histogram()
    total = sum(histogram)
    if total <= 0:
        return 0.0
    coverage = sum(histogram[: min(len(histogram), max(0, threshold) + 1)]) / float(total)
    return round(coverage, 4)


def _build_noise_map_image(preview_image: Image.Image) -> Image.Image:
    grayscale = ImageOps.exif_transpose(preview_image).convert("L")
    baseline = grayscale.filter(ImageFilter.GaussianBlur(radius=1.6))
    return ImageChops.difference(grayscale, baseline)


def _summarize_noise_residual(image: Image.Image) -> dict[str, Any]:
    stat = ImageStat.Stat(image)
    return {
        "mean_luma": round(float(stat.mean[0]), 3),
        "peak_luma": int(stat.extrema[0][1]),
        "p95_luma": _grayscale_percentile(image, 0.95),
        "hotspot_coverage": _coverage_above_threshold(image, threshold=16),
    }


def _summarize_saturation(image: Image.Image) -> dict[str, Any]:
    saturation = image.convert("HSV").getchannel("S")
    stat = ImageStat.Stat(saturation)
    return {
        "mean": round(float(stat.mean[0]), 3),
        "p95": _grayscale_percentile(saturation, 0.95),
        "high_saturation_coverage": _coverage_above_threshold(saturation, threshold=96),
    }


def _summarize_microcontrast(image: Image.Image) -> dict[str, Any]:
    grayscale = image.convert("L")
    baseline = grayscale.filter(ImageFilter.GaussianBlur(radius=1.15))
    residual = ImageChops.difference(grayscale, baseline)
    stat = ImageStat.Stat(residual)
    return {
        "mean": round(float(stat.mean[0]), 3),
        "p95": _grayscale_percentile(residual, 0.95),
        "high_microcontrast_coverage": _coverage_above_threshold(residual, threshold=14),
    }


def _summarize_lowlight_detail(image: Image.Image) -> dict[str, Any]:
    grayscale = image.convert("L")
    lowlight_mask = _build_lowlight_mask(image, threshold=104)
    masked_luma = ImageChops.multiply(grayscale, lowlight_mask)
    baseline = grayscale.filter(ImageFilter.GaussianBlur(radius=1.25))
    residual = ImageChops.difference(grayscale, baseline)
    masked_residual = ImageChops.multiply(residual, lowlight_mask)
    stat = ImageStat.Stat(masked_residual)
    luma_stat = ImageStat.Stat(masked_luma)
    return {
        "mean_detail": round(float(stat.mean[0]), 3),
        "p95_detail": _grayscale_percentile(masked_residual, 0.95),
        "mean_luma": round(float(luma_stat.mean[0]), 3),
        "shadow_coverage": _coverage_above_threshold(lowlight_mask, threshold=24),
    }


def _summarize_tonal_zone(image: Image.Image, *, zone: Literal["shadow", "highlight"]) -> dict[str, Any]:
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    if zone == "shadow":
        indices = range(0, 65)
        coverage = _coverage_below_threshold(grayscale, threshold=64)
    else:
        indices = range(208, 256)
        coverage = _coverage_above_threshold(grayscale, threshold=208)
    count = float(sum(histogram[index] for index in indices))
    if count <= 0:
        mean_luma = 0.0
    else:
        mean_luma = sum(float(index) * float(histogram[index]) for index in indices) / count
    return {
        "coverage": round(coverage, 4),
        "mean_luma": round(float(mean_luma), 3),
    }


def _summarize_single_raw_noise_report(
    execution_mode: SingleRawExecutionMode,
    *,
    before_mean: float,
    after_mean: float,
    suppression_ratio: float,
    hotspot_coverage: float,
) -> str:
    base = (
        f"잔여 노이즈 평균 {before_mean:.1f} -> {after_mean:.1f}, "
        f"억제율 {suppression_ratio * 100:.0f}%, 강한 잔여 구역 {hotspot_coverage * 100:.1f}%."
    )
    if execution_mode == "safe":
        return f"{base} Safe 경로는 과한 질감 상승을 누르기 위해 더 보수적인 억제를 먼저 겁니다."
    if execution_mode == "hq":
        return f"{base} HQ 경로는 복원 여지를 남기면서도 잔여 노이즈를 부드럽게 정리합니다."
    return f"{base} Fast 경로는 편집 시작 속도를 해치지 않는 범위에서 진단 중심 억제만 적용합니다."


def _summarize_single_raw_artifact_guardrail(
    execution_mode: SingleRawExecutionMode,
    *,
    guardrail_key: str,
    delta_mean_luma: float,
    delta_p95_luma: int,
) -> str:
    if execution_mode == "safe":
        return (
            f"{guardrail_key}가 평균 명도 {delta_mean_luma:.1f}, 상위 95% {delta_p95_luma}만큼 결과를 눌러 "
            "과한 질감과 경계 흔들림을 보수적으로 억제합니다."
        )
    if execution_mode == "hq":
        return (
            f"{guardrail_key}가 평균 명도 {delta_mean_luma:.1f}, 상위 95% {delta_p95_luma}만큼만 개입해 "
            "복원 여지를 남기는 쪽으로 미세 보호층을 겁니다."
        )
    return (
        f"{guardrail_key}는 평균 명도 {delta_mean_luma:.1f}, 상위 95% {delta_p95_luma}만큼만 개입해 "
        "고속 미리보기의 직접성을 유지합니다."
    )


def _summarize_single_raw_artifact_suppression(
    execution_mode: SingleRawExecutionMode,
    *,
    texture_ratio: float,
    saturation_ratio: float,
) -> str:
    base = (
        f"미세 질감 억제 {texture_ratio * 100:.0f}%, "
        f"강한 채도 억제 {saturation_ratio * 100:.0f}%."
    )
    if execution_mode == "safe":
        return f"{base} Safe 경로는 과한 질감 생성과 색 틀어짐을 먼저 눌러 더 보수적인 시작점을 만듭니다."
    if execution_mode == "hq":
        return f"{base} HQ 경로는 복원 여지를 남기면서도 과한 질감과 채도 치우침을 부드럽게 다룹니다."
    return f"{base} Fast 경로는 편집 속도를 우선해 최소한의 억제만 적용합니다."


def _summarize_single_raw_recovery_report(
    execution_mode: SingleRawExecutionMode,
    *,
    shadow_lift_ratio: float,
    highlight_rolloff_ratio: float,
    lowlight_detail_gain_ratio: float,
) -> str:
    base = (
        f"그림자 완화 {shadow_lift_ratio * 100:.0f}%, "
        f"하이라이트 완화 {highlight_rolloff_ratio * 100:.0f}%, "
        f"저조도 디테일 복원 {lowlight_detail_gain_ratio * 100:.0f}%."
    )
    if execution_mode == "hq":
        return f"{base} HQ 경로는 저조도 디테일 복원과 하이라이트 보존을 위해 recovery-first preview를 유지합니다."
    if execution_mode == "safe":
        return f"{base} Safe 경로는 복원보다 보수성을 우선하고 recovery 조정보다는 holdout을 먼저 택합니다."
    return f"{base} Fast 경로는 전용 복원보다 빠른 편집 시작을 우선합니다."


def build_single_raw_timing_report(
    execution_mode: SingleRawExecutionMode,
    *,
    materialization_source: Literal["sensor_decode", "preview_bootstrap"],
    decode_ms: float,
    preview_pipeline_ms: float,
    artifact_write_ms: float,
    planner_overhead_ms: float = 0.0,
) -> dict[str, Any]:
    total_ms = round(max(0.0, decode_ms + preview_pipeline_ms + artifact_write_ms + planner_overhead_ms), 3)
    decode_ms = round(max(0.0, decode_ms), 3)
    preview_pipeline_ms = round(max(0.0, preview_pipeline_ms), 3)
    artifact_write_ms = round(max(0.0, artifact_write_ms), 3)
    planner_overhead_ms = round(max(0.0, planner_overhead_ms), 3)
    summary = (
        f"{execution_mode.upper()} 경로 {total_ms:.1f}ms "
        f"(decode {decode_ms:.1f}ms, preview {preview_pipeline_ms:.1f}ms, artifact {artifact_write_ms:.1f}ms"
        f"{'' if planner_overhead_ms <= 0 else f', planner {planner_overhead_ms:.1f}ms'})."
    )
    return {
        "diagnostic_key": "single_raw_timing_report_v1",
        "execution_mode": execution_mode,
        "materialization_source": materialization_source,
        "decode_ms": decode_ms,
        "preview_pipeline_ms": preview_pipeline_ms,
        "artifact_write_ms": artifact_write_ms,
        "planner_overhead_ms": planner_overhead_ms,
        "total_ms": total_ms,
        "summary": summary,
    }


def build_single_raw_fallback_decision(
    execution_mode: SingleRawExecutionMode,
    *,
    materialization_source: Literal["sensor_decode", "preview_bootstrap"],
    selected_variant: Literal["runtime_preview", "guarded_preview", "preview_holdout", "recovery_preview"],
    noise_report: Mapping[str, Any] | None = None,
    artifact_suppression: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    residual_after = noise_report.get("residual_after") if isinstance(noise_report, Mapping) else {}
    hotspot_coverage = float(residual_after.get("hotspot_coverage", 0.0) or 0.0) if isinstance(residual_after, Mapping) else 0.0
    texture_ratio = float(artifact_suppression.get("texture_suppression_ratio", 0.0) or 0.0) if isinstance(artifact_suppression, Mapping) else 0.0
    saturation_ratio = float(artifact_suppression.get("saturation_suppression_ratio", 0.0) or 0.0) if isinstance(artifact_suppression, Mapping) else 0.0
    risk_score = round(min(1.0, hotspot_coverage * 0.55 + texture_ratio * 0.3 + saturation_ratio * 0.15), 4)

    fallback_triggered = execution_mode == "safe" and materialization_source == "preview_bootstrap"
    if fallback_triggered:
        summary = (
            "Safe 경로는 sensor decode를 쓰지 못할 때 preview holdout을 기본 결과로 채택해 "
            "Fast/HQ보다 더 보수적인 시작점을 남깁니다."
        )
        reason_key = "safe_preview_bootstrap_holdout"
    elif execution_mode == "safe":
        summary = "Safe 경로는 sensor decode 성공 시 guarded preview를 유지하고, holdout은 필요할 때만 남깁니다."
        reason_key = "safe_runtime_guarded_preview"
    elif execution_mode == "hq":
        summary = "HQ 경로는 복원 여지를 우선해 recovery preview를 유지하고, 별도 holdout으로 내려가지 않습니다."
        reason_key = "hq_runtime_recovery_preview"
    else:
        summary = "Fast 경로는 편집 시작 속도를 우선해 직접적인 preview를 유지합니다."
        reason_key = "fast_runtime_direct_preview"

    return {
        "decision_key": "single_raw_safe_fallback_v1",
        "execution_mode": execution_mode,
        "materialization_source": materialization_source,
        "selected_variant": selected_variant,
        "fallback_triggered": fallback_triggered,
        "reason_key": reason_key,
        "risk_score": risk_score,
        "summary": summary,
    }


def build_single_raw_preview_diagnostics(
    input_preview_image: Image.Image,
    output_preview_image: Image.Image,
    *,
    execution_mode: SingleRawExecutionMode,
) -> dict[str, dict[str, Any]]:
    runtime_profile = build_single_raw_runtime_profile(execution_mode)
    residual_before = _build_noise_map_image(input_preview_image)
    residual_after = _build_noise_map_image(output_preview_image)
    residual_before_summary = _summarize_noise_residual(residual_before)
    residual_after_summary = _summarize_noise_residual(residual_after)

    before_mean = float(residual_before_summary["mean_luma"])
    after_mean = float(residual_after_summary["mean_luma"])
    suppression_ratio = 0.0
    if before_mean > 0:
        suppression_ratio = max(0.0, min(1.0, (before_mean - after_mean) / before_mean))
    delta_image = ImageChops.difference(
        input_preview_image.convert("L"),
        output_preview_image.convert("L"),
    )
    delta_summary = _summarize_noise_residual(delta_image)
    saturation_before = _summarize_saturation(input_preview_image)
    saturation_after = _summarize_saturation(output_preview_image)
    microcontrast_before = _summarize_microcontrast(input_preview_image)
    microcontrast_after = _summarize_microcontrast(output_preview_image)
    shadow_before = _summarize_tonal_zone(input_preview_image, zone="shadow")
    shadow_after = _summarize_tonal_zone(output_preview_image, zone="shadow")
    highlight_before = _summarize_tonal_zone(input_preview_image, zone="highlight")
    highlight_after = _summarize_tonal_zone(output_preview_image, zone="highlight")
    lowlight_detail_before = _summarize_lowlight_detail(input_preview_image)
    lowlight_detail_after = _summarize_lowlight_detail(output_preview_image)
    texture_ratio = 0.0
    if float(microcontrast_before["mean"]) > 0:
        texture_ratio = max(
            0.0,
            min(
                1.0,
                (float(microcontrast_before["mean"]) - float(microcontrast_after["mean"])) / float(microcontrast_before["mean"]),
            ),
        )
    saturation_ratio = 0.0
    if float(saturation_before["high_saturation_coverage"]) > 0:
        saturation_ratio = max(
            0.0,
            min(
                1.0,
                (float(saturation_before["high_saturation_coverage"]) - float(saturation_after["high_saturation_coverage"]))
                / float(saturation_before["high_saturation_coverage"]),
            ),
        )
    shadow_lift_ratio = 0.0
    if float(shadow_before["mean_luma"]) < 64:
        shadow_lift_ratio = max(
            0.0,
            min(
                1.0,
                (float(shadow_after["mean_luma"]) - float(shadow_before["mean_luma"])) / max(1.0, 64.0 - float(shadow_before["mean_luma"])),
            ),
        )
    highlight_rolloff_ratio = 0.0
    if float(highlight_before["mean_luma"]) > 0:
        highlight_rolloff_ratio = max(
            0.0,
            min(
                1.0,
                (float(highlight_before["mean_luma"]) - float(highlight_after["mean_luma"])) / float(highlight_before["mean_luma"]),
            ),
        )
    lowlight_detail_gain_ratio = 0.0
    if float(lowlight_detail_before["mean_detail"]) > 0:
        detail_gain = max(
            0.0,
            min(
                1.0,
                (float(lowlight_detail_after["mean_detail"]) - float(lowlight_detail_before["mean_detail"]))
                / float(lowlight_detail_before["mean_detail"]),
            ),
        )
        luma_gain = max(
            0.0,
            min(
                1.0,
                (float(lowlight_detail_after["mean_luma"]) - float(lowlight_detail_before["mean_luma"]))
                / max(1.0, 64.0 - float(lowlight_detail_before["mean_luma"])),
            ),
        )
        lowlight_detail_gain_ratio = round(min(1.0, (detail_gain * 0.55) + (luma_gain * 0.45)), 4)

    noise_report = {
        "diagnostic_key": "single_raw_noise_report_v1",
        "execution_mode": execution_mode,
        "profile_key": runtime_profile["profile_key"],
        "residual_before": residual_before_summary,
        "residual_after": residual_after_summary,
        "suppression_ratio": round(suppression_ratio, 4),
        "summary": _summarize_single_raw_noise_report(
            execution_mode,
            before_mean=before_mean,
            after_mean=after_mean,
            suppression_ratio=suppression_ratio,
            hotspot_coverage=float(residual_after_summary["hotspot_coverage"]),
        ),
    }
    artifact_guardrail = {
        "guardrail_key": runtime_profile["preview_guardrail"],
        "execution_mode": execution_mode,
        "delta_luma": delta_summary,
        "summary": _summarize_single_raw_artifact_guardrail(
            execution_mode,
            guardrail_key=str(runtime_profile["preview_guardrail"]),
            delta_mean_luma=float(delta_summary["mean_luma"]),
            delta_p95_luma=int(delta_summary["p95_luma"]),
        ),
    }
    artifact_suppression = {
        "strategy_key": "single_raw_artifact_suppression_v1",
        "execution_mode": execution_mode,
        "profile_key": runtime_profile["profile_key"],
        "texture_guard_strength": runtime_profile["texture_guard_strength"],
        "saturation_guard_strength": runtime_profile["saturation_guard_strength"],
        "contrast_guard_strength": runtime_profile["contrast_guard_strength"],
        "microcontrast_before": microcontrast_before,
        "microcontrast_after": microcontrast_after,
        "texture_suppression_ratio": round(texture_ratio, 4),
        "saturation_before": saturation_before,
        "saturation_after": saturation_after,
        "saturation_suppression_ratio": round(saturation_ratio, 4),
        "summary": _summarize_single_raw_artifact_suppression(
            execution_mode,
            texture_ratio=texture_ratio,
            saturation_ratio=saturation_ratio,
        ),
    }
    recovery_report = {
        "diagnostic_key": "single_raw_recovery_report_v1",
        "execution_mode": execution_mode,
        "profile_key": runtime_profile["profile_key"],
        "shadow_before": shadow_before,
        "shadow_after": shadow_after,
        "highlight_before": highlight_before,
        "highlight_after": highlight_after,
        "lowlight_detail_before": lowlight_detail_before,
        "lowlight_detail_after": lowlight_detail_after,
        "lowlight_detail_gain_ratio": round(lowlight_detail_gain_ratio, 4),
        "shadow_lift_ratio": round(shadow_lift_ratio, 4),
        "highlight_rolloff_ratio": round(highlight_rolloff_ratio, 4),
        "summary": _summarize_single_raw_recovery_report(
            execution_mode,
            shadow_lift_ratio=shadow_lift_ratio,
            highlight_rolloff_ratio=highlight_rolloff_ratio,
            lowlight_detail_gain_ratio=lowlight_detail_gain_ratio,
        ),
    }
    return {
        "noise_report": noise_report,
        "recovery_report": recovery_report,
        "artifact_guardrail": artifact_guardrail,
        "artifact_suppression": artifact_suppression,
    }


def _write_noise_map(preview_image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    noise_map = _build_noise_map_image(preview_image)
    ImageOps.autocontrast(noise_map).save(target_path, format="PNG")


def _build_lowlight_recovery_map_image(
    input_preview_image: Image.Image,
    output_preview_image: Image.Image,
) -> Image.Image:
    input_luma = input_preview_image.convert("L")
    output_luma = output_preview_image.convert("L")
    lowlight_mask = _build_lowlight_mask(input_preview_image, threshold=104)
    gained_luma = ImageChops.subtract(output_luma, input_luma)
    emphasized = ImageChops.multiply(gained_luma, lowlight_mask)
    return ImageOps.autocontrast(emphasized)


def write_single_raw_lowlight_map(
    input_preview_image: Image.Image,
    output_preview_image: Image.Image,
    target_path: Path,
) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lowlight_map = _build_lowlight_recovery_map_image(input_preview_image, output_preview_image)
    lowlight_map.save(target_path, format="PNG")


def materialize_single_raw_sensor_decode(
    raw_path: str,
    *,
    working_root: str | Path,
    input_preview_relative_path: str = "diagnostics/input_preview.jpg",
    recovery_baseline_relative_path: str = "diagnostics/recovery_baseline.jpg",
    execution_mode: SingleRawExecutionMode = "fast",
    preview_relative_path: str = "preview.jpg",
    scene_linear_relative_path: str = "scene_linear.tiff",
    noise_map_relative_path: str = "diagnostics/noise_map.png",
    lowlight_map_relative_path: str = "diagnostics/lowlight_recovery_map.png",
    crop_margin_ratio: float = 0.0,
    lens_correction: Mapping[str, Any] | None = None,
) -> SingleRawSensorDecodeResult | None:
    backend = resolve_sensor_decode_backend()
    if backend != RAWPY_BACKEND_KEY:
        return None

    decode_start = perf_counter()
    try:
        lens_correction_plan = lens_correction_plan_from_mapping(
            lens_correction,
            crop_margin_ratio=crop_margin_ratio,
        )
        scene_linear, details = _decode_with_rawpy(raw_path, execution_mode=execution_mode)
        if "runtime_profile" not in details:
            details["runtime_profile"] = build_single_raw_runtime_profile(execution_mode)
        scene_linear, scene_linear_lens_report = apply_lens_correction_to_scene_linear(
            scene_linear,
            lens_correction_plan,
        )
        scene_linear = _normalize_scene_linear_channels(scene_linear)
        preview_input = _build_preview_from_scene_linear(scene_linear)
        preview_input, preview_lens_report = apply_lens_correction_to_preview(
            preview_input,
            lens_correction_plan,
            include_distortion=False,
            include_vignette=False,
            include_lateral_ca=True,
        )
        lens_correction_report = merge_lens_correction_reports(
            lens_correction_plan,
            scene_linear_lens_report,
            preview_lens_report,
        )
        recovery_baseline = (
            _apply_single_raw_base_guardrail(preview_input, execution_mode=execution_mode)
            if execution_mode == "hq"
            else None
        )
        preview_image = apply_single_raw_preview_guardrail(preview_input, execution_mode=execution_mode)
        preview_diagnostics = build_single_raw_preview_diagnostics(
            preview_input,
            preview_image,
            execution_mode=execution_mode,
        )
        fallback_decision = build_single_raw_fallback_decision(
            execution_mode,
            materialization_source="sensor_decode",
            selected_variant=(
                "runtime_preview"
                if execution_mode == "fast"
                else "recovery_preview"
                if execution_mode == "hq"
                else "guarded_preview"
            ),
            noise_report=preview_diagnostics["noise_report"],
            artifact_suppression=preview_diagnostics["artifact_suppression"],
        )
        details["noise_report"] = preview_diagnostics["noise_report"]
        details["lens_correction_report"] = lens_correction_report
        details["recovery_report"] = preview_diagnostics["recovery_report"]
        details["artifact_guardrail"] = preview_diagnostics["artifact_guardrail"]
        details["artifact_suppression"] = preview_diagnostics["artifact_suppression"]
        details["fallback_decision"] = fallback_decision
    except Exception:
        return None
    decode_stage_ms = (perf_counter() - decode_start) * 1000.0

    working_root_path = Path(working_root)
    input_preview_path = working_root_path / input_preview_relative_path
    recovery_baseline_path = working_root_path / recovery_baseline_relative_path
    preview_path = working_root_path / preview_relative_path
    scene_linear_path = working_root_path / scene_linear_relative_path
    noise_map_path = working_root_path / noise_map_relative_path
    lowlight_map_path = working_root_path / lowlight_map_relative_path

    artifact_write_start = perf_counter()
    _write_scene_linear_tiff(scene_linear, scene_linear_path)
    input_preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_input.save(input_preview_path, format="JPEG", quality=95)
    if recovery_baseline is not None:
        recovery_baseline_path.parent.mkdir(parents=True, exist_ok=True)
        recovery_baseline.save(recovery_baseline_path, format="JPEG", quality=95)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_image.save(preview_path, format="JPEG", quality=95)
    _write_noise_map(preview_image, noise_map_path)
    write_single_raw_lowlight_map(preview_input, preview_image, lowlight_map_path)
    artifact_write_ms = (perf_counter() - artifact_write_start) * 1000.0
    timing_report = build_single_raw_timing_report(
        execution_mode,
        materialization_source="sensor_decode",
        decode_ms=decode_stage_ms,
        preview_pipeline_ms=0.0,
        artifact_write_ms=artifact_write_ms,
    )
    details["timing_report"] = timing_report

    runtime_profile_summary = str(details.get("runtime_profile", {}).get("summary") or "")
    notes = [
        f"Sensor RAW decode completed through the runtime backend before SingleRaw preview materialization ({execution_mode}).",
        "scene_linear TIFF and diagnostics were emitted from decoded sensor data instead of a companion preview fallback.",
    ]
    if runtime_profile_summary:
        notes.append(runtime_profile_summary)
    lens_correction_summary = str(details.get("lens_correction_report", {}).get("summary") or "")
    if lens_correction_summary:
        notes.append(lens_correction_summary)

    return SingleRawSensorDecodeResult(
        backend=backend,
        execution_mode=execution_mode,
        runtime_profile=str(details.get("runtime_profile", {}).get("profile_key") or build_single_raw_runtime_profile(execution_mode)["profile_key"]),
        input_preview_path=str(input_preview_path),
        recovery_baseline_path=str(recovery_baseline_path) if recovery_baseline is not None else None,
        preview_path=str(preview_path),
        scene_linear_path=str(scene_linear_path),
        scene_linear_format=SCENE_LINEAR_OUTPUT_FORMAT,
        noise_map_path=str(noise_map_path),
        lowlight_map_path=str(lowlight_map_path),
        width=int(scene_linear.shape[1]),
        height=int(scene_linear.shape[0]),
        channels=int(scene_linear.shape[2]),
        dtype=str(scene_linear.dtype),
        noise_report=dict(details.get("noise_report") or {}),
        lens_correction_report=dict(details.get("lens_correction_report") or {}),
        recovery_report=dict(details.get("recovery_report") or {}),
        artifact_guardrail=dict(details.get("artifact_guardrail") or {}),
        artifact_suppression=dict(details.get("artifact_suppression") or {}),
        fallback_decision=dict(details.get("fallback_decision") or {}),
        timing_report=dict(details.get("timing_report") or {}),
        details=details,
        notes=tuple(notes),
    )


def build_single_raw_runtime_health(
    *,
    sample_raw_path: str | None = None,
    sample_working_root: str | Path | None = None,
) -> dict[str, Any]:
    required_modules = {
        module_name: find_spec(module_name) is not None
        for module_name in ("rawpy", "numpy", "tifffile", "PIL")
    }
    preferred_backend = resolve_sensor_decode_backend()
    payload: dict[str, Any] = {
        "ok": preferred_backend is not None,
        "message": (
            "SingleRaw sensor decode backend is available."
            if preferred_backend is not None
            else "SingleRaw sensor decode backend is unavailable; planner will fall back to preview bootstrap artifacts."
        ),
        "preferred_backend": preferred_backend,
        "required_modules": required_modules,
        "supports_sensor_decode": preferred_backend is not None,
        "sample_raw_path": None,
        "sample_decode_ok": None,
        "sample_result": None,
    }

    if not sample_raw_path:
        return payload

    sample_path = Path(sample_raw_path).expanduser().resolve()
    payload["sample_raw_path"] = str(sample_path)
    if not sample_path.exists() or not sample_path.is_file():
        payload["sample_decode_ok"] = False
        payload["sample_result"] = {
            "error": "sample_raw_not_found",
        }
        payload["ok"] = False
        return payload

    if sample_working_root is None:
        working_root = sample_path.parent / "_single_raw_healthcheck"
    else:
        working_root = Path(sample_working_root).expanduser().resolve()

    result = materialize_single_raw_sensor_decode(
        str(sample_path),
        working_root=working_root,
    )
    payload["sample_decode_ok"] = result is not None
    payload["sample_result"] = (
        {
            "backend": result.backend,
            "execution_mode": result.execution_mode,
            "runtime_profile": result.runtime_profile,
            "input_preview_path": result.input_preview_path,
            "recovery_baseline_path": result.recovery_baseline_path,
            "preview_path": result.preview_path,
            "scene_linear_path": result.scene_linear_path,
            "scene_linear_format": result.scene_linear_format,
            "noise_map_path": result.noise_map_path,
            "lowlight_map_path": result.lowlight_map_path,
            "width": result.width,
            "height": result.height,
            "channels": result.channels,
            "dtype": result.dtype,
            "noise_report": result.noise_report,
            "lens_correction_report": result.lens_correction_report,
            "recovery_report": result.recovery_report,
            "artifact_guardrail": result.artifact_guardrail,
            "artifact_suppression": result.artifact_suppression,
            "fallback_decision": result.fallback_decision,
            "timing_report": result.timing_report,
            "details": result.details,
            "notes": list(result.notes),
        }
        if result is not None
        else {
            "error": "sample_decode_failed",
        }
    )
    if result is None:
        payload["ok"] = False
        if preferred_backend is not None:
            payload["message"] = "SingleRaw sensor decode backend is present, but the sample RAW decode failed."
    return payload
