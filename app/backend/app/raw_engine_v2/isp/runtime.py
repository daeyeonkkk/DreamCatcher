from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import tifffile

from .planner import DreamISPHandoffPlan


MODULE_STATUS = "phase1_runtime_wiring"
RENDER_BACKEND_KEY = "dreamisp_lite_preview_v1"


@dataclass(frozen=True)
class DreamISPRenderResult:
    backend: str
    source_kind: Literal["scene_linear", "preview_proxy"]
    preview_path: str
    width: int
    height: int
    mean_luminance: float
    notes: tuple[str, ...]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_rgb(array: np.ndarray) -> np.ndarray:
    if array.ndim == 2:
        array = np.stack([array, array, array], axis=-1)
    elif array.ndim == 3 and array.shape[2] == 1:
        array = np.repeat(array, 3, axis=2)
    elif array.ndim == 3 and array.shape[2] > 3:
        array = array[:, :, :3]
    return array


def _load_scene_linear_rgb(path: Path) -> np.ndarray:
    array = tifffile.imread(path)
    array = _coerce_rgb(np.asarray(array))
    normalized = array.astype(np.float32)
    if np.issubdtype(array.dtype, np.integer):
        denominator = float(np.iinfo(array.dtype).max)
    else:
        denominator = float(np.nanmax(normalized)) if np.isfinite(normalized).any() else 1.0
        denominator = max(denominator, 1e-6)
    return np.clip(normalized / denominator, 0.0, None)


def _load_preview_proxy_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.float32) / 255.0


def _apply_white_balance(linear: np.ndarray, render_state: dict[str, Any]) -> np.ndarray:
    wb = render_state.get("white_balance", {})
    temperature = _clamp(float(wb.get("temperature_delta", 0.0)) / 100.0, -1.0, 1.0)
    tint = _clamp(float(wb.get("tint_delta", 0.0)) / 100.0, -1.0, 1.0)
    gains = np.array(
        [
            1.0 + (0.22 * temperature) - (0.06 * tint),
            1.0 + (0.10 * tint),
            1.0 - (0.22 * temperature) - (0.06 * tint),
        ],
        dtype=np.float32,
    )
    gains = np.clip(gains, 0.55, 1.45)
    return linear * gains.reshape((1, 1, 3))


def _apply_linear_tone(linear: np.ndarray, render_state: dict[str, Any]) -> np.ndarray:
    tone = render_state.get("tone", {})
    exposure_ev = _clamp(float(tone.get("exposure_ev", 0.0)), -4.0, 4.0)
    contrast = _clamp(float(tone.get("contrast", 0.0)) / 100.0, -1.0, 1.0)
    highlights = _clamp(float(tone.get("highlights", 0.0)) / 100.0, -1.0, 1.0)
    shadows = _clamp(float(tone.get("shadows", 0.0)) / 100.0, -1.0, 1.0)
    whites = _clamp(float(tone.get("whites", 0.0)) / 100.0, -1.0, 1.0)
    blacks = _clamp(float(tone.get("blacks", 0.0)) / 100.0, -1.0, 1.0)

    linear = np.clip(linear * (2.0**exposure_ev), 0.0, None)
    normalized = linear / (1.0 + linear)
    linear = linear * (1.0 + (0.75 * shadows * (1.0 - normalized)))
    linear = linear * (1.0 - (0.55 * highlights * normalized))
    linear = np.clip(linear + (blacks * 0.03), 0.0, None)
    linear = linear * (1.0 + (0.20 * whites))

    display = linear / (1.0 + linear)
    display = np.power(np.clip(display, 0.0, 1.0), 1.0 / 2.2)
    display = np.clip(0.5 + ((display - 0.5) * (1.0 + (0.90 * contrast))), 0.0, 1.0)
    return display


def _apply_color_controls(display: np.ndarray, render_state: dict[str, Any]) -> np.ndarray:
    color = render_state.get("color", {})
    saturation = _clamp(float(color.get("saturation", 0.0)) / 100.0, -1.0, 1.0)
    vibrance = _clamp(float(color.get("vibrance", 0.0)) / 100.0, -1.0, 1.0)
    luminance = np.dot(display[..., :3], np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))
    gray = np.repeat(luminance[..., None], 3, axis=2)

    display = gray + ((display - gray) * (1.0 + saturation))
    chroma = np.mean(np.abs(display - gray), axis=2, keepdims=True)
    vibrance_gain = 1.0 + (vibrance * (1.0 - np.clip(chroma * 3.0, 0.0, 1.0)))
    display = gray + ((display - gray) * vibrance_gain)
    return np.clip(display, 0.0, 1.0)


def _apply_detail_controls(display: np.ndarray, render_state: dict[str, Any]) -> Image.Image:
    image = Image.fromarray(np.clip(display * 255.0, 0.0, 255.0).astype(np.uint8), mode="RGB")
    detail = render_state.get("detail", {})
    clarity = _clamp(float(detail.get("clarity", 0.0)) / 100.0, -1.0, 1.0)
    dehaze = _clamp(float(detail.get("dehaze", 0.0)) / 100.0, -1.0, 1.0)

    if clarity > 0.0:
        image = image.filter(
            ImageFilter.UnsharpMask(
                radius=1.6 + (clarity * 0.8),
                percent=int(115 + (clarity * 120)),
                threshold=2,
            )
        )
    elif clarity < 0.0:
        image = image.filter(ImageFilter.GaussianBlur(radius=abs(clarity) * 1.2))

    if dehaze != 0.0:
        contrast_factor = 1.0 + (0.30 * dehaze)
        color_factor = 1.0 + (0.12 * dehaze)
        image = ImageEnhance.Contrast(image).enhance(max(0.4, contrast_factor))
        image = ImageEnhance.Color(image).enhance(max(0.4, color_factor))

    return image


