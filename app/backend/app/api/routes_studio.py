from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..core.studio_intake import (
    StudioIntakeRequest,
    build_studio_intake_plan,
    dump_model,
    list_recent_studio_sessions,
    load_studio_intake_plan,
)
from ..core.studio_catalog import (
    StudioCatalogBatchUpdate,
    StudioCatalogUpdate,
    batch_update_session_catalogs,
    load_session_catalog,
    update_session_catalog,
)
from ..core.studio_job_service import (
    load_job_record as load_studio_job_record,
    retry_studio_job,
    save_job_record as save_studio_job_record,
)
from ..core.rawprep_service import retry_rawprep_job, save_job_record as save_rawprep_job_record
from ..core.raw_restoration_policy import DEFAULT_RAW_RESTORATION_GOAL
from ..core.runpod_provider import (
    StudioProviderCheckpointSavedVersion,
    StudioProviderCheckpointSessionSnapshot,
    pause_provider_lifecycle,
    provider_runtime_summary,
    resume_provider_lifecycle,
)
from ..core.studio_ops import (
    list_dead_letters,
    list_operations_roots,
    summarize_studio_operations,
    update_dead_letter_investigation,
)
from ..core.studio_queue import (
    clear_worker_stop_request,
    enqueue_job,
    launch_external_worker_process,
    launch_external_worker_processes,
    request_worker_stop_many,
    request_worker_stop,
    start_queue_worker,
    worker_control_status_many,
    worker_control_status,
)
from ..core.studio_telemetry import list_recent_events, record_studio_event
from ..core.studio_files import (
    DeliveryPresetKey,
    build_delivery_preset_package,
    export_batch_delivery_packages,
    export_output_file,
    export_session_package,
    resolve_output_target,
)
from ..core.studio_preview import build_preview_image
from ..core.studio_compare_advisor import build_compare_advice
from ..core.studio_compare_memory import record_compare_decision
from ..core.studio_quality_automation import (
    JudgeEvidencePacket,
    QwenJudgeSignal,
    build_quality_assessment,
    build_quality_automation_policy,
    build_quality_tuning_proposal,
)
from ..core.studio_qwen_judge import QwenJudgeError, build_qwen_judge_signal
from ..core.rawprep_contract import build_directory_layout, default_session_id
from ..core.studio_dreamisp_service import apply_dreamisp_workspace_profile
from ..core.studio_recovery import (
    build_session_recovery_packet,
    load_session_recovery_packet,
)
from ..core.studio_selection_service import (
    StudioSelectionControls,
    apply_session_selection_state,
    load_session_selection_state,
)
from ..core.studio_edit_linkage import (
    build_or_update_session_edit_linkage,
    load_session_edit_linkage,
)
from ..core.runpod_storage_contract import build_runpod_storage_contract


router = APIRouter(prefix="/api/studio", tags=["studio"])


class StudioExportRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    path: str
    label: str | None = None


class StudioExportPackageItem(BaseModel):
    path: str
    label: str | None = None


class StudioExportPackageRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    label: str | None = None
    items: list[StudioExportPackageItem]
    metadata: Dict[str, Any] | None = None


class StudioBatchExportRequest(BaseModel):
    output_root: str = "outputs"
    session_ids: list[str]
    preset: Literal["review_pack", "client_delivery", "master_archive", "proofing_sheet", "print_master", "client_review_portal"] = "client_delivery"


class StudioPresetExportRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    preset: DeliveryPresetKey = "client_delivery"
    label: str | None = None
    metadata: Dict[str, Any] | None = None


class StudioRecoveryPacketRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    preset: DeliveryPresetKey = "master_archive"
    create_package: bool = True


class StudioCompareAdviceRequest(BaseModel):
    output_root: str = "outputs"
    primary_path: str
    candidate_path: str
    tool: str = "compare"
    seed_root: str = "seed_bundle"
    motion_overlay_path: str | None = None
    motion_overlay_summary: str | None = None
    motion_overlay_coverage: float | None = None


class StudioCompareDecisionRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    tool: str = "compare"
    primary_path: str
    candidate_path: str
    winner_path: str
    action: Literal["keep_select", "accept_candidate", "manual"] = "manual"
    note: str | None = None


