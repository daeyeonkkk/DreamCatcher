from __future__ import annotations

import json
from pathlib import Path

from app.raw_engine_v2.isp.planner import DreamISPHandoffPlan
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render

from .studio_intake import StudioIntakePlan, dump_model, load_studio_intake_plan, write_json


def _clamp_slider(value: int) -> int:
    return max(0, min(100, int(value)))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _load_dreamisp_plan(payload: dict[str, object]) -> DreamISPHandoffPlan:
    plan_path = payload.get("plan_path")
    if isinstance(plan_path, str) and plan_path.strip():
        candidate = Path(plan_path)
        if candidate.exists() and candidate.is_file():
            return DreamISPHandoffPlan(**json.loads(candidate.read_text(encoding="utf-8")))
    return DreamISPHandoffPlan(**payload)


def _apply_workspace_sliders(
    plan: DreamISPHandoffPlan,
    *,
    strength: int,
    realism: int,
    preserve_texture: int,
) -> DreamISPHandoffPlan:
    normalized_strength = (_clamp_slider(strength) - 50) / 50.0
    normalized_realism = (_clamp_slider(realism) - 50) / 50.0
    normalized_texture = (_clamp_slider(preserve_texture) - 50) / 50.0

    payload = plan.model_dump()
    render_state = dict(payload.get("render_state") or {})
    white_balance = dict(render_state.get("white_balance") or {})
    tone = dict(render_state.get("tone") or {})
    color = dict(render_state.get("color") or {})
    detail = dict(render_state.get("detail") or {})

    white_balance["mode"] = "workspace_profile_v1"
    white_balance["temperature_delta"] = round(normalized_strength * 8.0, 2)
    white_balance["tint_delta"] = round(normalized_realism * 6.0, 2)

    tone["exposure_ev"] = round((normalized_strength * 0.65) + (normalized_realism * 0.12), 3)
    tone["contrast"] = round((normalized_strength * 22.0) - (normalized_realism * 8.0), 2)
    tone["highlights"] = round((-normalized_strength * 18.0) + (normalized_realism * 6.0), 2)
    tone["shadows"] = round((normalized_strength * 16.0) + (normalized_realism * 7.0), 2)
    tone["whites"] = round(normalized_strength * 10.0, 2)
    tone["blacks"] = round(-normalized_realism * 8.0, 2)

    color["saturation"] = round((normalized_strength * 10.0) + (normalized_realism * 4.0), 2)
    color["vibrance"] = round((normalized_strength * 14.0) + (normalized_realism * 10.0), 2)

    detail["clarity"] = round((normalized_strength * 8.0) + (normalized_texture * 18.0), 2)
    detail["dehaze"] = round((normalized_strength * 6.0) + (normalized_realism * 8.0), 2)

    render_state["white_balance"] = white_balance
    render_state["tone"] = tone
    render_state["color"] = color
    render_state["detail"] = detail
    render_state["workspace_sliders"] = {
        "strength": _clamp_slider(strength),
        "realism": _clamp_slider(realism),
        "preserve_texture": _clamp_slider(preserve_texture),
        "mapping_version": "workspace_profile_v1",
    }
    payload["render_state"] = render_state
    return DreamISPHandoffPlan(**payload)


def _apply_manual_controls(
    plan: DreamISPHandoffPlan,
    *,
    temperature_delta: float | None = None,
    tint_delta: float | None = None,
    exposure_ev: float | None = None,
    contrast: float | None = None,
    clarity: float | None = None,
) -> DreamISPHandoffPlan:
    payload = plan.model_dump()
    render_state = dict(payload.get("render_state") or {})
    white_balance = dict(render_state.get("white_balance") or {})
    tone = dict(render_state.get("tone") or {})
    detail = dict(render_state.get("detail") or {})

    if temperature_delta is not None:
        white_balance["temperature_delta"] = round(_clamp_float(temperature_delta, -100.0, 100.0), 2)
    if tint_delta is not None:
        white_balance["tint_delta"] = round(_clamp_float(tint_delta, -100.0, 100.0), 2)
    if temperature_delta is not None or tint_delta is not None:
        white_balance["mode"] = "manual_ui_v1"

    if exposure_ev is not None:
        tone["exposure_ev"] = round(_clamp_float(exposure_ev, -4.0, 4.0), 3)
    if contrast is not None:
        tone["contrast"] = round(_clamp_float(contrast, -100.0, 100.0), 2)

    if clarity is not None:
        detail["clarity"] = round(_clamp_float(clarity, -100.0, 100.0), 2)

    render_state["white_balance"] = white_balance
    render_state["tone"] = tone
    render_state["detail"] = detail
    render_state["manual_controls"] = {
        "temperature_delta": white_balance.get("temperature_delta"),
        "tint_delta": white_balance.get("tint_delta"),
        "exposure_ev": tone.get("exposure_ev"),
        "contrast": tone.get("contrast"),
        "clarity": detail.get("clarity"),
        "control_profile": "manual_ui_v1",
    }
    payload["render_state"] = render_state
    return DreamISPHandoffPlan(**payload)


def apply_dreamisp_workspace_profile(
    session_id: str,
    *,
    output_root: str = "outputs",
    strength: int,
    realism: int,
    preserve_texture: int,
    temperature_delta: float | None = None,
    tint_delta: float | None = None,
    exposure_ev: float | None = None,
    contrast: float | None = None,
    clarity: float | None = None,
) -> StudioIntakePlan:
    intake_plan = load_studio_intake_plan(session_id, output_root=output_root)
    if not isinstance(intake_plan.dreamisp_plan, dict):
        raise FileNotFoundError(f"DreamISP plan is not available for session: {session_id}")

    dreamisp_plan = _load_dreamisp_plan(intake_plan.dreamisp_plan)
    dreamisp_plan = _apply_workspace_sliders(
        dreamisp_plan,
        strength=strength,
        realism=realism,
        preserve_texture=preserve_texture,
    )
    dreamisp_plan = _apply_manual_controls(
        dreamisp_plan,
        temperature_delta=temperature_delta,
        tint_delta=tint_delta,
        exposure_ev=exposure_ev,
        contrast=contrast,
        clarity=clarity,
    )
    dreamisp_plan = materialize_dreamisp_lite_render(dreamisp_plan)

    intake_payload = dump_model(intake_plan)
    intake_payload["dreamisp_plan"] = dump_model(dreamisp_plan)
    intake_payload["editable_asset_path"] = dreamisp_plan.recommended_editable_source_path or intake_plan.editable_asset_path
    updated_intake = StudioIntakePlan(**intake_payload)
    write_json(Path(updated_intake.manifest_path), dump_model(updated_intake))
    return updated_intake
