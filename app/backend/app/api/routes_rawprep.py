from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..core.rawprep_catalog import list_engine_specs, preview_runtime_note, rawprep_catalog_payload
from ..core.rawprep_benchmark_service import (
    RawPrepBenchmarkRequest,
    build_rawprep_benchmark_foundation_health,
    load_rawprep_benchmark_record,
    load_rawprep_benchmark_report,
    run_rawprep_benchmark,
)
from ..core.rawprep_benchmark_gate import build_rawprep_benchmark_gate
from ..core.rawprep_benchmark_gate import (
    RawPrepBenchmarkGateRequest,
    load_rawprep_benchmark_gate,
    write_rawprep_benchmark_gate,
)
from ..core.rawprep_benchmark_measurement_batch import (
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest,
    RawPrepBenchmarkMeasurementBatchRequest,
    write_rawprep_benchmark_measurement_batch_from_single_raw_report,
    write_rawprep_benchmark_measurement_batch,
)
from ..core.rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
    RawPrepBenchmarkMeasurementRequest,
    RawPrepBenchmarkMeasurementWriteRequest,
    build_rawprep_benchmark_measurement,
    write_rawprep_benchmark_measurement,
    write_rawprep_benchmark_measurement_from_single_raw_report,
)
from ..core.rawprep_benchmark_measurement_report_scaffold import (
    RawPrepBenchmarkMeasurementReportScaffoldRequest,
    build_rawprep_benchmark_measurement_report_scaffold,
)
from ..core.rawprep_benchmark_single_raw_run import (
    RawPrepBenchmarkSingleRawRunRequest,
    run_rawprep_benchmark_single_raw_samples,
)
from ..core.rawprep_benchmark_local_e2e_smoke import (
    RawPrepBenchmarkLocalE2ESmokeRequest,
    build_rawprep_benchmark_local_e2e_smoke,
    load_rawprep_benchmark_local_e2e_smoke,
    write_rawprep_benchmark_local_e2e_smoke,
)
from ..core.rawprep_benchmark_local_recovery_smoke import (
    RawPrepBenchmarkLocalRecoverySmokeRequest,
    build_rawprep_benchmark_local_recovery_smoke,
    load_rawprep_benchmark_local_recovery_smoke,
    write_rawprep_benchmark_local_recovery_smoke,
)
from ..core.rawprep_benchmark_local_ui_language_smoke import (
    RawPrepBenchmarkLocalUiLanguageSmokeRequest,
    build_rawprep_benchmark_local_ui_language_smoke,
    load_rawprep_benchmark_local_ui_language_smoke,
    write_rawprep_benchmark_local_ui_language_smoke,
)
from ..core.rawprep_benchmark_tri_raw_run import (
    RawPrepBenchmarkTriRawRunRequest,
    run_rawprep_benchmark_tri_raw_samples,
)
from ..core.rawprep_benchmark_packet import (
    RawPrepBenchmarkPacketRequest,
    load_rawprep_benchmark_packet,
    write_rawprep_benchmark_packet,
)
from ..core.rawprep_benchmark_runpod_smoke import (
    RawPrepBenchmarkRunPodSmokeRequest,
    build_rawprep_benchmark_runpod_smoke,
    load_rawprep_benchmark_runpod_smoke,
    write_rawprep_benchmark_runpod_smoke,
)
from ..core.rawprep_benchmark_runpod_smoke_plan import (
    RawPrepBenchmarkRunPodSmokePlanRequest,
    build_rawprep_benchmark_runpod_smoke_plan,
    load_rawprep_benchmark_runpod_smoke_plan,
    write_rawprep_benchmark_runpod_smoke_plan,
)
from ..core.rawprep_benchmark_runpod_smoke_stage import (
    RawPrepBenchmarkRunPodSmokeStageRequest,
    build_rawprep_benchmark_runpod_smoke_stage,
    load_rawprep_benchmark_runpod_smoke_stage,
    write_rawprep_benchmark_runpod_smoke_stage,
)
from ..core.rawprep_benchmark_runpod_smoke_handoff import (
    RawPrepBenchmarkRunPodSmokeHandoffRequest,
    build_rawprep_benchmark_runpod_smoke_handoff,
    load_rawprep_benchmark_runpod_smoke_handoff,
    write_rawprep_benchmark_runpod_smoke_handoff,
)
from ..core.rawprep_benchmark_scaffold import (
    RawPrepBenchmarkScaffoldRequest,
    build_rawprep_benchmark_scaffold,
)
from ..core.rawprep_benchmark_review import (
    RawPrepBenchmarkReleaseReviewRequest,
    build_rawprep_benchmark_release_review,
    load_rawprep_benchmark_release_review,
    write_rawprep_benchmark_release_review,
)
from ..core.rawprep_benchmark_default_decision import (
    RawPrepBenchmarkDefaultDecisionRequest,
    build_rawprep_benchmark_default_decision,
    load_rawprep_benchmark_default_decision,
    write_rawprep_benchmark_default_decision,
)
from ..core.rawprep_contract import RawPrepJobRequest, build_job_plan
from ..core.raw_restoration_policy import build_raw_restoration_policy
from ..core.rawprep_runner import (
    build_rawprep_command_previews,
    detect_rawprep_tools,
    missing_required_tools,
    required_tools_for_plan,
)
from ..core.rawprep_service import (
    dump_model,
    initialize_rawprep_job,
    load_job_record,
    request_rawprep_cancel,
    retry_rawprep_job,
    save_job_record,
)
from ..core.studio_queue import clear_worker_stop_request, enqueue_job, start_queue_worker


