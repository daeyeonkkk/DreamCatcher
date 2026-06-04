from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Literal

from pydantic import BaseModel, Field

from .rawprep_benchmark_service import (
    _load_optional_manifest,
    _sample_entries,
    _single_raw_manifest_path,
    _tri_raw_manifest_path,
)
from .rawprep_contract import ReferencePolicy, RawPrepJobRequest, build_job_plan
from .rawprep_service import detect_rawprep_tools, execute_rawprep_job, initialize_rawprep_job
from .studio_intake import StudioIntakeRequest, build_studio_intake_plan
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkLocalE2ESmokeRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    run_root: str = "_benchmark_runs/local_e2e"
    single_raw_sample_id: str | None = None
    tri_raw_sample_id: str | None = None
    single_raw_quality_preset: Literal["balanced", "safe"] = "balanced"
    single_raw_mode_preference: Literal["auto", "fast", "hq", "safe"] = "fast"
    tri_raw_reference_policy: ReferencePolicy = "auto"


class RawPrepBenchmarkLocalE2EFlow(BaseModel):
    sample_id: str | None = None
    session_id: str | None = None
    session_root: str | None = None
    entry_mode: str | None = None
    status: str = "missing"
    source_preview_path: str | None = None
    foundation_report_path: str | None = None
    foundation_preview_path: str | None = None
    scene_linear_path: str | None = None
    dreamisp_render_preview_path: str | None = None
    dreamisp_render_state_path: str | None = None
    rawprep_job_path: str | None = None
    runtime_profile: str | None = None
    runtime_backend: str | None = None
    ready_for_edit_ui: bool = False
    issues: list[str] = Field(default_factory=list)
    summary: str = ""


