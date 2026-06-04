from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Mapping

from PIL import Image

from .metadata import NormalizedRawMetadata


MODULE_STATUS = "phase1_applied_module"


@dataclass(frozen=True)
class LensCorrectionPlan:
    camera_key: str
    lens_key: str
    apply_distortion: bool
    apply_vignette: bool
    apply_lateral_ca: bool
    distortion_model: str
    crop_margin_ratio: float
    vignette_strength: float
    chroma_strength: float
    notes: tuple[str, ...] = ()


def lens_correction_plan_from_mapping(
    payload: Mapping[str, Any] | LensCorrectionPlan | None,
    *,
    crop_margin_ratio: float = 0.0,
) -> LensCorrectionPlan:
    if isinstance(payload, LensCorrectionPlan):
        return payload

    mapping = dict(payload or {})

    def _string(name: str, default: str) -> str:
        value = mapping.get(name)
        return value if isinstance(value, str) and value.strip() else default

    def _float(name: str, default: float) -> float:
        value = mapping.get(name)
        if isinstance(value, (int, float)):
            return float(value)
        return float(default)

    notes = tuple(note for note in mapping.get("notes", ()) if isinstance(note, str))
    return LensCorrectionPlan(
        camera_key=_string("camera_key", "unknown"),
        lens_key=_string("lens_key", "unknown"),
        apply_distortion=bool(mapping.get("apply_distortion", False)),
        apply_vignette=bool(mapping.get("apply_vignette", False)),
        apply_lateral_ca=bool(mapping.get("apply_lateral_ca", False)),
        distortion_model=_string("distortion_model", "identity"),
        crop_margin_ratio=_float("crop_margin_ratio", crop_margin_ratio),
        vignette_strength=_float("vignette_strength", 0.0),
        chroma_strength=_float("chroma_strength", 0.0),
        notes=notes,
    )


def build_lens_correction_plan(
    metadata: NormalizedRawMetadata,
    *,
    conservative: bool = True,
) -> LensCorrectionPlan:
    lens_known = metadata.lens_key != "unknown"
    focal_length = metadata.focal_length_mm or 0.0
    aperture = metadata.aperture_f_number or 0.0
    wide_angle = 0.0 < focal_length <= 28.0
    fast_aperture = 0.0 < aperture < 3.5

    crop_margin_ratio = 0.0
    if lens_known:
        crop_margin_ratio = 0.02
        if wide_angle:
            crop_margin_ratio = 0.04 if conservative else 0.03

    notes: list[str] = []
    if not lens_known:
        notes.append("Lens metadata is unavailable; distortion correction falls back to an identity plan.")
    if wide_angle:
        notes.append("Wide-angle focal length detected; reserve additional crop margin for distortion correction.")
    if fast_aperture:
        notes.append("Fast aperture detected; keep vignette compensation available in the default plan.")

    return LensCorrectionPlan(
        camera_key=metadata.camera_key,
        lens_key=metadata.lens_key,
        apply_distortion=lens_known,
        apply_vignette=lens_known or fast_aperture,
        apply_lateral_ca=lens_known,
        distortion_model="brown_conrady" if lens_known else "identity",
        crop_margin_ratio=crop_margin_ratio,
        vignette_strength=0.35 if fast_aperture else 0.2 if lens_known else 0.0,
        chroma_strength=0.25 if lens_known else 0.0,
        notes=tuple(notes),
    )


def _import_numpy() -> Any:
    return import_module("numpy")


def _compute_crop_margins(width: int, height: int, crop_margin_ratio: float) -> tuple[int, int]:
    if crop_margin_ratio <= 0 or width < 32 or height < 32:
        return 0, 0
    margin_x = int(width * crop_margin_ratio / 2)
    margin_y = int(height * crop_margin_ratio / 2)
    if width - (margin_x * 2) < 32 or height - (margin_y * 2) < 32:
        return 0, 0
    return margin_x, margin_y


def _build_radial_gain(height: int, width: int, *, strength: float) -> Any:
    numpy = _import_numpy()
    if height <= 0 or width <= 0 or strength <= 0:
        return numpy.ones((max(height, 1), max(width, 1)), dtype=numpy.float32), 0.0
    y = numpy.linspace(-1.0, 1.0, height, dtype=numpy.float32)[:, None]
    x = numpy.linspace(-1.0, 1.0, width, dtype=numpy.float32)[None, :]
    radius = numpy.sqrt((x * x) + (y * y)) / numpy.float32(2.0**0.5)
    radius = numpy.clip(radius, 0.0, 1.0)
    gain_peak = min(0.18, max(0.0, float(strength)) * 0.28)
    gain = 1.0 + (gain_peak * numpy.power(radius, 1.85))
    return gain.astype(numpy.float32), round(gain_peak, 4)