def _save_preview(image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(target_path, format="JPEG", quality=95)


def render_dreamisp_preview(
    plan: DreamISPHandoffPlan,
) -> DreamISPRenderResult | None:
    scene_linear_path = Path(plan.scene_linear_path)
    preview_proxy_path = Path(plan.preview_path) if plan.preview_path else None
    notes: list[str] = []

    if scene_linear_path.is_file():
        linear = _load_scene_linear_rgb(scene_linear_path)
        source_kind: Literal["scene_linear", "preview_proxy"] = "scene_linear"
        notes.append("DreamISP-lite가 장면 선형 마스터에서 편집 미리보기를 렌더했습니다.")
    elif preview_proxy_path is not None and preview_proxy_path.is_file():
        linear = _load_preview_proxy_rgb(preview_proxy_path)
        source_kind = "preview_proxy"
        notes.append("장면 선형 마스터가 없어 DreamISP-lite가 미리보기 프록시를 대체 경로로 사용했습니다.")
    else:
        return None

    linear = _apply_white_balance(linear, plan.render_state)
    display = _apply_linear_tone(linear, plan.render_state)
    display = _apply_color_controls(display, plan.render_state)
    rendered_image = _apply_detail_controls(display, plan.render_state)

    preview_path = Path(plan.working_root) / "editable_preview.jpg"
    _save_preview(rendered_image, preview_path)

    with Image.open(preview_path) as saved_preview:
        saved_rgb = np.asarray(saved_preview.convert("RGB"), dtype=np.float32) / 255.0
    mean_luminance = float(
        np.mean(np.dot(saved_rgb[..., :3], np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)))
    )

    return DreamISPRenderResult(
        backend=RENDER_BACKEND_KEY,
        source_kind=source_kind,
        preview_path=str(preview_path),
        width=int(rendered_image.width),
        height=int(rendered_image.height),
        mean_luminance=mean_luminance,
        notes=tuple(notes),
    )


def materialize_dreamisp_lite_render(
    plan: DreamISPHandoffPlan,
) -> DreamISPHandoffPlan:
    result = render_dreamisp_preview(plan)
    if result is None:
        return plan

    payload = plan.model_dump()
    payload["materialization_status"] = "preview_rendered"
    payload["render_preview_path"] = result.preview_path
    payload["render_preview_exists"] = Path(result.preview_path).is_file()
    payload["render_source_kind"] = result.source_kind
    payload["render_backend"] = result.backend
    payload["recommended_editable_source_path"] = result.preview_path
    payload["render_state"]["source"]["recommended_editable_source_path"] = result.preview_path
    payload["render_state"]["output"] = {
        "editable_preview_path": result.preview_path,
        "backend": result.backend,
        "source_kind": result.source_kind,
        "width": result.width,
        "height": result.height,
        "mean_luminance": result.mean_luminance,
    }
    payload["notes"] = [
        *payload.get("notes", []),
        *result.notes,
        "DreamISP-lite가 편집 미리보기를 기록해 Studio가 장면 선형 마스터를 바꾸지 않고도 02_manual에서 편집 흐름에 들어갈 수 있습니다.",
    ]
    updated_plan = DreamISPHandoffPlan(**payload)

    report_payload = {
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "status": updated_plan.materialization_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_stage": updated_plan.source_stage,
        "source_item_key": updated_plan.source_item_key,
        "source_engine_key": updated_plan.source_engine_key,
        "source_engine_version": updated_plan.source_engine_version,
        "scene_linear_path": updated_plan.scene_linear_path,
        "scene_linear_exists": updated_plan.scene_linear_exists,
        "preview_path": updated_plan.preview_path,
        "preview_exists": updated_plan.preview_exists,
        "recommended_editable_source_path": updated_plan.recommended_editable_source_path,
        "render_preview_path": updated_plan.render_preview_path,
        "render_preview_exists": updated_plan.render_preview_exists,
        "render_source_kind": updated_plan.render_source_kind,
        "render_backend": updated_plan.render_backend,
        "handoff_ready": updated_plan.scene_linear_exists or updated_plan.preview_exists,
        "source_report_path": updated_plan.source_report_path,
        "source_diagnostics_manifest_path": updated_plan.source_diagnostics_manifest_path,
        "render_state_summary": {
            "white_balance": updated_plan.render_state.get("white_balance"),
            "tone": updated_plan.render_state.get("tone"),
            "color": updated_plan.render_state.get("color"),
            "detail": updated_plan.render_state.get("detail"),
        },
        "render_result": asdict(result),
        "notes": list(updated_plan.notes),
    }
    _write_json(Path(updated_plan.render_state_path), updated_plan.render_state)
    _write_json(Path(updated_plan.report_path), report_payload)
    _write_json(Path(updated_plan.plan_path), updated_plan.model_dump())
    return updated_plan
