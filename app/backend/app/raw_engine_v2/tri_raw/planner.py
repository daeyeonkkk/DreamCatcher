from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, Field

from app.raw_engine_v2.shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA, SceneLinearFormat
from app.raw_engine_v2.shared.engine_registry import get_engine_descriptor
from app.raw_engine_v2.shared.lens_correction import build_lens_correction_plan
from app.raw_engine_v2.shared.metadata import normalize_raw_metadata, summarize_bracket_metadata
from app.raw_engine_v2.shared.noise_model import estimate_noise_profile, summarize_bracket_noise
from app.raw_engine_v2.shared.raw_io import build_raw_input_bundle
from app.raw_engine_v2.shared.scene_linear import build_scene_linear_plan


MODULE_STATUS = "phase1_foundation"


class TriRawExpectedArtifact(BaseModel):
    kind: str
    path: str
    required: bool = False
    content_type: str | None = None
    notes: str | None = None


class TriRawFoundationPlan(BaseModel):
    engine_key: str
    engine_version: str
    engine_lifecycle: str
    status: Literal["phase1_foundation"] = "phase1_foundation"
    bracket_id: str
    source_paths: list[str]
    working_root: str
    plan_path: str
    report_path: str
    diagnostics_manifest_path: str
    input_bundle_kind: str
    reference_frame_index: int
    reference_frame_role: str
    metadata_source: Literal["provided", "default"]
    materialization_status: Literal["planned", "foundation_written"] = "planned"
    frame_decodes: list[dict[str, Any]]
    frame_metadata: list[dict[str, Any]]
    bracket_metadata: dict[str, Any]
    frame_noise_profiles: list[dict[str, Any]]
    noise_summary: dict[str, Any]
    lens_correction: dict[str, Any]
    scene_linear: dict[str, Any]
    expected_artifacts: list[TriRawExpectedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _artifact_root(session_root: str | Path | None, bracket_id: str) -> Path:
    if session_root is None:
        return Path("01_rawprep") / bracket_id
    return Path(session_root) / "01_rawprep" / bracket_id


def _build_expected_artifacts(working_root: Path) -> list[TriRawExpectedArtifact]:
    artifacts: list[TriRawExpectedArtifact] = []
    for slot in PHASE0_ARTIFACT_SCHEMA.required_slots:
        artifacts.append(
            TriRawExpectedArtifact(
                kind=slot.key,
                path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()[slot.key]),
                required=slot.required,
                content_type=slot.content_type,
                notes=slot.description,
            )
        )
    for diagnostic in PHASE0_ARTIFACT_SCHEMA.optional_diagnostics:
        artifacts.append(
            TriRawExpectedArtifact(
                kind=diagnostic.key,
                path=str(working_root / diagnostic.relative_path),
                required=diagnostic.required,
                notes=diagnostic.description,
            )
        )
    return artifacts


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_tri_raw_foundation_plan(
    raw_paths: Sequence[str],
    *,
    bracket_id: str = "bracket_01",
    session_root: str | Path | None = None,
    metadata_payloads: Sequence[Mapping[str, Any]] | None = None,
    preferred_scene_linear_format: SceneLinearFormat | None = None,
) -> TriRawFoundationPlan:
    bundle = build_raw_input_bundle(list(raw_paths), bracket_id=bracket_id)
    if bundle.kind != "raw_bracket" or len(bundle.frames) not in {3, 9}:
        raise ValueError("TriRaw foundation plan requires exactly three or nine RAW files")

    metadata_source: Literal["provided", "default"] = "provided" if metadata_payloads is not None else "default"
    if metadata_payloads is not None and len(metadata_payloads) != len(bundle.frames):
        raise ValueError("metadata_payloads must align with the RAW frames in the bracket")

    normalized_frames = [
        normalize_raw_metadata(
            dict(metadata_payloads[index]) if metadata_payloads is not None else {},
            source_path=frame.path,
        )
        for index, frame in enumerate(bundle.frames)
    ]
    bracket_metadata = summarize_bracket_metadata(normalized_frames)
    reference_frame_index = bracket_metadata.reference_frame_index
    reference_frame = bundle.frames[reference_frame_index]
    reference_metadata = normalized_frames[reference_frame_index]
    frame_noise_profiles = [estimate_noise_profile(metadata) for metadata in normalized_frames]
    noise_summary = summarize_bracket_noise(frame_noise_profiles)
    lens_correction = build_lens_correction_plan(reference_metadata)
    scene_linear_plan = build_scene_linear_plan(
        reference_metadata,
        noise_profile=frame_noise_profiles[reference_frame_index],
        lens_correction=lens_correction,
        preferred_format=preferred_scene_linear_format,
    )

    engine = get_engine_descriptor("dreamraw_tri_v2")
    working_root = _artifact_root(session_root, bracket_id)
    expected_artifacts = _build_expected_artifacts(working_root)

    notes = [
        "TriRaw v2 foundation plan binds shared RAW I/O, bracket metadata normalization, noise estimation, lens planning, and scene-linear planning.",
        f"Reference frame role is `{reference_frame.frame_role}` with exposure order `{bracket_metadata.exposure_order}`.",
    ]
    if bracket_metadata.mixed_sensor_calibration:
        notes.append("Bracket frames report mixed sensor calibration metadata; later fusion stages must guard against calibration drift.")
    notes.extend(bracket_metadata.notes)
    if metadata_source == "default":
        notes.append("Frame metadata payloads were not provided, so TriRaw planning used conservative defaults for all bracket frames.")
    else:
        notes.append("Caller-provided frame metadata was used for the TriRaw planning layer.")

    return TriRawFoundationPlan(
        engine_key=engine.key,
        engine_version=engine.version,
        engine_lifecycle=engine.lifecycle,
        bracket_id=bracket_id,
        source_paths=list(bundle.frame_paths()),
        working_root=str(working_root),
        plan_path=str(working_root / "tri_raw_plan.json"),
        report_path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()["report"]),
        diagnostics_manifest_path=str(working_root / PHASE0_ARTIFACT_SCHEMA.expected_paths()["diagnostics_manifest"]),
        input_bundle_kind=bundle.kind,
        reference_frame_index=reference_frame_index,
        reference_frame_role=reference_frame.frame_role,
        metadata_source=metadata_source,
        frame_decodes=[asdict(decode) for decode in bundle.build_decode_plans()],
        frame_metadata=[asdict(metadata) for metadata in normalized_frames],
        bracket_metadata=asdict(bracket_metadata),
        frame_noise_profiles=[asdict(profile) for profile in frame_noise_profiles],
        noise_summary=asdict(noise_summary),
        lens_correction=asdict(lens_correction),
        scene_linear=asdict(scene_linear_plan),
        expected_artifacts=expected_artifacts,
        notes=notes,
    )