class RawPrepBenchmarkLocalE2ESmoke(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    smoke_path: str
    run_root: str
    status: str = "failed"
    ok: bool = False
    single_raw: RawPrepBenchmarkLocalE2EFlow
    tri_raw: RawPrepBenchmarkLocalE2EFlow
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Local E2E smoke output_dir must stay inside the configured output root.") from exc
    return resolved


def _resolve_run_root(path_value: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Local E2E smoke run_root must stay inside the configured output root.") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _smoke_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_local_e2e_smoke.json"


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_repo_or_output_path(path_value: str, *, output_root: str) -> Path:
    normalized = path_value.strip()
    if not normalized:
        raise ValueError("Path value is required.")
    root = repo_root().resolve()
    output_root_path = resolve_output_root(output_root).resolve()
    raw = Path(normalized)
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    for allowed_root in (root, output_root_path):
        try:
            candidate.relative_to(allowed_root)
            return candidate
        except ValueError:
            continue
    raise ValueError(f"Path must stay inside the repository or output root: {path_value}")


def _load_manifest_entry(manifest_path: Path, *, sample_id: str | None) -> dict:
    payload = _load_optional_manifest(manifest_path)
    if payload is None:
        raise FileNotFoundError(f"Benchmark manifest was not found: {manifest_path}")
    entries = [entry for entry in _sample_entries(payload) if str(entry.get("sample_id") or "").strip()]
    if not entries:
        raise ValueError(f"Benchmark manifest has no usable sample entries: {manifest_path}")
    if sample_id is None:
        return entries[0]
    for entry in entries:
        if str(entry.get("sample_id") or "").strip() == sample_id:
            return entry
    raise ValueError(f"Requested sample_id was not found in manifest: {sample_id}")


def _slug(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in value.strip())
    normalized = normalized.strip("_")
    return normalized or "sample"


def _prepare_clean_session_root(run_root: Path, *, session_id: str) -> Path:
    session_root = run_root / session_id
    if session_root.exists():
        try:
            session_root.resolve().relative_to(run_root.resolve())
        except ValueError as exc:
            raise ValueError("Refusing to remove a session directory outside the configured run_root.") from exc
        shutil.rmtree(session_root)
    return session_root


def _existing_repo_relative(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    return _repo_relative_string(path)


def _path_exists(path_value: str | None) -> bool:
    return bool(path_value and Path(path_value).exists())


def _read_json_object(path_value: str | None) -> dict:
    if not path_value or not Path(path_value).exists():
        return {}
    payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _first_existing_path(*path_values: Any) -> str | None:
    for path_value in path_values:
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        if Path(path_value).exists():
            return path_value
    return None


def _required_artifact_path(manifest_payload: dict, key: str) -> str | None:
    required_artifacts = manifest_payload.get("required_artifacts")
    if not isinstance(required_artifacts, list):
        return None
    for artifact in required_artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("key") or "").strip() != key:
            continue
        path_value = artifact.get("path")
        if isinstance(path_value, str) and path_value.strip():
            return path_value
    return None


def _job_artifact_path(record: Any, kind: str) -> str | None:
    artifacts = getattr(record, "artifacts", [])
    for artifact in artifacts:
        if getattr(artifact, "kind", None) != kind:
            continue
        path_value = getattr(artifact, "path", None)
        if isinstance(path_value, str) and path_value.strip():
            return path_value
    return None


def _run_single_raw_flow(
    entry: dict,
    *,
    output_root: str,
    run_root: Path,
    quality_preset: Literal["balanced", "safe"],
    mode_preference: Literal["auto", "fast", "hq", "safe"],
) -> RawPrepBenchmarkLocalE2EFlow:
    sample_id = str(entry.get("sample_id") or "").strip()
    raw_path_value = str(entry.get("raw_path") or "").strip()
    if not raw_path_value:
        return RawPrepBenchmarkLocalE2EFlow(
            sample_id=sample_id or None,
            status="failed",
            issues=["Official SingleRaw manifest entry is missing raw_path."],
            summary="SingleRaw local E2E smoke failed because the manifest entry has no raw_path.",
        )

    raw_path = _resolve_repo_or_output_path(raw_path_value, output_root=output_root)
    if not raw_path.exists() or not raw_path.is_file():
        return RawPrepBenchmarkLocalE2EFlow(
            sample_id=sample_id,
            status="failed",
            issues=[f"SingleRaw source file was not found: {raw_path}"],
            summary="SingleRaw local E2E smoke failed because the source file is missing.",
        )

    single_root = run_root / "single_raw"
    single_root.mkdir(parents=True, exist_ok=True)
    session_id = f"local_e2e_single_raw_{_slug(sample_id)}"
    _prepare_clean_session_root(single_root, session_id=session_id)

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            session_id=session_id,
            output_root=str(single_root),
            asset_paths=[str(raw_path)],
            entry_preference="direct_edit",
            quality_preset=quality_preset,
            single_raw_mode_preference=mode_preference,
        )
    )
    single_payload = plan.single_raw_plan if isinstance(plan.single_raw_plan, dict) else {}
    dreamisp_payload = plan.dreamisp_plan if isinstance(plan.dreamisp_plan, dict) else {}
    report_path = _first_existing_path(single_payload.get("report_path"))
    report_payload = _read_json_object(report_path)
    scene_linear_payload = single_payload.get("scene_linear") if isinstance(single_payload.get("scene_linear"), dict) else {}
    foundation_preview_path = _first_existing_path(
        single_payload.get("materialized_preview_path"),
        report_payload.get("materialized_preview_path"),
    )
    scene_linear_path = _first_existing_path(
        single_payload.get("materialized_scene_linear_path"),
        scene_linear_payload.get("materialized_path"),
        report_payload.get("materialized_scene_linear_path"),
    )
    source_preview_path = _first_existing_path(
        single_payload.get("source_preview_path"),
        single_payload.get("preview_source_path"),
        report_payload.get("preview_source_path"),
    )

    render_preview_path = (
        dreamisp_payload.get("render_preview_path")
        or dreamisp_payload.get("recommended_editable_source_path")
        if isinstance(dreamisp_payload, dict)
        else None
    )
    ready_for_edit_ui = _path_exists(render_preview_path)
    issues: list[str] = []
    if not _path_exists(report_path):
        issues.append("SingleRaw report.json was not materialized.")
    if not _path_exists(foundation_preview_path):
        issues.append("SingleRaw preview artifact was not materialized.")
    if not _path_exists(scene_linear_path):
        issues.append("SingleRaw scene_linear artifact was not materialized.")
    if not ready_for_edit_ui:
        issues.append("DreamISP editable preview was not materialized for the SingleRaw flow.")

    status = "passed" if not issues else "partial"
    summary = (
        "SingleRaw local E2E smoke reached the editable DreamISP preview."
        if not issues
        else "SingleRaw local E2E smoke materialized some artifacts, but the editable handoff is incomplete."
    )
    return RawPrepBenchmarkLocalE2EFlow(
        sample_id=sample_id,
        session_id=session_id,
        session_root=plan.session_root,
        entry_mode=plan.entry_mode,
        status=status,
        source_preview_path=_existing_repo_relative(source_preview_path),
        foundation_report_path=_existing_repo_relative(report_path),
        foundation_preview_path=_existing_repo_relative(foundation_preview_path),
        scene_linear_path=_existing_repo_relative(scene_linear_path),
        dreamisp_render_preview_path=_existing_repo_relative(render_preview_path),
        dreamisp_render_state_path=_existing_repo_relative(dreamisp_payload.get("render_state_path") if isinstance(dreamisp_payload, dict) else None),
        runtime_profile=(
            str(single_payload.get("decode", {}).get("runtime_profile"))
            if isinstance(single_payload.get("decode"), dict) and single_payload.get("decode", {}).get("runtime_profile")
            else str(report_payload.get("runtime_profile") or "") or None
        ),
        ready_for_edit_ui=ready_for_edit_ui,
        issues=issues,
        summary=summary,
    )