def _clip_array_like(array: Any, *, reference_dtype: Any) -> Any:
    numpy = _import_numpy()
    if reference_dtype.kind in {"u", "i"}:
        info = numpy.iinfo(reference_dtype)
        clipped = numpy.clip(array, info.min, info.max)
        return clipped.astype(reference_dtype)
    if reference_dtype.kind == "f":
        clipped = numpy.clip(array, 0.0, 1.0 if float(array.max()) <= 1.25 else float(array.max()))
        return clipped.astype(reference_dtype)
    return array.astype(reference_dtype)


def _empty_lens_correction_report(plan: LensCorrectionPlan) -> dict[str, Any]:
    return {
        "diagnostic_key": "single_raw_lens_correction_report_v1",
        "camera_key": plan.camera_key,
        "lens_key": plan.lens_key,
        "distortion_model": plan.distortion_model,
        "apply_distortion": plan.apply_distortion,
        "apply_vignette": plan.apply_vignette,
        "apply_lateral_ca": plan.apply_lateral_ca,
        "crop_margin_ratio": round(float(plan.crop_margin_ratio), 4),
        "crop_applied": False,
        "crop_pixels_x": 0,
        "crop_pixels_y": 0,
        "scene_linear_vignette_gain_peak": 0.0,
        "preview_vignette_gain_peak": 0.0,
        "preview_lateral_ca_suppression_ratio": 0.0,
        "input_width": None,
        "input_height": None,
        "output_width": None,
        "output_height": None,
        "applied_steps": [],
        "notes": list(plan.notes),
        "summary": "",
    }


def _summarize_lens_correction_report(report: Mapping[str, Any]) -> str:
    steps: list[str] = []
    if report.get("crop_applied"):
        steps.append(f"왜곡 보정을 위해 크롭 여유 {float(report.get('crop_margin_ratio', 0.0)) * 100:.1f}%를 적용했습니다")
    preview_vignette = float(report.get("preview_vignette_gain_peak", 0.0) or 0.0)
    scene_linear_vignette = float(report.get("scene_linear_vignette_gain_peak", 0.0) or 0.0)
    if max(preview_vignette, scene_linear_vignette) > 0:
        gain_peak = max(preview_vignette, scene_linear_vignette)
        steps.append(f"비네팅 보정을 최대 {gain_peak * 100:.0f}%까지 보정했습니다")
    lateral_ca_ratio = float(report.get("preview_lateral_ca_suppression_ratio", 0.0) or 0.0)
    if lateral_ca_ratio > 0:
        steps.append(f"경계 색수차를 {lateral_ca_ratio * 100:.0f}% 수준으로 억제했습니다")
    if not steps:
        return "광학 보정 계획은 읽었지만 현재 세션에서는 추가 보정이 적용되지 않았습니다."
    return " ".join(step.rstrip(".") + "." for step in steps)


