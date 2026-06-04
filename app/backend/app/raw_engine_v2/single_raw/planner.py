from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Mapping

from PIL import Image, ImageChops, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from app.raw_engine_v2.shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA, SceneLinearFormat
from app.raw_engine_v2.shared.engine_registry import get_engine_descriptor
from app.raw_engine_v2.shared.lens_correction import (
    apply_lens_correction_to_preview,
    build_lens_correction_plan,
    lens_correction_plan_from_mapping,
)
from app.raw_engine_v2.shared.metadata import normalize_raw_metadata
from app.raw_engine_v2.shared.noise_model import estimate_noise_profile
from app.raw_engine_v2.shared.raw_io import build_decode_plan, build_raw_input_bundle
from app.raw_engine_v2.shared.scene_linear import build_scene_linear_plan
from app.raw_engine_v2.single_raw.runtime import (
    _apply_single_raw_base_guardrail,
    apply_single_raw_preview_guardrail,
    apply_single_raw_preview_holdout,
    build_single_raw_fallback_decision,
    build_single_raw_preview_diagnostics,
    build_single_raw_runtime_profile,
    build_single_raw_timing_report,
    materialize_single_raw_sensor_decode,
    write_single_raw_lowlight_map,
)


MODULE_STATUS = "phase1_foundation"
INPUT_PREVIEW_RELATIVE_PATH = "diagnostics/input_preview.jpg"
RECOVERY_BASELINE_RELATIVE_PATH = "diagnostics/recovery_baseline.jpg"
NOISE_MAP_RELATIVE_PATH = "diagnostics/noise_map.png"
LOWLIGHT_MAP_RELATIVE_PATH = "diagnostics/lowlight_recovery_map.png"
SingleRawQualityPreset = Literal["balanced", "safe"]
SingleRawModePreference = Literal["auto", "fast", "hq", "safe"]
SingleRawExecutionMode = Literal["fast", "hq", "safe"]


class SingleRawExpectedArtifact(BaseModel):
    kind: str
    path: str
    required: bool = False
    content_type: str | None = None
    notes: str | None = None


class SingleRawModePolicy(BaseModel):
    requested_quality_preset: SingleRawQualityPreset
    requested_mode: SingleRawExecutionMode
    resolved_mode: SingleRawExecutionMode
    delivery_intent: Literal["direct_edit", "guarded_preview", "maximum_recovery"]
    decode_priority: Literal["latency_first", "guardrail_first", "quality_first"]
    denoise_strategy: Literal["preview_first", "conservative_holdout", "maximum_recovery_pending"]
    artifact_discipline: Literal["minimal", "guarded", "extended"]
    summary: str
    notes: list[str] = Field(default_factory=list)


