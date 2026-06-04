from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_paths import repo_root, resolve_output_root


class RawPrepSingleRawFastReadinessRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    benchmark_report_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    local_timing_target_ms: float = 6000.0
    runpod_timing_target_ms: float = 12000.0


class RawPrepSingleRawFastReadinessChecks(BaseModel):
    measured_coverage_complete: bool = False
    local_fast_timing_within_target: bool = False
    runpod_fast_timing_within_target: bool = False
    runpod_fast_mode_confirmed: bool = False
    compare_baseline_available: bool = False
    editable_output_available: bool = False
    diagnostics_available: bool = False


class RawPrepSingleRawFastReadinessArtifact(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_evidence"
    summary: str
    artifact_path: str | None = None
    benchmark_report_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    local_timing_target_ms: float
    runpod_timing_target_ms: float
    measured_sample_count: int = 0
    expected_sample_count: int = 0
    local_timing_ms_mean: float | None = None
    runpod_sample_timing_ms: float | None = None
    runpod_runtime_profile: str | None = None
    runpod_sample_raw_path: str | None = None
    metric_mean_by_axis: dict[str, float] = Field(default_factory=dict)
    checks: RawPrepSingleRawFastReadinessChecks
    blockers: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("SingleRaw fast readiness output_dir must stay inside the configured output root.") from exc
    return resolved


def _artifact_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_single_raw_fast_readiness.json"


def _resolve_report_path(request: RawPrepSingleRawFastReadinessRequest) -> Path:
    if request.benchmark_report_path:
        candidate = Path(request.benchmark_report_path)
        return candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    return _resolve_output_dir(request.output_dir, output_root=request.output_root) / "rawprep_benchmark_report.json"


def _resolve_healthcheck_path(request: RawPrepSingleRawFastReadinessRequest) -> Path:
    if request.single_raw_healthcheck_path:
        candidate = Path(request.single_raw_healthcheck_path)
        return candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    return (repo_root() / "app" / "runtime" / "single_raw_healthcheck.json").resolve()


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def build_rawprep_single_raw_fast_readiness(
    request: RawPrepSingleRawFastReadinessRequest,
) -> RawPrepSingleRawFastReadinessArtifact:
    report_path = _resolve_report_path(request)
    healthcheck_path = _resolve_healthcheck_path(request)
    report_payload = _load_json_dict(report_path)
    healthcheck_payload = _load_json_dict(healthcheck_path)

    blockers: list[str] = []
    recommended_actions: list[str] = []

    if report_payload is None:
        blockers.append("SingleRaw measured benchmark report가 없어 practical readiness를 계산할 수 없습니다.")
    if healthcheck_payload is None:
        blockers.append("RunPod single_raw_healthcheck.json이 없어 실제 sample decode timing을 확인할 수 없습니다.")

    single_raw_summary = report_payload.get("single_raw_summary", {}) if report_payload else {}
    metric_mean_by_axis = {
        str(key): float(value)
        for key, value in (single_raw_summary.get("metric_mean_by_axis", {}) or {}).items()
        if value is not None
    }
    measured_sample_count = int(single_raw_summary.get("measured_sample_count") or 0) if single_raw_summary else 0
    expected_sample_count = int(single_raw_summary.get("sample_count") or 0) if single_raw_summary else 0
    local_timing_ms_mean = (
        float(single_raw_summary.get("timing_ms_mean"))
        if single_raw_summary and single_raw_summary.get("timing_ms_mean") is not None
        else None
    )

    sample_result = healthcheck_payload.get("sample_result") if healthcheck_payload else None
    if not isinstance(sample_result, dict):
        sample_result = {}
    timing_report = sample_result.get("timing_report") if isinstance(sample_result.get("timing_report"), dict) else {}
    noise_report = sample_result.get("noise_report") if isinstance(sample_result.get("noise_report"), dict) else {}
    artifact_guardrail = sample_result.get("artifact_guardrail") if isinstance(sample_result.get("artifact_guardrail"), dict) else {}

    runpod_sample_timing_ms = (
        float(timing_report.get("total_ms"))
        if timing_report.get("total_ms") is not None
        else None
    )
    runpod_runtime_profile = str(sample_result.get("runtime_profile") or "") or None
    runpod_execution_mode = str(sample_result.get("execution_mode") or "") or None
    runpod_sample_raw_path = (
        str(healthcheck_payload.get("sample_raw_path") or "")
        if isinstance(healthcheck_payload, dict)
        else ""
    ) or None
    input_preview_path = str(sample_result.get("input_preview_path") or "") or None
    preview_path = str(sample_result.get("preview_path") or "") or None
    scene_linear_path = str(sample_result.get("scene_linear_path") or "") or None

    checks = RawPrepSingleRawFastReadinessChecks(
        measured_coverage_complete=expected_sample_count > 0 and measured_sample_count == expected_sample_count,
        local_fast_timing_within_target=local_timing_ms_mean is not None and local_timing_ms_mean <= request.local_timing_target_ms,
        runpod_fast_timing_within_target=runpod_sample_timing_ms is not None and runpod_sample_timing_ms <= request.runpod_timing_target_ms,
        runpod_fast_mode_confirmed=(
            bool(healthcheck_payload)
            and bool(healthcheck_payload.get("sample_decode_ok"))
            and runpod_execution_mode == "fast"
        ),
        compare_baseline_available=bool(input_preview_path and preview_path),
        editable_output_available=bool(preview_path and scene_linear_path),
        diagnostics_available=bool(noise_report and artifact_guardrail),
    )

    if not checks.measured_coverage_complete:
        blockers.append("SingleRaw measured benchmark coverage가 아직 완전하지 않습니다.")
        recommended_actions.append("official SingleRaw manifest의 measured sample count가 sample count와 같아질 때까지 benchmark result를 채우세요.")
    if local_timing_ms_mean is None:
        blockers.append("SingleRaw local timing 평균이 benchmark report에 없습니다.")
    if runpod_sample_timing_ms is None:
        blockers.append("RunPod sample decode timing이 single_raw_healthcheck.json에 없습니다.")
    if not checks.runpod_fast_mode_confirmed:
        blockers.append("RunPod sample decode가 fast 모드로 끝났다는 근거가 부족합니다.")
    if not checks.compare_baseline_available:
        blockers.append("input preview와 preview result가 같이 남지 않아 fast compare baseline을 확인할 수 없습니다.")
    if not checks.editable_output_available:
        blockers.append("preview 또는 scene_linear output evidence가 부족합니다.")
    if not checks.diagnostics_available:
        blockers.append("noise_report와 artifact_guardrail evidence가 함께 남지 않았습니다.")
    if local_timing_ms_mean is not None and not checks.local_fast_timing_within_target:
        blockers.append("SingleRaw local mean timing이 실사용 목표를 넘었습니다.")
        recommended_actions.append("Fast path timing을 더 줄이거나 목표 시간을 다시 정의하기 전에 추가 측정 근거를 확보하세요.")
    if runpod_sample_timing_ms is not None and not checks.runpod_fast_timing_within_target:
        blockers.append("RunPod sample fast timing이 실사용 목표를 넘었습니다.")
        recommended_actions.append("RunPod fast decode timing을 다시 측정하고, decode/artifact write 분해값을 기준으로 병목을 줄이세요.")

    if not report_payload:
        recommended_actions.append("measured benchmark report를 먼저 생성한 뒤 readiness artifact를 다시 쓰세요.")
    if not healthcheck_payload:
        recommended_actions.append("RunPod에서 single_raw_healthcheck.py --sample-raw smoke를 다시 실행해 timing evidence를 남기세요.")

    if blockers:
        if report_payload is None or healthcheck_payload is None:
            status = "missing_evidence"
            summary = "SingleRaw fast readiness를 판단할 measured benchmark 또는 RunPod sample decode evidence가 아직 부족합니다."
        else:
            status = "needs_tuning"
            summary = "SingleRaw fast evidence는 있지만, 실사용 readiness를 닫기엔 아직 보완이 필요합니다."
    else:
        status = "ready_for_practical_use"
        summary = (
            f"SingleRaw fast measured {measured_sample_count}/{expected_sample_count}, "
            f"local mean {local_timing_ms_mean:.1f}ms, RunPod sample {runpod_sample_timing_ms:.1f}ms로 "
            "실사용 시간/품질 근거가 준비됐습니다."
        )

    artifact = RawPrepSingleRawFastReadinessArtifact(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
        benchmark_report_path=str(report_path),
        single_raw_healthcheck_path=str(healthcheck_path),
        local_timing_target_ms=request.local_timing_target_ms,
        runpod_timing_target_ms=request.runpod_timing_target_ms,
        measured_sample_count=measured_sample_count,
        expected_sample_count=expected_sample_count,
        local_timing_ms_mean=local_timing_ms_mean,
        runpod_sample_timing_ms=runpod_sample_timing_ms,
        runpod_runtime_profile=runpod_runtime_profile,
        runpod_sample_raw_path=runpod_sample_raw_path,
        metric_mean_by_axis=metric_mean_by_axis,
        checks=checks,
        blockers=blockers,
        recommended_actions=recommended_actions,
        ok=not blockers,
    )
    return artifact


def write_rawprep_single_raw_fast_readiness(
    request: RawPrepSingleRawFastReadinessRequest,
) -> RawPrepSingleRawFastReadinessArtifact:
    artifact = build_rawprep_single_raw_fast_readiness(request)
    path = _artifact_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def load_rawprep_single_raw_fast_readiness(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepSingleRawFastReadinessArtifact:
    path = _artifact_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"SingleRaw fast readiness artifact was not found: {path}")
    return RawPrepSingleRawFastReadinessArtifact(**json.loads(path.read_text(encoding="utf-8")))