def materialize_tri_raw_foundation_plan(
    plan: TriRawFoundationPlan,
) -> TriRawFoundationPlan:
    payload = plan.model_dump()
    payload["materialization_status"] = "foundation_written"
    updated_plan = TriRawFoundationPlan(**payload)

    scene_linear_artifact = next(
        (artifact for artifact in updated_plan.expected_artifacts if artifact.kind == "scene_linear"),
        None,
    )
    report_payload = {
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "status": updated_plan.materialization_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bracket_id": updated_plan.bracket_id,
        "frame_count": len(updated_plan.source_paths),
        "source_paths": updated_plan.source_paths,
        "metadata_source": updated_plan.metadata_source,
        "reference_frame_index": updated_plan.reference_frame_index,
        "reference_frame_role": updated_plan.reference_frame_role,
        "exposure_order": updated_plan.bracket_metadata.get("exposure_order"),
        "mixed_sensor_calibration": updated_plan.bracket_metadata.get("mixed_sensor_calibration"),
        "recommended_artifact": scene_linear_artifact.path if scene_linear_artifact is not None else None,
        "scene_linear_target": updated_plan.scene_linear.get("target_relative_path"),
        "notes": [
            *updated_plan.notes,
            "TriRaw foundation report was written before executable fusion lands, so deliverable preview/scene_linear imagery may still be missing.",
        ],
    }
    _write_json(Path(updated_plan.report_path), report_payload)
    _write_json(Path(updated_plan.plan_path), updated_plan.model_dump())

    diagnostics_payload = {
        "schema_id": PHASE0_ARTIFACT_SCHEMA.schema_id,
        "schema_version": PHASE0_ARTIFACT_SCHEMA.schema_version,
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "materialization_status": updated_plan.materialization_status,
        "required_artifacts": [
            {
                "key": artifact.kind,
                "path": artifact.path,
                "required": artifact.required,
                "exists": Path(artifact.path).is_file() or artifact.kind == "diagnostics_manifest",
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
        ],
        "bracket_metadata": updated_plan.bracket_metadata,
        "noise_summary": updated_plan.noise_summary,
        "lens_correction": {
            "distortion_model": updated_plan.lens_correction.get("distortion_model"),
            "apply_distortion": updated_plan.lens_correction.get("apply_distortion"),
            "crop_margin_ratio": updated_plan.lens_correction.get("crop_margin_ratio"),
        },
        "scene_linear": {
            "target_relative_path": updated_plan.scene_linear.get("target_relative_path"),
            "preferred_format": updated_plan.scene_linear.get("preferred_format"),
            "fallback_format": updated_plan.scene_linear.get("fallback_format"),
        },
    }
    _write_json(Path(updated_plan.diagnostics_manifest_path), diagnostics_payload)
    return updated_plan