def _run_tri_raw_flow(
    entry: dict,
    *,
    output_root: str,
    run_root: Path,
    requested_reference_policy: ReferencePolicy,
) -> RawPrepBenchmarkLocalE2EFlow:
    sample_id = str(entry.get("sample_id") or "").strip()
    source_values = entry.get("source_paths")
    if not isinstance(source_values, list) or len(source_values) not in {3, 9}:
        return RawPrepBenchmarkLocalE2EFlow(
            sample_id=sample_id or None,
            status="failed",
            issues=["Official TriRaw manifest entry must declare exactly three or nine source_paths."],
            summary="TriRaw local E2E smoke failed because the manifest entry is invalid.",
        )

    source_paths = [
        _resolve_repo_or_output_path(str(path_value), output_root=output_root)
        for path_value in source_values
    ]
    missing_sources = [path for path in source_paths if not path.exists() or not path.is_file()]
    if missing_sources:
        return RawPrepBenchmarkLocalE2EFlow(
            sample_id=sample_id,
            status="failed",
            issues=[f"TriRaw source file was not found: {missing_sources[0]}"],
            summary="TriRaw local E2E smoke failed because at least one bracket source file is missing.",
        )

    tri_root = run_root / "tri_raw"
    tri_root.mkdir(parents=True, exist_ok=True)
    session_id = f"local_e2e_tri_raw_{_slug(sample_id)}"
    _prepare_clean_session_root(tri_root, session_id=session_id)

    intake_plan = build_studio_intake_plan(
        StudioIntakeRequest(
            session_id=session_id,
            output_root=str(tri_root),
            asset_paths=[str(path) for path in source_paths],
            entry_preference="rawprep",
            quality_preset="balanced",
        )
    )
    rawprep_request_payload = intake_plan.rawprep_request if isinstance(intake_plan.rawprep_request, dict) else None
    if rawprep_request_payload is None:
        return RawPrepBenchmarkLocalE2EFlow(
            sample_id=sample_id,
            session_id=session_id,
            session_root=intake_plan.session_root,
            entry_mode=intake_plan.entry_mode,
            status="failed",
            issues=["Studio intake did not produce a rawprep_request for the TriRaw bracket."],
            summary="TriRaw local E2E smoke failed before rawprep execution.",
        )

    rawprep_request_payload["groups"][0]["reference_policy"] = requested_reference_policy
    job_plan = build_job_plan(RawPrepJobRequest(**rawprep_request_payload))
    tool_status = detect_rawprep_tools()
    initialize_rawprep_job(job_plan, tool_status=tool_status)
    record = execute_rawprep_job(job_plan, tool_status=tool_status)

    group_report = record.group_reports[0] if record.group_reports else {}
    if not isinstance(group_report, dict):
        group_report = {}
    report_path = _first_existing_path(
        group_report.get("report_path"),
        _job_artifact_path(record, "report"),
    )
    diagnostics_manifest_path = _first_existing_path(
        group_report.get("diagnostics_manifest_path"),
        _job_artifact_path(record, "diagnostics_manifest"),
    )
    report_payload = _read_json_object(report_path)
    diagnostics_payload = _read_json_object(diagnostics_manifest_path)
    dreamisp_payload = group_report.get("dreamisp_handoff") if isinstance(group_report.get("dreamisp_handoff"), dict) else {}
    foundation_preview_path = _first_existing_path(
        group_report.get("materialized_preview_path"),
        report_payload.get("materialized_preview_path"),
        _required_artifact_path(diagnostics_payload, "preview"),
    )
    scene_linear_path = _first_existing_path(
        group_report.get("materialized_scene_linear_path"),
        report_payload.get("materialized_scene_linear_path"),
        dreamisp_payload.get("scene_linear_path") if isinstance(dreamisp_payload, dict) else None,
        _required_artifact_path(diagnostics_payload, "scene_linear"),
    )
    render_preview_path = (
        dreamisp_payload.get("render_preview_path")
        or dreamisp_payload.get("recommended_editable_source_path")
        if isinstance(dreamisp_payload, dict)
        else None
    )
    ready_for_edit_ui = _path_exists(render_preview_path)
    issues: list[str] = []
    if record.status != "done":
        issues.append(f"TriRaw rawprep job did not finish successfully: {record.status}")
    if not _path_exists(foundation_preview_path):
        issues.append("TriRaw preview artifact was not materialized.")
    if not _path_exists(scene_linear_path):
        issues.append("TriRaw scene_linear artifact was not materialized.")
    if not _path_exists(report_path):
        issues.append("TriRaw report.json was not materialized.")
    if not ready_for_edit_ui:
        issues.append("DreamISP editable preview was not materialized for the TriRaw flow.")

    status = "passed" if not issues else "partial"
    summary = (
        "TriRaw local E2E smoke reached the editable DreamISP preview."
        if not issues
        else "TriRaw local E2E smoke materialized some artifacts, but the editable handoff is incomplete."
    )
    return RawPrepBenchmarkLocalE2EFlow(
        sample_id=sample_id,
        session_id=record.session_id,
        session_root=record.session_root,
        entry_mode=intake_plan.entry_mode,
        status=status,
        foundation_report_path=_existing_repo_relative(report_path),
        foundation_preview_path=_existing_repo_relative(foundation_preview_path),
        scene_linear_path=_existing_repo_relative(scene_linear_path),
        dreamisp_render_preview_path=_existing_repo_relative(render_preview_path),
        dreamisp_render_state_path=_existing_repo_relative(dreamisp_payload.get("render_state_path") if isinstance(dreamisp_payload, dict) else None),
        rawprep_job_path=_existing_repo_relative(record.state_path),
        runtime_backend=str(group_report.get("runtime_backend") or report_payload.get("runtime_backend") or "") or None,
        ready_for_edit_ui=ready_for_edit_ui,
        issues=issues,
        summary=summary,
    )


