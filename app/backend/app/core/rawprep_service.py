from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.raw_engine_v2.isp.planner import (
    DreamISPHandoffPlan,
    build_dreamisp_handoff_plan,
    materialize_dreamisp_handoff_plan,
)
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render
from app.raw_engine_v2.tri_raw.planner import (
    TriRawFoundationPlan,
    build_tri_raw_foundation_plan,
    materialize_tri_raw_foundation_plan,
)
from app.raw_engine_v2.tri_raw.runtime import (
    TriRawPreviewRuntimeResult,
    materialize_tri_raw_preview_runtime,
)

from .rawprep_catalog import legacy_removed_note, preview_runtime_note
from .rawprep_contract import RawPrepArtifact, RawPrepJobPlan
from .rawprep_runner import RawPrepCommandPreview, RawPrepToolStatus, detect_rawprep_tools as detect_rawprep_tools_runner
from .rawprep_runner import artifact_map, build_rawprep_command_previews, missing_required_tools, required_tools_for_plan
from .studio_paths import resolve_output_root


class RawPrepArtifactStatus(BaseModel):
    bracket_id: str
    kind: str
    path: str
    exists: bool = False
    required: bool = False
    notes: str | None = None


class RawPrepCommandResult(BaseModel):
    step: str
    success: bool
    detail: str | None = None


class RawPrepJobRecord(BaseModel):
    job_id: str
    session_id: str
    output_root: str
    session_root: str
    plan_path: str
    state_path: str
    status: str
    current_step: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    missing_tools: list[str] = Field(default_factory=list)
    artifacts: list[RawPrepArtifactStatus] = Field(default_factory=list)
    tool_status: dict[str, dict[str, Any]] = Field(default_factory=dict)
    command_previews: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    group_reports: list[dict[str, Any]] = Field(default_factory=list)
    cancel_requested_at: str | None = None
    cancelled_at: str | None = None


class RawPrepCancellationRequest(BaseModel):
    job_id: str
    output_root: str = "outputs"


def dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rawprep_runtime_message() -> str:
    return preview_runtime_note()


def _index_path(output_root: str) -> Path:
    return resolve_output_root(output_root) / "rawprep_job_index.json"


def session_root_path(plan: RawPrepJobPlan) -> Path:
    return Path(plan.layout.session_root)


def plan_file_path(plan: RawPrepJobPlan) -> Path:
    return session_root_path(plan) / "rawprep_plan.json"


def state_file_path(plan: RawPrepJobPlan) -> Path:
    return session_root_path(plan) / "rawprep_job.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_artifact_statuses(record: RawPrepJobRecord) -> RawPrepJobRecord:
    refreshed = []
    for artifact in record.artifacts:
        refreshed.append(
            RawPrepArtifactStatus(
                **{
                    **dump_model(artifact),
                    "exists": Path(artifact.path).exists(),
                }
            )
        )
    record.artifacts = refreshed
    record.updated_at = utc_now_iso()
    return record


def save_job_record(record: RawPrepJobRecord) -> RawPrepJobRecord:
    record = refresh_artifact_statuses(record)
    state_path = Path(record.state_path)
    _write_json(state_path, dump_model(record))

    index_path = _index_path(record.output_root)
    if index_path.exists():
        try:
            index_payload = _read_json(index_path)
        except (OSError, json.JSONDecodeError):
            index_payload = {}
    else:
        index_payload = {}
    if not isinstance(index_payload, dict):
        index_payload = {}
    index_payload[record.job_id] = {
        "job_id": record.job_id,
        "session_id": record.session_id,
        "status": record.status,
        "updated_at": record.updated_at,
        "plan_path": record.plan_path,
        "state_path": record.state_path,
    }
    _write_json(index_path, index_payload)
    return record


def _artifact_statuses(plan: RawPrepJobPlan) -> list[RawPrepArtifactStatus]:
    return [
        RawPrepArtifactStatus(
            bracket_id=artifact.bracket_id,
            kind=artifact.kind,
            path=artifact.path,
            exists=Path(artifact.path).exists(),
            required=artifact.required,
            notes=artifact.notes,
        )
        for artifact in plan.expected_artifacts
    ]