class StudioQualityAssessmentRequest(BaseModel):
    output_root: str = "outputs"
    session_id: str | None = None
    tool: str = "compare"
    result_path: str
    reference_path: str | None = None
    qwen_judge_signal: QwenJudgeSignal | None = None
    judge_evidence_packet: JudgeEvidencePacket | None = None
    run_qwen_judge: bool = False
    task_intent: str | None = None
    seed_root: str = "seed_bundle"
    operation_context: Dict[str, Any] = Field(default_factory=dict)
    mask_evidence: Dict[str, Any] = Field(default_factory=dict)
    raw_evidence: Dict[str, Any] = Field(default_factory=dict)
    workflow_evidence: Dict[str, Any] = Field(default_factory=dict)
    user_preference_evidence: Dict[str, Any] = Field(default_factory=dict)
    write_artifact: bool = True


class StudioQualityTuningProposalRequest(BaseModel):
    output_root: str = "outputs"
    session_id: str | None = None
    assessments: list[Dict[str, Any]] = Field(default_factory=list)
    assessment_paths: list[str] = Field(default_factory=list)
    write_artifact: bool = True


class StudioDreamISPWorkspaceSlidersRequest(BaseModel):
    strength: int
    realism: int
    preserve_texture: int


class StudioDreamISPManualControlsRequest(BaseModel):
    temperature_delta: float | None = None
    tint_delta: float | None = None
    exposure_ev: float | None = None
    contrast: float | None = None
    clarity: float | None = None


class StudioDreamISPApplyRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    sliders: StudioDreamISPWorkspaceSlidersRequest
    controls: StudioDreamISPManualControlsRequest | None = None


class StudioSelectionControlsRequest(BaseModel):
    threshold: int = 128
    expand_pixels: int = 0
    feather_radius: int = 4


class StudioSelectionApplyRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    source_mask_path: str
    source_asset_path: str | None = None
    controls: StudioSelectionControlsRequest | None = None


class StudioEditLinkageSyncRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    current_source_path: str | None = None
    active_tool: str | None = None
    studio_job_id: str | None = None
    source_history: list[str] = []
    source_history_index: int = -1


class StudioWorkerStartRequest(BaseModel):
    output_root: str = "outputs"
    output_roots: list[str] = []
    mode: Literal["external", "embedded"] = "external"
    poll_interval_seconds: float = 2.0


class StudioWorkerStopRequest(BaseModel):
    output_root: str = "outputs"
    output_roots: list[str] = []
    reason: str | None = None


class StudioProviderSessionSavedVersionRequest(BaseModel):
    id: str
    label: str
    path: str
    created_at: str


class StudioProviderSessionSnapshotRequest(BaseModel):
    session_id: str
    output_root: str = "outputs"
    rawprep_job_id: str | None = None
    studio_job_id: str | None = None
    direct_path: str | None = None
    compare_primary: str | None = None
    compare_candidate: str | None = None
    source_history: list[str] = []
    source_history_index: int = -1
    saved_versions: list[StudioProviderSessionSavedVersionRequest] = []


class StudioProviderPauseRequest(BaseModel):
    output_root: str = "outputs"
    output_roots: list[str] = []
    reason: str | None = None
    worker_mode: Literal["external", "embedded"] | None = None
    poll_interval_seconds: float | None = None
    drain_timeout_seconds: float = 12.0
    stop_provider: bool = True
    session_snapshot: StudioProviderSessionSnapshotRequest | None = None
    recovery_session_id: str | None = None
    recovery_preset: DeliveryPresetKey = "master_archive"
    require_recovery_ready: bool = False
    create_recovery_package: bool = True


class StudioProviderResumeRequest(BaseModel):
    output_root: str = "outputs"
    output_roots: list[str] = []
    worker_mode: Literal["external", "embedded"] | None = None
    poll_interval_seconds: float | None = None


class StudioDeadLetterRetryItem(BaseModel):
    task_type: Literal["studio", "rawprep"]
    job_id: str
    output_root: str = "outputs"


class StudioDeadLetterRetryRequest(BaseModel):
    output_root: str = "outputs"
    items: list[StudioDeadLetterRetryItem] = []


class StudioDeadLetterInvestigationRequest(BaseModel):
    output_root: str = "outputs"
    history_path: str
    assigned_to: str | None = None
    acknowledged: bool | None = None
    note: str | None = None
    investigation_status: Literal["open", "acknowledged", "assigned", "resolved", "muted"] | None = None


def _resolved_request_output_roots(output_root: str, output_roots: list[str]) -> list[str]:
    combined = [output_root, *output_roots]
    seen: set[str] = set()
    roots: list[str] = []
    for root in combined:
        if root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots


def _provider_session_snapshot(
    request: StudioProviderSessionSnapshotRequest | None,
) -> StudioProviderCheckpointSessionSnapshot | None:
    if request is None:
        return None
    return StudioProviderCheckpointSessionSnapshot(
        session_id=request.session_id,
        output_root=request.output_root,
        rawprep_job_id=request.rawprep_job_id,
        studio_job_id=request.studio_job_id,
        direct_path=request.direct_path,
        compare_primary=request.compare_primary,
        compare_candidate=request.compare_candidate,
        source_history=list(request.source_history),
        source_history_index=request.source_history_index,
        saved_versions=[
            StudioProviderCheckpointSavedVersion(
                id=item.id,
                label=item.label,
                path=item.path,
                created_at=item.created_at,
            )
            for item in request.saved_versions
        ],
    )


def _retry_dead_letter_item(item: StudioDeadLetterRetryItem) -> dict[str, Any]:
    if item.task_type == "studio":
        record = retry_studio_job(item.job_id, output_root=item.output_root)
        if not record.execution_ready:
            record.status = "blocked"
            record.current_step = "backend_unavailable"
            record.error = record.availability_error or "ComfyUI is not ready for this tool."
            save_studio_job_record(record)
            return {"job_id": item.job_id, "task_type": item.task_type, "output_root": item.output_root, "status": record.status, "detail": record.error}
        if not record.source_path:
            record.status = "blocked"
            record.current_step = "waiting_for_source"
            record.error = "Studio AI execution requires a source raster file."
            save_studio_job_record(record)
            return {"job_id": item.job_id, "task_type": item.task_type, "output_root": item.output_root, "status": record.status, "detail": record.error}
        record.status = "queued"
        record.current_step = "queued"
        record.notes.append("Studio job was re-queued from the dead-letter queue.")
        save_studio_job_record(record)
        enqueue_job(
            task_type="studio",
            job_id=record.job_id,
            session_id=record.session_id,
            output_root=record.output_root,
        )
        clear_worker_stop_request(record.output_root)
        start_queue_worker(record.output_root)
        return {"job_id": item.job_id, "task_type": item.task_type, "output_root": item.output_root, "status": "queued", "detail": None}

    plan, record, _tool_status = retry_rawprep_job(item.job_id, output_root=item.output_root)
    if record.missing_tools:
        record.notes.append("Dead-letter retry was requested, but the required rawprep tools are still missing.")
        save_rawprep_job_record(record)
        return {
            "job_id": item.job_id,
            "task_type": item.task_type,
            "output_root": item.output_root,
            "status": record.status,
            "detail": f"Missing tools: {', '.join(record.missing_tools)}",
        }

    record.status = "queued"
    record.current_step = "queued"
    record.notes.append("rawprep job was re-queued from the dead-letter queue.")
    save_rawprep_job_record(record)
    enqueue_job(
        task_type="rawprep",
        job_id=plan.job_id,
        session_id=plan.session_id,
        output_root=plan.output_root,
    )
    clear_worker_stop_request(plan.output_root)
    start_queue_worker(plan.output_root)
    return {"job_id": item.job_id, "task_type": item.task_type, "output_root": item.output_root, "status": "queued", "detail": None}