def build_rawprep_benchmark_local_e2e_smoke(
    request: RawPrepBenchmarkLocalE2ESmokeRequest,
) -> RawPrepBenchmarkLocalE2ESmoke:
    run_root = _resolve_run_root(request.run_root, output_root=request.output_root)
    single_entry = _load_manifest_entry(_single_raw_manifest_path().resolve(), sample_id=request.single_raw_sample_id)
    tri_entry = _load_manifest_entry(_tri_raw_manifest_path().resolve(), sample_id=request.tri_raw_sample_id)

    single_raw = _run_single_raw_flow(
        single_entry,
        output_root=request.output_root,
        run_root=run_root,
        quality_preset=request.single_raw_quality_preset,
        mode_preference=request.single_raw_mode_preference,
    )
    tri_raw = _run_tri_raw_flow(
        tri_entry,
        output_root=request.output_root,
        run_root=run_root,
        requested_reference_policy=request.tri_raw_reference_policy,
    )

    recommended_actions: list[str] = []
    if not single_raw.ready_for_edit_ui:
        recommended_actions.append("Fix the SingleRaw direct-edit flow so it consistently materializes preview, scene_linear, and DreamISP editable preview artifacts.")
    if not tri_raw.ready_for_edit_ui:
        recommended_actions.append("Fix the TriRaw rawprep flow so it finishes preview runtime and materializes DreamISP editable preview artifacts.")

    if single_raw.ready_for_edit_ui and tri_raw.ready_for_edit_ui:
        status = "passed"
        summary = "Local end-to-end smoke verified SingleRaw, TriRaw, and DreamISP handoff artifacts on curated benchmark samples."
    elif single_raw.ready_for_edit_ui or tri_raw.ready_for_edit_ui:
        status = "partial"
        summary = "Local end-to-end smoke verified only part of the SingleRaw/TriRaw handoff chain."
    else:
        status = "failed"
        summary = "Local end-to-end smoke could not verify the DreamISP handoff chain on the selected samples."

    return RawPrepBenchmarkLocalE2ESmoke(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        smoke_path=str(_smoke_path(request.output_dir, output_root=request.output_root)),
        run_root=str(run_root),
        status=status,
        ok=status == "passed",
        single_raw=single_raw,
        tri_raw=tri_raw,
        recommended_actions=recommended_actions,
        summary=summary,
    )


def write_rawprep_benchmark_local_e2e_smoke(
    request: RawPrepBenchmarkLocalE2ESmokeRequest,
) -> RawPrepBenchmarkLocalE2ESmoke:
    smoke = build_rawprep_benchmark_local_e2e_smoke(request)
    path = _smoke_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return smoke


def load_rawprep_benchmark_local_e2e_smoke(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkLocalE2ESmoke:
    path = _smoke_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep local E2E smoke artifact was not found: {path}")
    return RawPrepBenchmarkLocalE2ESmoke(**json.loads(path.read_text(encoding="utf-8")))