def _tri_raw_artifact_path(plan: TriRawFoundationPlan, kind: str) -> str | None:
    for artifact in plan.expected_artifacts:
        if artifact.kind == kind:
            return artifact.path
    return None


def _dreamisp_handoff_summary(plan: DreamISPHandoffPlan) -> dict[str, Any]:
    return {
        "source_stage": plan.source_stage,
        "source_item_key": plan.source_item_key,
        "materialization_status": plan.materialization_status,
        "plan_path": plan.plan_path,
        "render_state_path": plan.render_state_path,
        "report_path": plan.report_path,
        "scene_linear_path": plan.scene_linear_path,
        "scene_linear_exists": plan.scene_linear_exists,
        "preview_path": plan.preview_path,
        "preview_exists": plan.preview_exists,
        "render_preview_path": plan.render_preview_path,
        "render_preview_exists": plan.render_preview_exists,
        "recommended_editable_source_path": plan.recommended_editable_source_path,
        "render_source_kind": plan.render_source_kind,
        "render_backend": plan.render_backend,
        "handoff_ready": plan.scene_linear_exists or plan.preview_exists,
    }


def _materialize_tri_raw_dreamisp_handoff(
    foundation_plan: TriRawFoundationPlan,
    *,
    session_root: str,
    scene_linear_path: str | None = None,
    preview_path: str | None = None,
) -> DreamISPHandoffPlan | None:
    scene_linear_path = scene_linear_path or _tri_raw_artifact_path(foundation_plan, "scene_linear")
    if not scene_linear_path:
        return None

    preview_path = preview_path or _tri_raw_artifact_path(foundation_plan, "preview")
    dreamisp_plan = build_dreamisp_handoff_plan(
        session_root=session_root,
        source_stage="tri_raw",
        source_item_key=foundation_plan.bracket_id,
        source_engine_key=foundation_plan.engine_key,
        source_engine_version=foundation_plan.engine_version,
        scene_linear_path=scene_linear_path,
        preview_path=preview_path,
        source_report_path=foundation_plan.report_path,
        source_diagnostics_manifest_path=foundation_plan.diagnostics_manifest_path,
    )
    dreamisp_plan = materialize_dreamisp_handoff_plan(dreamisp_plan)
    return materialize_dreamisp_lite_render(dreamisp_plan)