class SingleRawFoundationPlan(BaseModel):
    engine_key: str
    engine_version: str
    engine_lifecycle: str
    status: Literal["phase1_foundation"] = "phase1_foundation"
    source_path: str
    item_key: str
    working_root: str
    manifest_path: str
    report_path: str
    diagnostics_manifest_path: str
    input_bundle_kind: str
    selected_frame_role: str
    quality_preset: SingleRawQualityPreset = "balanced"
    mode_preference: SingleRawModePreference = "auto"
    requested_mode: SingleRawExecutionMode = "fast"
    resolved_mode: SingleRawExecutionMode = "fast"
    mode_policy: SingleRawModePolicy
    metadata_source: Literal["provided", "exiftool", "default"]
    materialization_status: Literal["planned", "preview_bootstrapped", "sensor_decoded"] = "planned"
    preview_source_path: str | None = None
    materialized_input_preview_path: str | None = None
    materialized_recovery_baseline_path: str | None = None
    materialized_preview_path: str | None = None
    materialized_noise_map_path: str | None = None
    materialized_lowlight_map_path: str | None = None
    materialized_timing_report: dict[str, Any] | None = None
    decode: dict[str, Any]
    metadata: dict[str, Any]
    noise_profile: dict[str, Any]
    lens_correction: dict[str, Any]
    scene_linear: dict[str, Any]
    expected_artifacts: list[SingleRawExpectedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")
    return cleaned or "single_raw_item"


def resolve_exiftool_binary() -> str | None:
    return shutil.which("exiftool")


def extract_raw_metadata_with_exiftool(raw_path: str) -> dict[str, Any] | None:
    exiftool = resolve_exiftool_binary()
    if not exiftool:
        return None

    try:
        result = subprocess.run(
            [exiftool, "-json", raw_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return None


def _artifact_root(session_root: str | Path | None, item_key: str) -> Path:
    if session_root is None:
        return Path("01_single_raw") / item_key
    return Path(session_root) / "01_single_raw" / item_key


def _build_expected_artifacts(working_root: Path) -> list[SingleRawExpectedArtifact]:
    artifacts: list[SingleRawExpectedArtifact] = []
    for slot in PHASE0_ARTIFACT_SCHEMA.required_slots:
        artifacts.append(
            SingleRawExpectedArtifact(
                kind=slot.key,
                path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()[slot.key]),
                required=slot.required,
                content_type=slot.content_type,
                notes=slot.description,
            )
        )
    for diagnostic in PHASE0_ARTIFACT_SCHEMA.optional_diagnostics:
        if diagnostic.key != "noise_map":
            continue
        artifacts.append(
            SingleRawExpectedArtifact(
                kind=diagnostic.key,
                path=str(working_root / diagnostic.relative_path),
                required=diagnostic.required,
                notes=diagnostic.description,
            )
        )
    return artifacts


def build_single_raw_mode_policy(
    quality_preset: SingleRawQualityPreset,
    mode_preference: SingleRawModePreference = "auto",
) -> SingleRawModePolicy:
    if mode_preference == "hq":
        return SingleRawModePolicy(
            requested_quality_preset=quality_preset,
            requested_mode="hq",
            resolved_mode="hq",
            delivery_intent="maximum_recovery",
            decode_priority="quality_first",
            denoise_strategy="maximum_recovery_pending",
            artifact_discipline="extended",
            summary="HQ policy prioritizes recovery headroom, gentler guardrails, and a more deliberate baseline before manual editing.",
            notes=[
                "HQ mode uses the dedicated recovery runtime profile instead of the latency-first fast path.",
                "DreamCatcher keeps the same preview, scene-linear, and diagnostics contract while surfacing a more recovery-biased baseline in the UI.",
            ],
        )
    if mode_preference == "safe" or quality_preset == "safe":
        return SingleRawModePolicy(
            requested_quality_preset=quality_preset,
            requested_mode="safe",
            resolved_mode="safe",
            delivery_intent="guarded_preview",
            decode_priority="guardrail_first",
            denoise_strategy="conservative_holdout",
            artifact_discipline="guarded",
            summary="Safe policy keeps direct RAW sessions conservative and guardrail-first before manual editing.",
            notes=[
                "Safe mode currently shares the phase1 runtime wiring, but records a stricter output intent for fallback and diagnostics.",
                "DreamCatcher keeps preview, scene-linear bridge, and diagnostics visible so the operator can inspect risk before heavier edits.",
            ],
        )
    if mode_preference == "fast":
        return SingleRawModePolicy(
            requested_quality_preset=quality_preset,
            requested_mode="fast",
            resolved_mode="fast",
            delivery_intent="direct_edit",
            decode_priority="latency_first",
            denoise_strategy="preview_first",
            artifact_discipline="minimal",
            summary="Fast policy gets a direct RAW session to an editable baseline quickly and keeps the scene-linear bridge ready.",
            notes=[
                "Fast mode prefers a sensor decode when available and falls back to preview bootstrap artifacts without blocking DreamISP handoff.",
                "This explicit fast preference keeps the direct RAW path on the latency-first profile even when other recovery modes are available.",
            ],
        )
    return SingleRawModePolicy(
        requested_quality_preset="balanced",
        requested_mode="fast",
        resolved_mode="fast",
        delivery_intent="direct_edit",
        decode_priority="latency_first",
        denoise_strategy="preview_first",
        artifact_discipline="minimal",
        summary="Fast policy gets a direct RAW session to an editable baseline quickly and keeps the scene-linear bridge ready.",
        notes=[
            "Balanced studio intake currently maps to DreamRAW-One fast policy while dedicated HQ kernels are still pending.",
            "Fast mode prefers a sensor decode when available and falls back to preview bootstrap artifacts without blocking DreamISP handoff.",
        ],
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _open_corrected_preview(
    source_path: Path,
    *,
    lens_correction: Mapping[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    with Image.open(source_path) as image:
        corrected = ImageOps.exif_transpose(image).convert("RGB").copy()
    lens_plan = lens_correction_plan_from_mapping(lens_correction)
    return apply_lens_correction_to_preview(corrected, lens_plan)


def _write_preview_artifact(image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(target_path, format="JPEG", quality=95)


def _srgb_channel_to_linear(value: int) -> int:
    normalized = max(0.0, min(1.0, float(value) / 255.0))
    if normalized <= 0.04045:
        linear = normalized / 12.92
    else:
        linear = ((normalized + 0.055) / 1.055) ** 2.4
    return int(round(linear * 255.0))


def _write_scene_linear_fallback(image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lut = [_srgb_channel_to_linear(index) for index in range(256)] * len(image.getbands())
    linearized = image.point(lut)
    linearized.save(target_path, format="TIFF", compression="tiff_deflate")


def _write_noise_map(image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    grayscale = image.convert("L")
    baseline = grayscale.filter(ImageFilter.GaussianBlur(radius=1.6))
    noise_map = ImageChops.difference(grayscale, baseline)
    ImageOps.autocontrast(noise_map).save(target_path, format="PNG")


def _update_expected_artifact(
    artifacts: list[dict[str, Any]],
    *,
    kind: str,
    path: str | None = None,
    content_type: str | None = None,
    notes: str | None = None,
) -> None:
    for artifact in artifacts:
        if artifact.get("kind") != kind:
            continue
        if path is not None:
            artifact["path"] = path
        if content_type is not None:
            artifact["content_type"] = content_type
        if notes is not None:
            artifact["notes"] = notes
        return


def build_single_raw_foundation_plan(
    raw_path: str,
    *,
    session_root: str | Path | None = None,
    metadata_payload: Mapping[str, Any] | None = None,
    preferred_scene_linear_format: SceneLinearFormat | None = None,
    quality_preset: SingleRawQualityPreset = "balanced",
    mode_preference: SingleRawModePreference = "auto",
) -> SingleRawFoundationPlan:
    bundle = build_raw_input_bundle([raw_path])
    frame = bundle.reference_frame()
    decode_plan = build_decode_plan(frame)

    metadata_source: Literal["provided", "exiftool", "default"]
    extracted_metadata = dict(metadata_payload) if metadata_payload is not None else extract_raw_metadata_with_exiftool(frame.path)
    if metadata_payload is not None:
        metadata_source = "provided"
    elif extracted_metadata is not None:
        metadata_source = "exiftool"
    else:
        metadata_source = "default"
        extracted_metadata = {}

    normalized_metadata = normalize_raw_metadata(extracted_metadata, source_path=frame.path)
    noise_profile = estimate_noise_profile(normalized_metadata)
    lens_correction = build_lens_correction_plan(normalized_metadata)
    scene_linear_plan = build_scene_linear_plan(
        normalized_metadata,
        noise_profile=noise_profile,
        lens_correction=lens_correction,
        preferred_format=preferred_scene_linear_format,
    )
    mode_policy = build_single_raw_mode_policy(quality_preset, mode_preference=mode_preference)

    engine = get_engine_descriptor("dreamraw_one_v2")
    item_key = _slug(Path(frame.file_name).stem)
    working_root = _artifact_root(session_root, item_key)
    expected_artifacts = _build_expected_artifacts(working_root)

    notes = [
        "SingleRaw v2 foundation plan binds shared RAW I/O, metadata normalization, noise profiling, lens correction, and scene-linear planning.",
    ]
    if metadata_source == "default":
        notes.append("EXIF metadata was unavailable, so DreamCatcher used conservative default metadata values for the planning layer.")
    elif metadata_source == "exiftool":
        notes.append("EXIF metadata was extracted with ExifTool for the direct RAW session.")
    else:
        notes.append("Caller-provided metadata was used for the SingleRaw planning layer.")
    notes.append(
        f"Direct RAW intake requested the {mode_policy.resolved_mode} execution policy from the {quality_preset} quality preset and the {mode_preference} mode preference."
    )

    return SingleRawFoundationPlan(
        engine_key=engine.key,
        engine_version=engine.version,
        engine_lifecycle=engine.lifecycle,
        source_path=frame.path,
        item_key=item_key,
        working_root=str(working_root),
        manifest_path=str(working_root / "single_raw_plan.json"),
        report_path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()["report"]),
        diagnostics_manifest_path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()["diagnostics_manifest"]),
        input_bundle_kind=bundle.kind,
        selected_frame_role=frame.frame_role,
        quality_preset=quality_preset,
        mode_preference=mode_preference,
        requested_mode=mode_policy.requested_mode,
        resolved_mode=mode_policy.resolved_mode,
        mode_policy=mode_policy,
        metadata_source=metadata_source,
        decode=asdict(decode_plan),
        metadata=asdict(normalized_metadata),
        noise_profile=asdict(noise_profile),
        lens_correction=asdict(lens_correction),
        scene_linear=asdict(scene_linear_plan),
        expected_artifacts=expected_artifacts,
        notes=notes,
    )


def materialize_single_raw_foundation_plan(
    plan: SingleRawFoundationPlan,
    *,
    source_preview_path: str | None = None,
) -> SingleRawFoundationPlan:
    materialization_started_at = perf_counter()
    working_root = Path(plan.working_root)
    preview_artifact = next((artifact for artifact in plan.expected_artifacts if artifact.kind == "preview"), None)
    preview_source = Path(source_preview_path).resolve() if source_preview_path else None
    materialized_input_preview_path: str | None = None
    materialized_recovery_baseline_path: str | None = None
    materialized_preview_path: str | None = None
    materialized_scene_linear_path: str | None = None
    materialized_scene_linear_format: str | None = None
    materialized_noise_map_path: str | None = None
    materialized_lowlight_map_path: str | None = None
    noise_report: dict[str, Any] = {}
    lens_correction_report: dict[str, Any] = {}
    recovery_report: dict[str, Any] = {}
    artifact_guardrail: dict[str, Any] = {}
    artifact_suppression: dict[str, Any] = {}
    fallback_decision: dict[str, Any] = {}
    timing_report: dict[str, Any] = {}
    materialization_status: Literal["planned", "preview_bootstrapped", "sensor_decoded"] = "planned"
    payload = plan.model_dump()
    runtime_decode = materialize_single_raw_sensor_decode(
        plan.source_path,
        working_root=working_root,
        input_preview_relative_path=INPUT_PREVIEW_RELATIVE_PATH,
        recovery_baseline_relative_path=RECOVERY_BASELINE_RELATIVE_PATH,
        execution_mode=plan.resolved_mode,
        preview_relative_path=PHASE0_ARTIFACT_SCHEMA.expected_paths()["preview"],
        scene_linear_relative_path=PHASE0_ARTIFACT_SCHEMA.expected_paths(
            str(payload["scene_linear"].get("fallback_format") or PHASE0_ARTIFACT_SCHEMA.scene_linear_fallback_format)
        )["scene_linear"],
        noise_map_relative_path=NOISE_MAP_RELATIVE_PATH,
        lowlight_map_relative_path=LOWLIGHT_MAP_RELATIVE_PATH,
        crop_margin_ratio=float(plan.lens_correction.get("crop_margin_ratio", 0.0)),
        lens_correction=plan.lens_correction,
    )

    if runtime_decode is not None:
        materialized_input_preview_path = runtime_decode.input_preview_path
        materialized_recovery_baseline_path = runtime_decode.recovery_baseline_path
        materialized_preview_path = runtime_decode.preview_path
        materialized_scene_linear_path = runtime_decode.scene_linear_path
        materialized_scene_linear_format = runtime_decode.scene_linear_format
        materialized_noise_map_path = runtime_decode.noise_map_path
        materialized_lowlight_map_path = runtime_decode.lowlight_map_path
        noise_report = runtime_decode.noise_report
        lens_correction_report = runtime_decode.lens_correction_report
        recovery_report = runtime_decode.recovery_report
        artifact_guardrail = runtime_decode.artifact_guardrail
        artifact_suppression = runtime_decode.artifact_suppression
        fallback_decision = runtime_decode.fallback_decision
        timing_report = runtime_decode.timing_report
        materialization_status = "sensor_decoded"
    elif preview_artifact is not None and preview_source is not None and preview_source.exists():
        preview_pipeline_started_at = perf_counter()
        preview_baseline, lens_correction_report = _open_corrected_preview(
            preview_source,
            lens_correction=plan.lens_correction,
        )
        recovery_baseline_preview = (
            _apply_single_raw_base_guardrail(preview_baseline, execution_mode=plan.resolved_mode)
            if plan.resolved_mode == "hq"
            else None
        )
        corrected_preview = apply_single_raw_preview_guardrail(preview_baseline, execution_mode=plan.resolved_mode)
        selected_preview = (
            apply_single_raw_preview_holdout(corrected_preview, execution_mode=plan.resolved_mode)
            if plan.resolved_mode == "safe"
            else corrected_preview
        )
        preview_diagnostics = build_single_raw_preview_diagnostics(
            preview_baseline,
            selected_preview,
            execution_mode=plan.resolved_mode,
        )
        preview_pipeline_ms = (perf_counter() - preview_pipeline_started_at) * 1000.0
        fallback_decision = build_single_raw_fallback_decision(
            plan.resolved_mode,
            materialization_source="preview_bootstrap",
            selected_variant=(
                "preview_holdout"
                if plan.resolved_mode == "safe"
                else "recovery_preview"
                if plan.resolved_mode == "hq"
                else "guarded_preview"
            ),
            noise_report=preview_diagnostics["noise_report"],
            artifact_suppression=preview_diagnostics["artifact_suppression"],
        )
        target_input_preview_path = working_root / INPUT_PREVIEW_RELATIVE_PATH
        _write_preview_artifact(preview_baseline, target_input_preview_path)
        materialized_input_preview_path = str(target_input_preview_path)
        artifact_write_started_at = perf_counter()
        if recovery_baseline_preview is not None:
            target_recovery_baseline_path = working_root / RECOVERY_BASELINE_RELATIVE_PATH
            _write_preview_artifact(recovery_baseline_preview, target_recovery_baseline_path)
            materialized_recovery_baseline_path = str(target_recovery_baseline_path)
        target_preview_path = Path(preview_artifact.path)
        _write_preview_artifact(selected_preview, target_preview_path)
        materialized_preview_path = str(target_preview_path)
        scene_linear_format = str(payload["scene_linear"].get("fallback_format") or PHASE0_ARTIFACT_SCHEMA.scene_linear_fallback_format)
        target_scene_linear_path = working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths(scene_linear_format)["scene_linear"]
        _write_scene_linear_fallback(selected_preview, target_scene_linear_path)
        materialized_scene_linear_path = str(target_scene_linear_path)
        materialized_scene_linear_format = scene_linear_format
        target_noise_map_path = working_root / NOISE_MAP_RELATIVE_PATH
        _write_noise_map(selected_preview, target_noise_map_path)
        materialized_noise_map_path = str(target_noise_map_path)
        target_lowlight_map_path = working_root / LOWLIGHT_MAP_RELATIVE_PATH
        write_single_raw_lowlight_map(preview_baseline, selected_preview, target_lowlight_map_path)
        materialized_lowlight_map_path = str(target_lowlight_map_path)
        noise_report = preview_diagnostics["noise_report"]
        recovery_report = preview_diagnostics["recovery_report"]
        artifact_guardrail = preview_diagnostics["artifact_guardrail"]
        artifact_suppression = preview_diagnostics["artifact_suppression"]
        artifact_write_ms = (perf_counter() - artifact_write_started_at) * 1000.0
        timing_report = build_single_raw_timing_report(
            plan.resolved_mode,
            materialization_source="preview_bootstrap",
            decode_ms=0.0,
            preview_pipeline_ms=preview_pipeline_ms,
            artifact_write_ms=artifact_write_ms,
        )
        materialization_status = "preview_bootstrapped"

    planner_total_ms = (perf_counter() - materialization_started_at) * 1000.0
    if timing_report:
        timing_report["planner_total_ms"] = round(planner_total_ms, 3)
        timing_report["summary"] = (
            f"{timing_report.get('summary', '').rstrip('.')} | planner total {planner_total_ms:.1f}ms."
        ).strip()

    payload["preview_source_path"] = str(preview_source) if preview_source is not None else None
    payload["materialized_input_preview_path"] = materialized_input_preview_path
    payload["materialized_recovery_baseline_path"] = materialized_recovery_baseline_path
    payload["materialized_preview_path"] = materialized_preview_path
    payload["materialized_noise_map_path"] = materialized_noise_map_path
    payload["materialized_lowlight_map_path"] = materialized_lowlight_map_path
    payload["materialized_timing_report"] = timing_report or None
    payload["materialization_status"] = materialization_status
    payload["decode"]["runtime_backend"] = runtime_decode.backend if runtime_decode is not None else None
    payload["decode"]["runtime_sensor_decode"] = runtime_decode is not None
    payload["decode"]["runtime_decode_details"] = runtime_decode.details if runtime_decode is not None else None
    payload["decode"]["runtime_notes"] = list(runtime_decode.notes) if runtime_decode is not None else []
    payload["decode"]["runtime_profile"] = runtime_decode.runtime_profile if runtime_decode is not None else build_single_raw_runtime_profile(plan.resolved_mode)["profile_key"]
    payload["decode"]["runtime_execution_mode"] = runtime_decode.execution_mode if runtime_decode is not None else plan.resolved_mode
    payload["decode"]["runtime_profile_summary"] = (
        runtime_decode.details.get("runtime_profile", {}).get("summary")
        if runtime_decode is not None
        else build_single_raw_runtime_profile(plan.resolved_mode)["summary"]
    )
    payload["decode"]["noise_report"] = noise_report
    payload["decode"]["noise_report_summary"] = noise_report.get("summary")
    payload["decode"]["lens_correction_report"] = lens_correction_report
    payload["decode"]["lens_correction_summary"] = lens_correction_report.get("summary")
    payload["decode"]["recovery_report"] = recovery_report
    if recovery_report:
        payload["decode"]["recovery_report"]["map_path"] = materialized_lowlight_map_path
        payload["decode"]["recovery_report"]["baseline_path"] = materialized_recovery_baseline_path
    payload["decode"]["recovery_report_summary"] = recovery_report.get("summary")
    payload["decode"]["artifact_guardrail"] = artifact_guardrail
    payload["decode"]["artifact_guardrail_summary"] = artifact_guardrail.get("summary")
    payload["decode"]["artifact_suppression"] = artifact_suppression
    payload["decode"]["artifact_suppression_summary"] = artifact_suppression.get("summary")
    payload["decode"]["fallback_decision"] = fallback_decision
    payload["decode"]["fallback_summary"] = fallback_decision.get("summary")
    payload["decode"]["timing_report"] = timing_report
    payload["decode"]["timing_summary"] = timing_report.get("summary") if timing_report else None
    payload["scene_linear"]["materialized_path"] = materialized_scene_linear_path
    payload["scene_linear"]["materialized_format"] = materialized_scene_linear_format
    payload["scene_linear"]["materialization_source"] = (
        "sensor_decode_tiff"
        if runtime_decode is not None
        else "preview_bootstrap_linearized_tiff"
        if materialized_scene_linear_path is not None
        else None
    )
    payload["scene_linear"]["materialization_notes"] = (
        [
            "Sensor RAW decode runtime produced the current scene_linear TIFF artifact.",
            "This keeps the contract aligned with the future DreamISP path while EXR output is still pending.",
        ]
        if runtime_decode is not None
        else
        [
            "Preview-derived TIFF fallback was emitted because sensor RAW decode is not wired yet.",
            "This artifact is for contract continuity and Studio plumbing validation, not final image quality evaluation.",
        ]
        if materialized_scene_linear_path is not None
        else []
    )
    if runtime_decode is not None:
        payload["notes"] = [
            *payload.get("notes", []),
            "SingleRaw runtime preferred a sensor decode backend over the preview bootstrap path.",
        ]

    if materialized_scene_linear_path is not None:
        payload["scene_linear"]["target_relative_path"] = str(Path(materialized_scene_linear_path).relative_to(working_root))
        _update_expected_artifact(
            payload["expected_artifacts"],
            kind="scene_linear",
            path=materialized_scene_linear_path,
            content_type="image/tiff",
            notes=(
                "Sensor-decoded TIFF fallback emitted by the SingleRaw runtime."
                if runtime_decode is not None
                else "Preview-derived linearized TIFF fallback until sensor RAW decode is wired."
            ),
        )
    _update_expected_artifact(
        payload["expected_artifacts"],
        kind="noise_map",
        content_type="image/png",
        notes=(
            "Sensor-decode diagnostic heatmap derived from the scene-linear runtime output."
            if runtime_decode is not None
            else "Preview-derived diagnostic heatmap that highlights fine residual detail before real denoise wiring."
        ),
    )
    updated_plan = SingleRawFoundationPlan(**payload)

    diagnostics_payload = {
        "schema_id": PHASE0_ARTIFACT_SCHEMA.schema_id,
        "schema_version": PHASE0_ARTIFACT_SCHEMA.schema_version,
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality_preset": updated_plan.quality_preset,
        "requested_mode": updated_plan.requested_mode,
        "resolved_mode": updated_plan.resolved_mode,
        "mode_policy": updated_plan.mode_policy.model_dump(),
        "runtime_profile": updated_plan.decode.get("runtime_profile"),
        "runtime_profile_summary": updated_plan.decode.get("runtime_profile_summary"),
        "noise_report": updated_plan.decode.get("noise_report"),
        "lens_correction_report": updated_plan.decode.get("lens_correction_report"),
        "recovery_report": updated_plan.decode.get("recovery_report"),
        "artifact_guardrail": updated_plan.decode.get("artifact_guardrail"),
        "artifact_suppression": updated_plan.decode.get("artifact_suppression"),
        "fallback_decision": updated_plan.decode.get("fallback_decision"),
        "timing_report": updated_plan.decode.get("timing_report"),
        "materialization_status": materialization_status,
        "preview_source_path": str(preview_source) if preview_source is not None else None,
        "materialized_input_preview_path": materialized_input_preview_path,
        "materialized_recovery_baseline_path": materialized_recovery_baseline_path,
        "materialized_preview_path": materialized_preview_path,
        "materialized_lowlight_map_path": materialized_lowlight_map_path,
        "runtime_backend": runtime_decode.backend if runtime_decode is not None else None,
        "required_artifacts": [
            {
                "key": artifact.kind,
                "path": artifact.path,
                "required": artifact.required,
                "exists": Path(artifact.path).is_file(),
            }
            for artifact in updated_plan.expected_artifacts
            if artifact.kind in PHASE0_ARTIFACT_SCHEMA.slot_keys()
        ],
        "diagnostics": [
            {
                "key": artifact.kind,
                "path": artifact.path,
                "required": artifact.required,
                "exists": Path(artifact.path).is_file(),
            }
            for artifact in updated_plan.expected_artifacts
            if artifact.kind in {"noise_map", "motion_map", "confidence_map"}
        ]
        + (
            [
                {
                    "key": "recovery_baseline",
                    "path": materialized_recovery_baseline_path,
                    "required": False,
                    "exists": bool(materialized_recovery_baseline_path and Path(materialized_recovery_baseline_path).is_file()),
                }
            ]
            if materialized_recovery_baseline_path
            else []
        )
        + (
            [
                {
                    "key": "lowlight_recovery_map",
                    "path": materialized_lowlight_map_path,
                    "required": False,
                    "exists": bool(materialized_lowlight_map_path and Path(materialized_lowlight_map_path).is_file()),
                }
            ]
            if materialized_lowlight_map_path
            else []
        ),
        "noise_profile": {
            "model_key": updated_plan.noise_profile.get("model_key"),
            "confidence": updated_plan.noise_profile.get("confidence"),
            "iso": updated_plan.noise_profile.get("iso"),
        },
        "lens_correction": {
            "distortion_model": updated_plan.lens_correction.get("distortion_model"),
            "apply_distortion": updated_plan.lens_correction.get("apply_distortion"),
            "apply_vignette": updated_plan.lens_correction.get("apply_vignette"),
            "apply_lateral_ca": updated_plan.lens_correction.get("apply_lateral_ca"),
            "crop_margin_ratio": updated_plan.lens_correction.get("crop_margin_ratio"),
            "summary": updated_plan.decode.get("lens_correction_summary"),
        },
        "scene_linear": {
            "target_relative_path": updated_plan.scene_linear.get("target_relative_path"),
            "preferred_format": updated_plan.scene_linear.get("preferred_format"),
            "fallback_format": updated_plan.scene_linear.get("fallback_format"),
            "materialized_format": updated_plan.scene_linear.get("materialized_format"),
            "materialized_path": updated_plan.scene_linear.get("materialized_path"),
            "materialization_source": updated_plan.scene_linear.get("materialization_source"),
        },
    }
    _write_json(Path(updated_plan.diagnostics_manifest_path), diagnostics_payload)

    report_notes = [
        *updated_plan.notes,
        updated_plan.mode_policy.summary,
        (
            "SingleRaw sensor decode runtime wrote preview/scene_linear/diagnostics directly from the RAW frame."
            if runtime_decode is not None
            else "Structured preview bootstrap writes preview/report/diagnostics into the SingleRaw session root."
        ),
        (
            "When preview bootstrap is available, DreamCatcher also emits a preview-derived scene_linear TIFF fallback and noise_map diagnostic for contract continuity."
            if runtime_decode is None
            else "The current runtime still emits TIFF as the scene-linear bridge artifact until EXR output is wired."
        ),
        (
            "Safe mode applies a guarded preview profile before manual editing so the operator starts from a more conservative baseline."
            if updated_plan.resolved_mode == "safe"
            else "HQ mode keeps more recovery headroom in the baseline preview before manual editing starts."
            if updated_plan.resolved_mode == "hq"
            else "Fast mode keeps the preview path latency-first so the operator can move into manual editing quickly."
        ),
        updated_plan.decode.get("noise_report_summary"),
        updated_plan.decode.get("lens_correction_summary"),
        updated_plan.decode.get("recovery_report_summary"),
        updated_plan.decode.get("artifact_guardrail_summary"),
        updated_plan.decode.get("artifact_suppression_summary"),
        updated_plan.decode.get("fallback_summary"),
        updated_plan.decode.get("timing_summary"),
    ]
    report_payload = {
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "status": materialization_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": updated_plan.source_path,
        "quality_preset": updated_plan.quality_preset,
        "requested_mode": updated_plan.requested_mode,
        "resolved_mode": updated_plan.resolved_mode,
        "mode_summary": updated_plan.mode_policy.summary,
        "runtime_profile": updated_plan.decode.get("runtime_profile"),
        "runtime_profile_summary": updated_plan.decode.get("runtime_profile_summary"),
        "noise_report": updated_plan.decode.get("noise_report"),
        "noise_report_summary": updated_plan.decode.get("noise_report_summary"),
        "lens_correction_report": updated_plan.decode.get("lens_correction_report"),
        "lens_correction_summary": updated_plan.decode.get("lens_correction_summary"),
        "recovery_report": updated_plan.decode.get("recovery_report"),
        "recovery_report_summary": updated_plan.decode.get("recovery_report_summary"),
        "artifact_guardrail": updated_plan.decode.get("artifact_guardrail"),
        "artifact_guardrail_summary": updated_plan.decode.get("artifact_guardrail_summary"),
        "artifact_suppression": updated_plan.decode.get("artifact_suppression"),
        "artifact_suppression_summary": updated_plan.decode.get("artifact_suppression_summary"),
        "fallback_decision": updated_plan.decode.get("fallback_decision"),
        "fallback_summary": updated_plan.decode.get("fallback_summary"),
        "timing_report": updated_plan.decode.get("timing_report"),
        "timing_summary": updated_plan.decode.get("timing_summary"),
        "preview_source_path": str(preview_source) if preview_source is not None else None,
        "materialized_input_preview_path": materialized_input_preview_path,
        "materialized_recovery_baseline_path": materialized_recovery_baseline_path,
        "materialized_preview_path": materialized_preview_path,
        "materialized_scene_linear_path": materialized_scene_linear_path,
        "materialized_scene_linear_format": materialized_scene_linear_format,
        "materialized_noise_map_path": materialized_noise_map_path,
        "materialized_lowlight_map_path": materialized_lowlight_map_path,
        "runtime_backend": runtime_decode.backend if runtime_decode is not None else None,
        "metadata_source": updated_plan.metadata_source,
        "camera_key": updated_plan.metadata.get("camera_key"),
        "lens_key": updated_plan.metadata.get("lens_key"),
        "iso": updated_plan.metadata.get("iso"),
        "exposure_seconds": updated_plan.metadata.get("exposure_seconds"),
        "scene_linear_target": updated_plan.scene_linear.get("target_relative_path"),
        "notes": [note for note in report_notes if isinstance(note, str) and note],
    }
    _write_json(Path(updated_plan.report_path), report_payload)
    _write_json(Path(updated_plan.manifest_path), updated_plan.model_dump())
    return updated_plan