@router.post("/intake")
def create_studio_intake(request: StudioIntakeRequest) -> Dict[str, Any]:
    try:
        plan = build_studio_intake_plan(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(plan)


@router.get("/intake/session")
def get_studio_intake(session_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        plan = load_studio_intake_plan(session_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(plan)


@router.post("/dreamisp/apply")
def apply_studio_dreamisp_preview(request: StudioDreamISPApplyRequest) -> Dict[str, Any]:
    try:
        plan = apply_dreamisp_workspace_profile(
            request.session_id,
            output_root=request.output_root,
            strength=request.sliders.strength,
            realism=request.sliders.realism,
            preserve_texture=request.sliders.preserve_texture,
            temperature_delta=request.controls.temperature_delta if request.controls else None,
            tint_delta=request.controls.tint_delta if request.controls else None,
            exposure_ev=request.controls.exposure_ev if request.controls else None,
            contrast=request.controls.contrast if request.controls else None,
            clarity=request.controls.clarity if request.controls else None,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dreamisp_payload = plan.dreamisp_plan if isinstance(plan.dreamisp_plan, dict) else {}
    record_studio_event(
        output_root=request.output_root,
        source="studio",
        event_type="dreamisp_preview_rendered",
        session_id=request.session_id,
        status=str(dreamisp_payload.get("materialization_status") or "done"),
        detail=str(dreamisp_payload.get("render_preview_path") or plan.editable_asset_path or ""),
        metadata={
            "strength": request.sliders.strength,
            "realism": request.sliders.realism,
            "preserve_texture": request.sliders.preserve_texture,
            "temperature_delta": request.controls.temperature_delta if request.controls else None,
            "tint_delta": request.controls.tint_delta if request.controls else None,
            "exposure_ev": request.controls.exposure_ev if request.controls else None,
            "contrast": request.controls.contrast if request.controls else None,
            "clarity": request.controls.clarity if request.controls else None,
            "render_backend": dreamisp_payload.get("render_backend"),
            "render_source_kind": dreamisp_payload.get("render_source_kind"),
        },
    )
    return dump_model(plan)


@router.get("/selection")
def get_studio_selection_state(session_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        state = load_session_selection_state(session_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dump_model(state)


@router.post("/selection/apply")
def apply_studio_selection_state_route(request: StudioSelectionApplyRequest) -> Dict[str, Any]:
    try:
        state = apply_session_selection_state(
            request.session_id,
            output_root=request.output_root,
            source_mask_path=request.source_mask_path,
            source_asset_path=request.source_asset_path,
            controls=StudioSelectionControls(
                threshold=request.controls.threshold if request.controls else 128,
                expand_pixels=request.controls.expand_pixels if request.controls else 0,
                feather_radius=request.controls.feather_radius if request.controls else 4,
            ),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    linkage_state = build_or_update_session_edit_linkage(
        request.session_id,
        output_root=request.output_root,
        current_source_path=state.source_asset_path,
        selection_state=state,
    )

    record_studio_event(
        output_root=request.output_root,
        source="studio",
        event_type="selection_state_applied",
        session_id=request.session_id,
        status="done",
        detail=state.preview_path,
        metadata={
            "source_mask_path": state.source_mask_path,
            "source_asset_path": state.source_asset_path,
            "threshold": state.controls.threshold,
            "expand_pixels": state.controls.expand_pixels,
            "feather_radius": state.controls.feather_radius,
            "coverage_ratio": state.coverage_ratio,
            "linkage_state_path": linkage_state.state_path,
        },
    )
    return dump_model(state)


@router.get("/edit-linkage")
def get_studio_edit_linkage_state(session_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        state = load_session_edit_linkage(session_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dump_model(state)


@router.post("/edit-linkage")
def sync_studio_edit_linkage_state(request: StudioEditLinkageSyncRequest) -> Dict[str, Any]:
    studio_job_record = None
    if request.studio_job_id:
        try:
            studio_job_record = load_studio_job_record(request.studio_job_id, output_root=request.output_root)
        except FileNotFoundError:
            studio_job_record = None

    try:
        state = build_or_update_session_edit_linkage(
            request.session_id,
            output_root=request.output_root,
            current_source_path=request.current_source_path,
            active_tool=request.active_tool,
            studio_job_record=studio_job_record,
            source_history=request.source_history,
            source_history_index=request.source_history_index,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="studio",
        event_type="edit_linkage_synced",
        session_id=request.session_id,
        status="done",
        detail=state.current_source_path or state.state_path,
        metadata={
            "active_tool": state.active_tool,
            "latest_tool": state.latest_tool,
            "mask_ready": state.mask_ready,
            "dreamgen_ready": state.dreamgen_ready,
            "current_source_kind": state.current_source_kind,
        },
    )
    return dump_model(state)


@router.get("/intake/sessions")
def get_recent_studio_sessions(output_root: str = "outputs", limit: int = 8) -> Dict[str, Any]:
    items = list_recent_studio_sessions(output_root=output_root, limit=limit)
    return {"items": [dump_model(item) for item in items]}


@router.get("/catalog/session")
def get_studio_session_catalog(session_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        metadata = load_session_catalog(session_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dump_model(metadata)


@router.put("/catalog/session")
def update_studio_session_catalog(request: StudioCatalogUpdate) -> Dict[str, Any]:
    try:
        metadata = update_session_catalog(
            request.session_id,
            output_root=request.output_root,
            rating=request.rating,
            pick_status=request.pick_status,
            review_status=request.review_status,
            color_tag=request.color_tag,
            keywords=request.keywords,
            notes=request.notes,
            proofing_profile=request.proofing_profile,
            print_profile=request.print_profile,
            client_collection=request.client_collection,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_studio_event(
        output_root=request.output_root,
        source="ops",
        event_type="session_catalog_updated",
        session_id=request.session_id,
        status="done",
        metadata={
            "rating": metadata.rating,
            "pick_status": metadata.pick_status,
            "review_status": metadata.review_status,
            "keywords": metadata.keywords,
        },
    )
    return dump_model(metadata)


@router.post("/catalog/batch")
def batch_update_studio_session_catalog(request: StudioCatalogBatchUpdate) -> Dict[str, Any]:
    try:
        items = batch_update_session_catalogs(
            request.session_ids,
            output_root=request.output_root,
            rating=request.rating,
            pick_status=request.pick_status,
            review_status=request.review_status,
            color_tag=request.color_tag,
            keywords=request.keywords,
            notes=request.notes,
            proofing_profile=request.proofing_profile,
            print_profile=request.print_profile,
            client_collection=request.client_collection,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_studio_event(
        output_root=request.output_root,
        source="ops",
        event_type="session_catalog_batch_updated",
        status="done",
        metadata={
            "session_count": len(items),
            "pick_status": request.pick_status,
            "review_status": request.review_status,
            "keywords": request.keywords or [],
        },
    )
    return {"count": len(items), "items": [dump_model(item) for item in items]}


@router.get("/ops")
def get_studio_operations(output_root: str = "outputs", limit: int = 12) -> Dict[str, Any]:
    start_queue_worker(output_root)
    summary = summarize_studio_operations(output_root=output_root, limit=limit)
    return dump_model(summary)


@router.get("/ops/events")
def get_studio_operation_events(
    output_root: str = "outputs",
    limit: int = 20,
    source: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    session_id: str | None = None,
    query: str | None = None,
) -> Dict[str, Any]:
    items = list_recent_events(
        output_root,
        limit=limit,
        source=source,
        status=status,
        event_type=event_type,
        session_id=session_id,
        query=query,
    )
    return {"items": [dump_model(item) for item in items]}


@router.get("/ops/roots")
def get_studio_operation_roots(output_root: str = "outputs", limit: int = 8) -> Dict[str, Any]:
    items = list_operations_roots(output_root, limit=limit)
    return {"items": [dump_model(item) for item in items]}


@router.get("/ops/provider")
def get_provider_control(output_root: str = "outputs") -> Dict[str, Any]:
    return dump_model(provider_runtime_summary(output_root=output_root))


@router.get("/ops/storage-contract")
def get_runpod_storage_contract(output_root: str = "outputs") -> Dict[str, Any]:
    return dump_model(build_runpod_storage_contract(output_root=output_root))


@router.get("/ops/worker")
def get_worker_control(output_root: str = "outputs") -> Dict[str, Any]:
    return dump_model(worker_control_status(output_root))


@router.post("/ops/worker/start")
def start_worker_control(request: StudioWorkerStartRequest) -> Dict[str, Any]:
    output_roots = _resolved_request_output_roots(request.output_root, request.output_roots)
    if request.mode == "embedded":
        for output_root in output_roots:
            clear_worker_stop_request(output_root)
            start_queue_worker(output_root)
        return {"items": [dump_model(item) for item in worker_control_status_many(output_roots)]}

    try:
        items = launch_external_worker_processes(
            output_roots,
            poll_interval_seconds=request.poll_interval_seconds,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"items": [dump_model(item) for item in items]}


@router.post("/ops/worker/stop")
def stop_worker_control(request: StudioWorkerStopRequest) -> Dict[str, Any]:
    output_roots = _resolved_request_output_roots(request.output_root, request.output_roots)
    request_worker_stop_many(
        output_roots,
        requested_by="ops_api",
        reason=request.reason or "manual worker stop requested from operations board",
    )
    return {"items": [dump_model(item) for item in worker_control_status_many(output_roots)]}


@router.post("/ops/provider/pause")
def pause_provider_control(request: StudioProviderPauseRequest) -> Dict[str, Any]:
    recovery_packet = None
    if request.require_recovery_ready:
        recovery_session_id = request.recovery_session_id or (
            request.session_snapshot.session_id if request.session_snapshot is not None else None
        )
        if not recovery_session_id:
            raise HTTPException(
                status_code=400,
                detail="recovery_session_id or session_snapshot.session_id is required when require_recovery_ready=true.",
            )
        try:
            recovery_packet = build_session_recovery_packet(
                session_id=recovery_session_id,
                output_root=request.output_root,
                preset=request.recovery_preset,
                create_package=request.create_recovery_package,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not recovery_packet.ready_for_provider_pause:
            raise HTTPException(
                status_code=409,
                detail="세션 복구 패킷이 아직 준비되지 않았습니다. provider를 중지하기 전에 전달 패키지와 메타데이터 스냅샷을 먼저 export해 주세요.",
            )
        record_studio_event(
            output_root=request.output_root,
            source="ops",
            event_type="provider_pause_recovery_ready",
            session_id=recovery_session_id,
            status="done",
            detail=recovery_packet.package_archive_path or recovery_packet.metadata_snapshot_path,
            metadata={
                "recovery_preset": request.recovery_preset,
                "metadata_snapshot_path": recovery_packet.metadata_snapshot_path,
            },
        )
    try:
        summary = pause_provider_lifecycle(
            output_root=request.output_root,
            output_roots=request.output_roots,
            reason=request.reason or "provider pause requested from operations board",
            worker_mode=request.worker_mode,
            poll_interval_seconds=request.poll_interval_seconds,
            session_snapshot=_provider_session_snapshot(request.session_snapshot),
            drain_timeout_seconds=request.drain_timeout_seconds,
            stop_provider=request.stop_provider,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    payload = dump_model(summary)
    if recovery_packet is not None:
        payload["recovery_packet"] = dump_model(recovery_packet)
    return payload


@router.post("/ops/provider/resume")
def resume_provider_control(request: StudioProviderResumeRequest) -> Dict[str, Any]:
    try:
        summary, _resumed_roots = resume_provider_lifecycle(
            output_root=request.output_root,
            output_roots=request.output_roots,
            worker_mode=request.worker_mode,
            poll_interval_seconds=request.poll_interval_seconds,
            trigger="ops_api",
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return dump_model(summary)


@router.post("/ops/dead-letters/retry")
def retry_dead_letters(request: StudioDeadLetterRetryRequest) -> Dict[str, Any]:
    items = request.items or [
        StudioDeadLetterRetryItem(task_type=dead_letter.task_type, job_id=dead_letter.job_id, output_root=dead_letter.output_root)
        for dead_letter in list_dead_letters(request.output_root, limit=1000)[1]
    ]
    results: list[dict[str, Any]] = []
    for item in items:
        try:
            results.append(_retry_dead_letter_item(item))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            results.append(
                {
                    "job_id": item.job_id,
                    "task_type": item.task_type,
                    "output_root": item.output_root,
                    "status": "failed",
                    "detail": str(exc),
                }
            )
    success_count = sum(1 for item in results if item["status"] == "queued")
    return {"count": len(results), "queued": success_count, "results": results}


@router.post("/ops/dead-letters/investigate")
def investigate_dead_letter(request: StudioDeadLetterInvestigationRequest) -> Dict[str, Any]:
    try:
        investigation = update_dead_letter_investigation(
            request.output_root,
            history_path=request.history_path,
            assigned_to=request.assigned_to,
            acknowledged=request.acknowledged,
            note=request.note,
            investigation_status=request.investigation_status,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="ops",
        event_type="dead_letter_investigated",
        status=investigation.investigation_status,
        detail=investigation.history_path,
        metadata={
            "assigned_to": investigation.assigned_to,
            "acknowledged_at": investigation.acknowledged_at,
            "note": investigation.note,
        },
    )
    return dump_model(investigation)


@router.post("/intake/upload")
async def create_uploaded_studio_intake(
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(default=None),
    output_root: str = Form(default="outputs"),
    entry_preference: str = Form(default="auto"),
    camera_profile: str = Form(default="auto"),
    quality_preset: str = Form(default="balanced"),
    single_raw_mode_preference: str = Form(default="auto"),
    restoration_goal: str = Form(default=DEFAULT_RAW_RESTORATION_GOAL),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    resolved_session_id = session_id or default_session_id()
    layout = build_directory_layout(output_root, resolved_session_id)
    upload_root = Path(layout.session_root) / "_uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    try:
        for index, upload in enumerate(files):
            filename = Path(upload.filename or f"upload_{index}").name
            target = upload_root / filename
            with target.open("wb") as handle:
                shutil.copyfileobj(upload.file, handle)
            saved_paths.append(str(target))
            await upload.close()

        request = StudioIntakeRequest(
            session_id=resolved_session_id,
            output_root=output_root,
            asset_paths=saved_paths,
            entry_preference=entry_preference,  # type: ignore[arg-type]
            camera_profile=camera_profile,
            quality_preset=quality_preset,  # type: ignore[arg-type]
            single_raw_mode_preference=single_raw_mode_preference,  # type: ignore[arg-type]
            restoration_goal=restoration_goal,  # type: ignore[arg-type]
        )
        plan = build_studio_intake_plan(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        shutil.rmtree(upload_root, ignore_errors=True)

    return dump_model(plan)


@router.get("/preview")
def get_studio_preview(path: str, output_root: str = "outputs", max_edge: int = 1600) -> FileResponse:
    try:
        preview_path = build_preview_image(path, output_root=output_root, max_edge=max_edge)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(preview_path, media_type="image/jpeg")


@router.post("/compare/advice")
def get_studio_compare_advice(request: StudioCompareAdviceRequest) -> Dict[str, Any]:
    try:
        return build_compare_advice(
            output_root=request.output_root,
            primary_path=request.primary_path,
            candidate_path=request.candidate_path,
            tool=request.tool,
            seed_root=request.seed_root,
            motion_overlay_path=request.motion_overlay_path,
            motion_overlay_summary=request.motion_overlay_summary,
            motion_overlay_coverage=request.motion_overlay_coverage,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compare/decision")
def create_studio_compare_decision(request: StudioCompareDecisionRequest) -> Dict[str, Any]:
    try:
        record = record_compare_decision(
            session_id=request.session_id,
            output_root=request.output_root,
            tool=request.tool,
            select_path=request.primary_path,
            candidate_path=request.candidate_path,
            winner_path=request.winner_path,
            action=request.action,
            note=request.note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="studio",
        event_type="compare_decision_recorded",
        session_id=request.session_id,
        status="done",
        detail=record.winner_path,
        metadata={
            "tool": record.tool,
            "winner_role": record.winner_role,
            "action": record.action,
        },
    )
    return dump_model(record)


@router.get("/quality-automation/policy")
def get_quality_automation_policy() -> Dict[str, Any]:
    return dump_model(build_quality_automation_policy())


@router.post("/quality-automation/assess")
def create_quality_assessment(request: StudioQualityAssessmentRequest) -> Dict[str, Any]:
    qwen_judge_signal = request.qwen_judge_signal
    try:
        if qwen_judge_signal is None and request.run_qwen_judge:
            qwen_judge_signal = build_qwen_judge_signal(
                result_path=request.result_path,
                output_root=request.output_root,
                reference_path=request.reference_path,
                tool=request.tool,
                task_intent=request.task_intent,
                seed_root=request.seed_root,
                operation_context=request.operation_context,
                mask_evidence=request.mask_evidence,
                raw_evidence=request.raw_evidence,
                workflow_evidence=request.workflow_evidence,
                user_preference_evidence=request.user_preference_evidence,
            )
        record = build_quality_assessment(
            result_path=request.result_path,
            output_root=request.output_root,
            reference_path=request.reference_path,
            session_id=request.session_id,
            tool=request.tool,
            task_intent=request.task_intent,
            qwen_judge_signal=qwen_judge_signal,
            judge_evidence_packet=request.judge_evidence_packet,
            seed_root=request.seed_root,
            operation_context=request.operation_context,
            mask_evidence=request.mask_evidence,
            raw_evidence=request.raw_evidence,
            workflow_evidence=request.workflow_evidence,
            user_preference_evidence=request.user_preference_evidence,
            write_artifact=request.write_artifact,
        )
    except QwenJudgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="quality_automation",
        event_type="quality_assessment_recorded",
        session_id=request.session_id,
        status=record.verdict,
        detail=record.result_path,
        metadata={
            "tool": record.tool,
            "failure_tags": record.failure_tags,
            "human_approval_required": record.human_approval_required,
            "golden_profile": record.golden_calibration.profile_id if record.golden_calibration else None,
            "golden_calibrated_verdict": (
                record.golden_calibration.calibrated_verdict if record.golden_calibration else None
            ),
            "artifact_path": record.artifact_path,
        },
    )
    return dump_model(record)


@router.post("/quality-automation/tuning/proposal")
def create_quality_tuning_proposal(request: StudioQualityTuningProposalRequest) -> Dict[str, Any]:
    assessments: list[Dict[str, Any] | str] = []
    assessments.extend(request.assessments)
    assessments.extend(request.assessment_paths)
    try:
        proposal = build_quality_tuning_proposal(
            output_root=request.output_root,
            session_id=request.session_id,
            assessments=assessments,
            write_artifact=request.write_artifact,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="quality_tuning",
        event_type="quality_tuning_proposal_created",
        session_id=request.session_id,
        status=proposal.status,
        detail=proposal.artifact_path or proposal.proposal_id,
        metadata={
            "source_assessment_count": proposal.source_assessment_count,
            "automatic_code_tuning_enabled": proposal.automatic_code_tuning_enabled,
            "failure_clusters": proposal.failure_clusters,
        },
    )
    return dump_model(proposal)


@router.post("/export")
def export_studio_asset(request: StudioExportRequest) -> Dict[str, Any]:
    try:
        export_path = export_output_file(
            request.path,
            output_root=request.output_root,
            session_id=request.session_id,
            label=request.label,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "session_id": request.session_id,
        "output_root": request.output_root,
        "export_path": str(export_path),
        "file_name": export_path.name,
    }
    record_studio_event(
        output_root=request.output_root,
        source="export",
        event_type="asset_exported",
        session_id=request.session_id,
        detail=str(export_path),
        metadata={"label": request.label or "export"},
    )
    return response


@router.post("/export/package")
def export_studio_package(request: StudioExportPackageRequest) -> Dict[str, Any]:
    try:
        archive_path = export_session_package(
            session_id=request.session_id,
            output_root=request.output_root,
            items=[dump_model(item) for item in request.items],
            label=request.label,
            metadata=request.metadata,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "session_id": request.session_id,
        "output_root": request.output_root,
        "archive_path": str(archive_path),
        "file_name": archive_path.name,
        "file_count": len(request.items),
    }
    record_studio_event(
        output_root=request.output_root,
        source="export",
        event_type="package_exported",
        session_id=request.session_id,
        detail=str(archive_path),
        metadata={"label": request.label or "delivery_package", "file_count": len(request.items)},
    )
    return response


@router.post("/export/preset")
def export_studio_preset_package(request: StudioPresetExportRequest) -> Dict[str, Any]:
    try:
        response = build_delivery_preset_package(
            session_id=request.session_id,
            output_root=request.output_root,
            preset=request.preset,
            label=request.label,
            metadata=request.metadata,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_studio_event(
        output_root=request.output_root,
        source="export",
        event_type="delivery_preset_exported",
        session_id=request.session_id,
        status="done",
        detail=response["archive_path"],
        metadata={"preset": request.preset, "delivery_profile": response["delivery_profile"]},
    )
    return response


@router.get("/export/recovery")
def get_studio_recovery_packet(session_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        packet = load_session_recovery_packet(session_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dump_model(packet)


@router.post("/export/recovery")
def export_studio_recovery_packet(request: StudioRecoveryPacketRequest) -> Dict[str, Any]:
    try:
        packet = build_session_recovery_packet(
            session_id=request.session_id,
            output_root=request.output_root,
            preset=request.preset,
            create_package=request.create_package,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_studio_event(
        output_root=request.output_root,
        source="export",
        event_type="session_recovery_packet_built",
        session_id=request.session_id,
        status="done" if packet.ready_for_provider_pause else "warning",
        detail=packet.package_archive_path or packet.metadata_snapshot_path,
        metadata={
            "preset": request.preset,
            "ready_for_provider_pause": packet.ready_for_provider_pause,
            "metadata_snapshot_path": packet.metadata_snapshot_path,
        },
    )
    return dump_model(packet)


@router.post("/export/batch")
def export_studio_batch_packages(request: StudioBatchExportRequest) -> Dict[str, Any]:
    try:
        response = export_batch_delivery_packages(
            output_root=request.output_root,
            session_ids=request.session_ids,
            preset=request.preset,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_studio_event(
        output_root=request.output_root,
        source="export",
        event_type="batch_package_exported",
        status="done",
        detail=response["report_path"],
        metadata={"preset": request.preset, "session_count": response["session_count"]},
    )
    return response


@router.get("/download")
def download_studio_asset(path: str, output_root: str = "outputs") -> FileResponse:
    try:
        target = resolve_output_target(path, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(target, filename=target.name)