def _materialize_tri_raw_foundations(plan: RawPrepJobPlan) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for group in plan.groups:
        foundation_plan = build_tri_raw_foundation_plan(
            group.raw_files,
            bracket_id=group.bracket_id,
            session_root=plan.layout.session_root,
        )
        materialized_plan = materialize_tri_raw_foundation_plan(foundation_plan)
        dreamisp_plan = _materialize_tri_raw_dreamisp_handoff(
            materialized_plan,
            session_root=plan.layout.session_root,
        )
        report_path = Path(materialized_plan.report_path)
        if not report_path.exists():
            continue
        try:
            payload = _read_json(report_path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            if dreamisp_plan is not None:
                payload["dreamisp_handoff"] = _dreamisp_handoff_summary(dreamisp_plan)
                notes = payload.get("notes")
                payload["notes"] = [
                    *(notes if isinstance(notes, list) else []),
                    "TriRaw foundation writes the DreamISP handoff contract under 02_manual so SingleRaw and TriRaw share the same editable render-state shape.",
                    "TriRaw foundation도 02_manual 아래에 DreamISP handoff 계약을 기록해 SingleRaw와 TriRaw가 같은 편집 렌더 상태 규격을 공유합니다.",
                ]
                _write_json(report_path, payload)
            reports.append(payload)
    return reports


def _load_tri_raw_foundation_plan(plan: RawPrepJobPlan, bracket_id: str) -> TriRawFoundationPlan:
    path = Path(plan.layout.rawprep_dir) / bracket_id / "tri_raw_plan.json"
    if not path.exists():
        raise FileNotFoundError(f"TriRaw foundation plan was not found: {path}")
    return TriRawFoundationPlan(**_read_json(path))


def _update_group_artifacts(
    record: RawPrepJobRecord,
    *,
    bracket_id: str,
    runtime_result: TriRawPreviewRuntimeResult,
) -> RawPrepJobRecord:
    updated: list[RawPrepArtifactStatus] = []
    for artifact in record.artifacts:
        if artifact.bracket_id != bracket_id:
            updated.append(artifact)
            continue

        payload = dump_model(artifact)
        if artifact.kind == "preview":
            payload["path"] = runtime_result.preview_path
            payload["notes"] = "현재 미리보기 병합 런타임이 선택한 실행 가능한 TriRaw 미리보기입니다."
        elif artifact.kind == "scene_linear":
            payload["path"] = runtime_result.scene_linear_path
            payload["notes"] = "TriRaw 미리보기 런타임이 기록한 preview 기반 선형화 TIFF 대체 산출물입니다."
        elif artifact.kind == "noise_map":
            payload["path"] = runtime_result.noise_map_path
        elif artifact.kind == "motion_map":
            payload["path"] = runtime_result.motion_map_path
        elif artifact.kind == "diagnostics_manifest":
            payload["path"] = runtime_result.diagnostics_manifest_path
        payload["exists"] = Path(payload["path"]).is_file()
        updated.append(RawPrepArtifactStatus(**payload))

    record.artifacts = updated
    return record


def initialize_rawprep_job(
    plan: RawPrepJobPlan,
    *,
    tool_status: dict[str, RawPrepToolStatus] | None = None,
    command_previews: list[RawPrepCommandPreview] | None = None,
) -> RawPrepJobRecord:
    session_root_path(plan).mkdir(parents=True, exist_ok=True)
    Path(plan.layout.rawprep_dir).mkdir(parents=True, exist_ok=True)
    Path(plan.layout.manual_dir).mkdir(parents=True, exist_ok=True)
    Path(plan.layout.ai_dir).mkdir(parents=True, exist_ok=True)
    Path(plan.layout.export_dir).mkdir(parents=True, exist_ok=True)

    tool_status = dict(tool_status or detect_rawprep_tools())
    command_previews = list(command_previews or build_rawprep_command_previews(plan, tool_status=tool_status))
    missing = missing_required_tools(tool_status, required_tools_for_plan(plan))
    _write_json(plan_file_path(plan), dump_model(plan))
    group_reports = _materialize_tri_raw_foundations(plan)

    now = utc_now_iso()
    record = RawPrepJobRecord(
        job_id=plan.job_id,
        session_id=plan.session_id,
        output_root=plan.output_root,
        session_root=plan.layout.session_root,
        plan_path=str(plan_file_path(plan)),
        state_path=str(state_file_path(plan)),
        status="ready" if not missing else "blocked",
        current_step="foundation_ready" if not missing else "waiting_for_runtime",
        created_at=now,
        updated_at=now,
        error=None if not missing else rawprep_runtime_message(),
        missing_tools=missing,
        artifacts=_artifact_statuses(plan),
        tool_status={name: dump_model(status) for name, status in tool_status.items()},
        command_previews=[dump_model(preview) for preview in command_previews],
        notes=[
            *plan.notes,
            "TriRaw foundation plan/report/diagnostics were recorded for each bracket group under 01_rawprep.",
            "DreamISP handoff/render-state files now follow the same 02_manual contract from each TriRaw bracket group.",
            "TriRaw foundation plan, report, diagnostics를 각 브라켓 그룹의 01_rawprep 아래에 기록했습니다.",
            "DreamISP handoff와 렌더 상태 파일도 이제 TriRaw 브라켓 그룹에서 같은 02_manual 계약을 따릅니다.",
            preview_runtime_note(),
        ],
        group_reports=group_reports,
    )
    return save_job_record(record)


def _load_index(output_root: str) -> dict[str, Any]:
    path = _index_path(output_root)
    if not path.exists():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def load_job_record(job_id: str, *, output_root: str = "outputs") -> RawPrepJobRecord:
    index_payload = _load_index(output_root)
    entry = index_payload.get(job_id)
    state_path = None
    if isinstance(entry, dict):
        candidate = entry.get("state_path")
        if isinstance(candidate, str):
            state_path = Path(candidate)
    if state_path is None:
        root = resolve_output_root(output_root)
        for candidate in root.glob("*/rawprep_job.json"):
            try:
                payload = _read_json(candidate)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("job_id") == job_id:
                state_path = candidate
                break
    if state_path is None or not state_path.exists():
        raise FileNotFoundError(f"Rawprep job was not found: {job_id}")
    record = RawPrepJobRecord(**_read_json(state_path))
    return refresh_artifact_statuses(record)


def load_job_plan(job_id: str, *, output_root: str = "outputs") -> RawPrepJobPlan:
    record = load_job_record(job_id, output_root=output_root)
    plan_path = Path(record.plan_path)
    if not plan_path.exists():
        raise FileNotFoundError(f"Rawprep plan was not found: {plan_path}")
    return RawPrepJobPlan(**_read_json(plan_path))


def request_rawprep_cancel(job_id: str, *, output_root: str = "outputs") -> RawPrepJobRecord:
    record = load_job_record(job_id, output_root=output_root)
    if record.status in {"done", "failed", "blocked", "cancelled"}:
        return record
    record.cancel_requested_at = utc_now_iso()
    record.cancelled_at = record.cancel_requested_at
    record.finished_at = record.cancel_requested_at
    record.status = "cancelled"
    record.current_step = "cancelled"
    record.error = None
    return save_job_record(record)


def retry_rawprep_job(job_id: str, *, output_root: str = "outputs") -> tuple[RawPrepJobPlan, RawPrepJobRecord, dict[str, RawPrepToolStatus]]:
    plan = load_job_plan(job_id, output_root=output_root)
    tool_status = detect_rawprep_tools()
    record = initialize_rawprep_job(plan, tool_status=tool_status)
    return plan, record, tool_status


def register_command_result(record: RawPrepJobRecord, result: RawPrepCommandResult) -> RawPrepJobRecord:
    record.notes.append(result.detail or f"{result.step}: {'ok' if result.success else 'failed'}")
    return save_job_record(record)


def execute_rawprep_job(plan: RawPrepJobPlan, tool_status: dict[str, RawPrepToolStatus] | None = None) -> RawPrepJobRecord:
    record = load_job_record(plan.job_id, output_root=plan.output_root)
    record.status = "running"
    record.current_step = "tri_raw_preview_runtime"
    record.error = None
    record.started_at = record.started_at or utc_now_iso()
    if tool_status:
        record.tool_status = {name: dump_model(status) for name, status in tool_status.items()}
    save_job_record(record)

    group_reports: list[dict[str, Any]] = []
    try:
        for group in plan.groups:
            foundation_plan = _load_tri_raw_foundation_plan(plan, group.bracket_id)
            runtime_result = materialize_tri_raw_preview_runtime(
                foundation_plan,
                requested_reference_policy=group.reference_policy,
                restoration_goal=plan.restoration_goal,
            )
            if runtime_result is None:
                record.status = "blocked"
                record.current_step = "waiting_for_preview_runtime"
                record.error = (
                    "TriRaw 미리보기 런타임이 이 브라켓에 필요한 companion preview 또는 sensor decode proxy를 찾지 못했습니다."
                )
                record.finished_at = utc_now_iso()
                record.notes.append(record.error)
                return save_job_record(record)

            dreamisp_plan = _materialize_tri_raw_dreamisp_handoff(
                foundation_plan,
                session_root=plan.layout.session_root,
                scene_linear_path=runtime_result.scene_linear_path,
                preview_path=runtime_result.preview_path,
            )

            report_path = Path(foundation_plan.report_path)
            try:
                payload = _read_json(report_path) if report_path.exists() else {}
            except (OSError, json.JSONDecodeError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}

            payload.update(
                {
                    "status": "preview_fused",
                    "runtime_backend": runtime_result.backend,
                    "baseline_backend": runtime_result.baseline_backend,
                    "frontier_contract": runtime_result.frontier_contract,
                    "merge_backend": runtime_result.baseline_backend,
                    "restoration_goal": runtime_result.restoration_goal,
                    "restoration_goal_policy": runtime_result.restoration_goal_policy,
                    "requested_reference_policy": group.reference_policy,
                    "selected_single_raw": runtime_result.selected_reference_raw_path,
                    "selected_single_index": runtime_result.selected_reference_index,
                    "recommended_artifact": runtime_result.recommended_artifact_path,
                    "merged_hdr_path": runtime_result.merged_hdr_path,
                    "denoised_result_path": runtime_result.denoised_result_path,
                    "aggressive_restore_candidate_path": runtime_result.aggressive_restore_candidate_path,
                    "fallback_reason": runtime_result.fallback_reason or "none",
                    "reference_selection": runtime_result.reference_selection,
                    "candidate_scores": runtime_result.candidate_scores,
                    "fallback_strategy": runtime_result.fallback_strategy,
                    "frontier_eval": runtime_result.frontier_eval,
                    "frontier_eval_path": runtime_result.frontier_eval_path,
                    "learned_adapter": runtime_result.learned_adapter,
                    "alignment_summary": runtime_result.alignment_summary,
                    "alignment_guard_summary": runtime_result.alignment_guard_summary,
                    "alignment_refinement_summary": runtime_result.alignment_refinement_summary,
                    "confidence_summary": runtime_result.confidence_summary,
                    "joint_denoise_summary": runtime_result.joint_denoise_summary,
                    "deghost_summary": runtime_result.deghost_summary,
                    "hdr_summary": runtime_result.hdr_summary,
                    "capture_summary": runtime_result.capture_summary,
                    "bracket_coverage": runtime_result.bracket_coverage,
                    "motion_overlay_path": runtime_result.motion_map_path,
                    "motion_overlay_summary": runtime_result.motion_overlay_summary,
                    "motion_overlay_coverage": runtime_result.motion_overlay_coverage,
                    "confidence_map_path": runtime_result.confidence_map_path,
                    "confidence_preview_path": runtime_result.confidence_preview_path,
                    "ghost_risk_map_path": runtime_result.ghost_risk_map_path,
                    "highlight_map_path": runtime_result.highlight_map_path,
                    "shadow_map_path": runtime_result.shadow_map_path,
                    "deghost_mask_path": runtime_result.deghost_mask_path,
                    "hdr_gain_map_path": runtime_result.hdr_gain_map_path,
                    "noise_suppression_map_path": runtime_result.noise_suppression_map_path,
                    "alignment_offset_map_path": runtime_result.alignment_offset_map_path,
                    "alignment_residual_map_path": runtime_result.alignment_residual_map_path,
                    "alignment_vector_field_path": runtime_result.alignment_vector_field_path,
                    "alignment_refinement_map_path": runtime_result.alignment_refinement_map_path,
                    "alignment_vector_summary": runtime_result.alignment_vector_summary,
                    "materialized_preview_path": runtime_result.preview_path,
                    "materialized_scene_linear_path": runtime_result.scene_linear_path,
                    "materialized_scene_linear_format": "tiff",
                }
            )
            payload["notes"] = [
                *(payload.get("notes") if isinstance(payload.get("notes"), list) else []),
                *runtime_result.notes,
            ]
            if dreamisp_plan is not None:
                payload["dreamisp_handoff"] = _dreamisp_handoff_summary(dreamisp_plan)
            _write_json(report_path, payload)
            group_reports.append(payload)
            record = _update_group_artifacts(record, bracket_id=group.bracket_id, runtime_result=runtime_result)

        record.group_reports = group_reports
        record.status = "done"
        record.current_step = "completed"
        record.error = None
        record.finished_at = utc_now_iso()
        record.notes.append("TriRaw 미리보기 런타임이 정상 완료됐고 브라켓 미리보기·진단 산출물을 기록했습니다.")
        return save_job_record(record)
    except Exception as exc:
        record.status = "failed"
        record.current_step = "failed"
        record.error = str(exc)
        record.finished_at = utc_now_iso()
        record.notes.append(f"TriRaw 미리보기 런타임이 실패했습니다: {exc}")
        return save_job_record(record)


def detect_rawprep_tools(tool_names: list[str] | None = None) -> dict[str, RawPrepToolStatus]:
    return detect_rawprep_tools_runner(tool_names)