def merge_lens_correction_reports(plan: LensCorrectionPlan, *reports: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = _empty_lens_correction_report(plan)
    for report in reports:
        if not isinstance(report, Mapping):
            continue
        for key in ("input_width", "input_height"):
            value = report.get(key)
            if isinstance(value, int) and value > 0 and merged[key] in {None, 0}:
                merged[key] = value
        for key in ("output_width", "output_height"):
            value = report.get(key)
            if isinstance(value, int) and value > 0:
                merged[key] = value
        for key in ("crop_applied", "apply_distortion", "apply_vignette", "apply_lateral_ca"):
            if report.get(key) is True:
                merged[key] = True
        for key in ("crop_pixels_x", "crop_pixels_y"):
            value = report.get(key)
            if isinstance(value, int):
                merged[key] = max(int(merged[key]), value)
        for key in ("crop_margin_ratio", "scene_linear_vignette_gain_peak", "preview_vignette_gain_peak", "preview_lateral_ca_suppression_ratio"):
            value = report.get(key)
            if isinstance(value, (int, float)):
                merged[key] = round(max(float(merged[key]), float(value)), 4)
        for step in report.get("applied_steps", []):
            if isinstance(step, str) and step not in merged["applied_steps"]:
                merged["applied_steps"].append(step)
        for note in report.get("notes", []):
            if isinstance(note, str) and note not in merged["notes"]:
                merged["notes"].append(note)
    merged["summary"] = _summarize_lens_correction_report(merged)
    return merged


def apply_lens_correction_to_preview(
    image: Image.Image,
    plan: LensCorrectionPlan,
    *,
    include_distortion: bool = True,
    include_vignette: bool = True,
    include_lateral_ca: bool = True,
) -> tuple[Image.Image, dict[str, Any]]:
    numpy = _import_numpy()
    corrected = image.convert("RGB")
    report = _empty_lens_correction_report(plan)
    report["input_width"], report["input_height"] = corrected.size

    if include_distortion and plan.apply_distortion:
        width, height = corrected.size
        margin_x, margin_y = _compute_crop_margins(width, height, plan.crop_margin_ratio)
        if margin_x > 0 or margin_y > 0:
            corrected = corrected.crop((margin_x, margin_y, width - margin_x, height - margin_y))
            report["crop_applied"] = True
            report["crop_pixels_x"] = margin_x
            report["crop_pixels_y"] = margin_y
            report["applied_steps"].append("distortion_crop")

    if include_vignette and plan.apply_vignette and plan.vignette_strength > 0:
        array = numpy.asarray(corrected, dtype=numpy.float32)
        gain, gain_peak = _build_radial_gain(array.shape[0], array.shape[1], strength=plan.vignette_strength)
        corrected_array = array * gain[:, :, None]
        corrected = Image.fromarray(numpy.clip(corrected_array + 0.5, 0.0, 255.0).astype(numpy.uint8), mode="RGB")
        report["preview_vignette_gain_peak"] = gain_peak
        report["applied_steps"].append("preview_vignette_compensation")

    if include_lateral_ca and plan.apply_lateral_ca and plan.chroma_strength > 0:
        array = numpy.asarray(corrected, dtype=numpy.float32)
        radius, _ = _build_radial_gain(array.shape[0], array.shape[1], strength=1.0)
        radius = numpy.clip((radius - 1.0) / max(1e-6, 0.18), 0.0, 1.0)
        chroma = numpy.ptp(array, axis=2) / 255.0
        mask = numpy.clip(radius * chroma * min(0.75, float(plan.chroma_strength) * 2.2), 0.0, 0.65)
        if float(mask.max()) > 0:
            luma = (
                (array[:, :, 0] * 0.2126)
                + (array[:, :, 1] * 0.7152)
                + (array[:, :, 2] * 0.0722)
            )
            neutral = numpy.stack((luma, luma, luma), axis=2)
            corrected_array = (array * (1.0 - mask[:, :, None])) + (neutral * mask[:, :, None])
            corrected = Image.fromarray(numpy.clip(corrected_array + 0.5, 0.0, 255.0).astype(numpy.uint8), mode="RGB")
            report["preview_lateral_ca_suppression_ratio"] = round(float(mask.mean()), 4)
            report["applied_steps"].append("preview_lateral_ca_suppression")

    report["output_width"], report["output_height"] = corrected.size
    report["summary"] = _summarize_lens_correction_report(report)
    return corrected, report


def apply_lens_correction_to_scene_linear(
    scene_linear: Any,
    plan: LensCorrectionPlan,
) -> tuple[Any, dict[str, Any]]:
    numpy = _import_numpy()
    corrected = numpy.asarray(scene_linear)
    report = _empty_lens_correction_report(plan)
    if corrected.ndim < 2:
        report["summary"] = _summarize_lens_correction_report(report)
        return corrected, report

    report["input_width"] = int(corrected.shape[1])
    report["input_height"] = int(corrected.shape[0])

    if plan.apply_distortion:
        margin_x, margin_y = _compute_crop_margins(int(corrected.shape[1]), int(corrected.shape[0]), plan.crop_margin_ratio)
        if margin_x > 0 or margin_y > 0:
            corrected = corrected[margin_y : corrected.shape[0] - margin_y, margin_x : corrected.shape[1] - margin_x]
            report["crop_applied"] = True
            report["crop_pixels_x"] = margin_x
            report["crop_pixels_y"] = margin_y
            report["applied_steps"].append("distortion_crop")

    if plan.apply_vignette and plan.vignette_strength > 0:
        gain, gain_peak = _build_radial_gain(int(corrected.shape[0]), int(corrected.shape[1]), strength=plan.vignette_strength)
        corrected = corrected.astype(numpy.float32)
        if corrected.ndim == 2:
            corrected = corrected * gain
        else:
            corrected = corrected * gain[:, :, None]
        corrected = _clip_array_like(corrected, reference_dtype=numpy.asarray(scene_linear).dtype)
        report["scene_linear_vignette_gain_peak"] = gain_peak
        report["applied_steps"].append("scene_linear_vignette_compensation")

    report["output_width"] = int(corrected.shape[1])
    report["output_height"] = int(corrected.shape[0])
    report["summary"] = _summarize_lens_correction_report(report)
    return corrected, report