router = APIRouter(prefix="/api/rawprep", tags=["rawprep"])


def load_group_reports(record) -> list[Dict[str, Any]]:
    reports: list[Dict[str, Any]] = []
    for artifact in record.artifacts:
        if artifact.kind != "report":
            continue
        path = Path(artifact.path)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        reports.append(payload)
    return reports


@router.get("/health")
def rawprep_health() -> Dict[str, Any]:
    tool_status = detect_rawprep_tools()
    engine_readiness = {}
    for spec in list_engine_specs():
        engine_readiness[spec.engine_stack] = {
            "required_tools": spec.required_tools,
            "missing_tools": missing_required_tools(tool_status, spec.required_tools),
        }

    return {
        "ok": any(not payload["missing_tools"] for payload in engine_readiness.values()),
        "message": preview_runtime_note(),
        "tool_status": {name: dump_model(status) for name, status in tool_status.items()},
        "engine_readiness": engine_readiness,
    }


@router.get("/catalog")
def rawprep_catalog() -> Dict[str, Any]:
    return rawprep_catalog_payload()


@router.get("/restoration-goals")
def rawprep_restoration_goals() -> Dict[str, Any]:
    return build_raw_restoration_policy().model_dump()


@router.post("/benchmark")
def create_rawprep_benchmark(request: RawPrepBenchmarkRequest) -> Dict[str, Any]:
    try:
        record = run_rawprep_benchmark(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(record)


@router.post("/benchmark/scaffold")
def scaffold_rawprep_benchmark(request: RawPrepBenchmarkScaffoldRequest) -> Dict[str, Any]:
    try:
        scaffold = build_rawprep_benchmark_scaffold(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(scaffold)


@router.get("/benchmark")
def get_rawprep_benchmark(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = load_rawprep_benchmark_record(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(record)


@router.get("/benchmark/foundation")
def get_rawprep_benchmark_foundation_health(output_root: str = "outputs") -> Dict[str, Any]:
    try:
        health = build_rawprep_benchmark_foundation_health(output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(health)


@router.get("/benchmark/measurement")
def get_rawprep_benchmark_measurement(sample_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        measurement = build_rawprep_benchmark_measurement(sample_id, output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(measurement)


@router.post("/benchmark/measurement")
def create_rawprep_benchmark_measurement(request: RawPrepBenchmarkMeasurementWriteRequest) -> Dict[str, Any]:
    try:
        measurement = write_rawprep_benchmark_measurement(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(measurement)


@router.post("/benchmark/measurement/from-single-raw-report")
def create_rawprep_benchmark_measurement_from_single_raw_report(
    request: RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
) -> Dict[str, Any]:
    try:
        measurement = write_rawprep_benchmark_measurement_from_single_raw_report(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(measurement)


@router.post("/benchmark/measurement/batch")
def create_rawprep_benchmark_measurement_batch(request: RawPrepBenchmarkMeasurementBatchRequest) -> Dict[str, Any]:
    try:
        batch = write_rawprep_benchmark_measurement_batch(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(batch)


@router.post("/benchmark/measurement/batch/from-single-raw-report")
def create_rawprep_benchmark_measurement_batch_from_single_raw_report(
    request: RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest,
) -> Dict[str, Any]:
    try:
        batch = write_rawprep_benchmark_measurement_batch_from_single_raw_report(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(batch)


@router.post("/benchmark/measurement/report-scaffold")
def create_rawprep_benchmark_measurement_report_scaffold(
    request: RawPrepBenchmarkMeasurementReportScaffoldRequest,
) -> Dict[str, Any]:
    try:
        scaffold = build_rawprep_benchmark_measurement_report_scaffold(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(scaffold)


@router.post("/benchmark/single-raw/run")
def create_rawprep_benchmark_single_raw_run(request: RawPrepBenchmarkSingleRawRunRequest) -> Dict[str, Any]:
    try:
        record = run_rawprep_benchmark_single_raw_samples(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(record)


@router.post("/benchmark/tri-raw/run")
def create_rawprep_benchmark_tri_raw_run(request: RawPrepBenchmarkTriRawRunRequest) -> Dict[str, Any]:
    try:
        record = run_rawprep_benchmark_tri_raw_samples(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(record)


@router.get("/benchmark/local-e2e-smoke")
def get_rawprep_benchmark_local_e2e_smoke(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = build_rawprep_benchmark_local_e2e_smoke(
            RawPrepBenchmarkLocalE2ESmokeRequest(output_dir=output_dir, output_root=output_root)
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/local-e2e-smoke/artifact")
def get_rawprep_benchmark_local_e2e_smoke_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = load_rawprep_benchmark_local_e2e_smoke(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(smoke)


@router.post("/benchmark/local-e2e-smoke")
def create_rawprep_benchmark_local_e2e_smoke(request: RawPrepBenchmarkLocalE2ESmokeRequest) -> Dict[str, Any]:
    try:
        smoke = write_rawprep_benchmark_local_e2e_smoke(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/local-recovery-smoke")
def get_rawprep_benchmark_local_recovery_smoke(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = build_rawprep_benchmark_local_recovery_smoke(
            RawPrepBenchmarkLocalRecoverySmokeRequest(output_dir=output_dir, output_root=output_root)
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/local-recovery-smoke/artifact")
def get_rawprep_benchmark_local_recovery_smoke_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = load_rawprep_benchmark_local_recovery_smoke(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(smoke)


@router.post("/benchmark/local-recovery-smoke")
def create_rawprep_benchmark_local_recovery_smoke(request: RawPrepBenchmarkLocalRecoverySmokeRequest) -> Dict[str, Any]:
    try:
        smoke = write_rawprep_benchmark_local_recovery_smoke(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/local-ui-language-smoke")
def get_rawprep_benchmark_local_ui_language_smoke(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = build_rawprep_benchmark_local_ui_language_smoke(
            RawPrepBenchmarkLocalUiLanguageSmokeRequest(output_dir=output_dir, output_root=output_root)
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/local-ui-language-smoke/artifact")
def get_rawprep_benchmark_local_ui_language_smoke_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = load_rawprep_benchmark_local_ui_language_smoke(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(smoke)


@router.post("/benchmark/local-ui-language-smoke")
def create_rawprep_benchmark_local_ui_language_smoke(request: RawPrepBenchmarkLocalUiLanguageSmokeRequest) -> Dict[str, Any]:
    try:
        smoke = write_rawprep_benchmark_local_ui_language_smoke(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.post("/benchmark/packet")
def create_rawprep_benchmark_packet(request: RawPrepBenchmarkPacketRequest) -> Dict[str, Any]:
    try:
        packet = write_rawprep_benchmark_packet(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(packet)


@router.get("/benchmark/packet/artifact")
def get_rawprep_benchmark_packet_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        packet = load_rawprep_benchmark_packet(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(packet)


@router.get("/benchmark/gate")
def get_rawprep_benchmark_gate(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        gate = build_rawprep_benchmark_gate(output_dir, output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(gate)


@router.get("/benchmark/runpod-smoke")
def get_rawprep_benchmark_runpod_smoke(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = build_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/runpod-smoke/artifact")
def get_rawprep_benchmark_runpod_smoke_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        smoke = load_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(smoke)


@router.post("/benchmark/runpod-smoke")
def create_rawprep_benchmark_runpod_smoke(request: RawPrepBenchmarkRunPodSmokeRequest) -> Dict[str, Any]:
    try:
        smoke = write_rawprep_benchmark_runpod_smoke(request.output_dir, output_root=request.output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(smoke)


@router.get("/benchmark/runpod-smoke-plan")
def get_rawprep_benchmark_runpod_smoke_plan(
    output_dir: str,
    output_root: str = "outputs",
    manifest_path: str | None = None,
    sample_id: str | None = None,
    sample_working_root: str = "outputs/_single_raw_healthcheck",
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json",
) -> Dict[str, Any]:
    try:
        plan = build_rawprep_benchmark_runpod_smoke_plan(
            RawPrepBenchmarkRunPodSmokePlanRequest(
                output_dir=output_dir,
                output_root=output_root,
                manifest_path=manifest_path,
                sample_id=sample_id,
                sample_working_root=sample_working_root,
                runtime_output_path=runtime_output_path,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(plan)


@router.get("/benchmark/runpod-smoke-plan/artifact")
def get_rawprep_benchmark_runpod_smoke_plan_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        plan = load_rawprep_benchmark_runpod_smoke_plan(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(plan)


@router.post("/benchmark/runpod-smoke-plan")
def create_rawprep_benchmark_runpod_smoke_plan(request: RawPrepBenchmarkRunPodSmokePlanRequest) -> Dict[str, Any]:
    try:
        plan = write_rawprep_benchmark_runpod_smoke_plan(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(plan)


@router.get("/benchmark/runpod-smoke-stage")
def get_rawprep_benchmark_runpod_smoke_stage(
    output_dir: str,
    output_root: str = "outputs",
    manifest_path: str | None = None,
    sample_id: str | None = None,
    sample_working_root: str = "outputs/_single_raw_healthcheck",
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json",
) -> Dict[str, Any]:
    try:
        stage = build_rawprep_benchmark_runpod_smoke_stage(
            RawPrepBenchmarkRunPodSmokeStageRequest(
                output_dir=output_dir,
                output_root=output_root,
                manifest_path=manifest_path,
                sample_id=sample_id,
                sample_working_root=sample_working_root,
                runtime_output_path=runtime_output_path,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(stage)


@router.get("/benchmark/runpod-smoke-stage/artifact")
def get_rawprep_benchmark_runpod_smoke_stage_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        stage = load_rawprep_benchmark_runpod_smoke_stage(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(stage)


@router.post("/benchmark/runpod-smoke-stage")
def create_rawprep_benchmark_runpod_smoke_stage(request: RawPrepBenchmarkRunPodSmokeStageRequest) -> Dict[str, Any]:
    try:
        stage = write_rawprep_benchmark_runpod_smoke_stage(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(stage)


@router.get("/benchmark/runpod-smoke-handoff")
def get_rawprep_benchmark_runpod_smoke_handoff(
    output_dir: str,
    output_root: str = "outputs",
    manifest_path: str | None = None,
    sample_id: str | None = None,
    sample_working_root: str = "outputs/_single_raw_healthcheck",
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json",
    release_bundle_path: str | None = None,
) -> Dict[str, Any]:
    try:
        handoff = build_rawprep_benchmark_runpod_smoke_handoff(
            RawPrepBenchmarkRunPodSmokeHandoffRequest(
                output_dir=output_dir,
                output_root=output_root,
                manifest_path=manifest_path,
                sample_id=sample_id,
                sample_working_root=sample_working_root,
                runtime_output_path=runtime_output_path,
                release_bundle_path=release_bundle_path,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(handoff)


@router.get("/benchmark/runpod-smoke-handoff/artifact")
def get_rawprep_benchmark_runpod_smoke_handoff_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        handoff = load_rawprep_benchmark_runpod_smoke_handoff(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(handoff)


@router.post("/benchmark/runpod-smoke-handoff")
def create_rawprep_benchmark_runpod_smoke_handoff(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> Dict[str, Any]:
    try:
        handoff = write_rawprep_benchmark_runpod_smoke_handoff(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(handoff)


@router.get("/benchmark/gate/artifact")
def get_rawprep_benchmark_gate_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        gate = load_rawprep_benchmark_gate(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(gate)


@router.post("/benchmark/gate")
def create_rawprep_benchmark_gate(request: RawPrepBenchmarkGateRequest) -> Dict[str, Any]:
    try:
        gate = write_rawprep_benchmark_gate(request.output_dir, output_root=request.output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(gate)


@router.get("/benchmark/review")
def get_rawprep_benchmark_release_review(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        review = build_rawprep_benchmark_release_review(output_dir, output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(review)


@router.get("/benchmark/review/artifact")
def get_rawprep_benchmark_release_review_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        review = load_rawprep_benchmark_release_review(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(review)


@router.post("/benchmark/review")
def create_rawprep_benchmark_release_review(request: RawPrepBenchmarkReleaseReviewRequest) -> Dict[str, Any]:
    try:
        review = write_rawprep_benchmark_release_review(request.output_dir, output_root=request.output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(review)


@router.get("/benchmark/default-decision")
def get_rawprep_benchmark_default_decision(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        decision = build_rawprep_benchmark_default_decision(output_dir, output_root=output_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(decision)


@router.get("/benchmark/default-decision/artifact")
def get_rawprep_benchmark_default_decision_artifact(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        decision = load_rawprep_benchmark_default_decision(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(decision)


@router.post("/benchmark/default-decision")
def create_rawprep_benchmark_default_decision(request: RawPrepBenchmarkDefaultDecisionRequest) -> Dict[str, Any]:
    try:
        decision = write_rawprep_benchmark_default_decision(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dump_model(decision)


@router.get("/benchmark/report")
def get_rawprep_benchmark_report(output_dir: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        report = load_rawprep_benchmark_report(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(report)


@router.post("/jobs")
def create_rawprep_job(
    request: RawPrepJobRequest,
    execute: bool = False,
) -> Dict[str, Any]:
    plan = build_job_plan(request)
    tool_status = detect_rawprep_tools()
    commands = build_rawprep_command_previews(plan, tool_status=tool_status)
    record = initialize_rawprep_job(plan, tool_status=tool_status, command_previews=commands)
    required_tools = required_tools_for_plan(plan)

    if execute and not record.missing_tools:
        record.status = "queued"
        record.current_step = "queued"
        record.notes.append("rawprep job was queued for immediate background execution.")
        save_job_record(record)
        enqueue_job(
            task_type="rawprep",
            job_id=plan.job_id,
            session_id=plan.session_id,
            output_root=plan.output_root,
        )
        clear_worker_stop_request(plan.output_root)
        start_queue_worker(plan.output_root)
    elif execute and record.missing_tools:
        record.notes.append("Immediate execution was requested, but the required rawprep tools are missing.")
        save_job_record(record)

    return {
        "job_id": plan.job_id,
        "session_id": plan.session_id,
        "status": record.status,
        "missing_tools": record.missing_tools,
        "required_tools": required_tools,
        "plan": dump_model(plan),
        "tool_status": record.tool_status,
        "command_previews": [dump_model(command) for command in commands],
        "notes": record.notes,
        "state_path": record.state_path,
    }


@router.get("/jobs/{job_id}")
def get_rawprep_job(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = load_job_record(job_id, output_root=output_root)
        if record.status == "queued":
            start_queue_worker(record.output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = dump_model(record)
    payload["group_reports"] = load_group_reports(record)
    return payload


@router.get("/jobs/{job_id}/artifacts")
def get_rawprep_artifacts(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = load_job_record(job_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "job_id": record.job_id,
        "session_id": record.session_id,
        "status": record.status,
        "artifacts": [dump_model(artifact) for artifact in record.artifacts],
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_rawprep_job(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = request_rawprep_cancel(job_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return dump_model(record)


@router.post("/jobs/{job_id}/retry")
def retry_rawprep_saved_job(
    job_id: str,
    output_root: str = "outputs",
) -> Dict[str, Any]:
    try:
        plan, record, _tool_status = retry_rawprep_job(job_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if record.missing_tools:
        record.notes.append("Retry was requested, but the required rawprep tools are still missing.")
        save_job_record(record)
        return dump_model(record)

    record.status = "queued"
    record.current_step = "queued"
    record.notes.append("rawprep job was re-queued for background execution.")
    save_job_record(record)
    enqueue_job(
        task_type="rawprep",
        job_id=plan.job_id,
        session_id=plan.session_id,
        output_root=plan.output_root,
    )
    clear_worker_stop_request(plan.output_root)
    start_queue_worker(plan.output_root)
    return dump_model(record)
