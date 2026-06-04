from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.raw_engine_v2.tri_raw.planner import (
    build_tri_raw_foundation_plan,
    materialize_tri_raw_foundation_plan,
)
from app.raw_engine_v2.tri_raw.runtime import (
    TriRawPreviewRuntimeResult,
    materialize_tri_raw_preview_runtime,
)

from .rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementWriteRequest,
    write_rawprep_benchmark_measurement,
)
from .rawprep_benchmark_service import (
    RawPrepBenchmarkRequest,
    _load_optional_manifest,
    _sample_entries,
    _tri_raw_manifest_path,
    run_rawprep_benchmark,
)
from .studio_paths import repo_root, resolve_output_root


TriRawReferencePolicy = Literal["auto", "first", "middle", "last"]


class RawPrepBenchmarkTriRawRunRequest(BaseModel):
    output_root: str = "outputs"
    manifest_path: str | None = None
    run_root: str = "_benchmark_runs/tri_raw"
    benchmark_output_dir: str | None = None
    sample_ids: list[str] = Field(default_factory=list)
    requested_reference_policy: TriRawReferencePolicy = "auto"
    write_measurements: bool = True


class RawPrepBenchmarkTriRawRunIssue(BaseModel):
    sample_id: str | None = None
    bucket_id: str | None = None
    severity: str = "error"
    code: str
    message: str


class RawPrepBenchmarkTriRawRunSample(BaseModel):
    sample_id: str
    bucket_id: str
    source_paths: list[str] = Field(default_factory=list)
    session_root: str
    report_path: str | None = None
    manifest_path: str | None = None
    materialization_status: str = "planned"
    runtime_backend: str | None = None
    requested_reference_policy: TriRawReferencePolicy = "auto"
    selected_reference_index: int | None = None
    selected_reference_raw_path: str | None = None
    selected_reference_preview_path: str | None = None
    recommended_label: str | None = None
    fallback_mode: str | None = None
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    measurement_path: str | None = None
    measurement_status: str = "missing"
    wrote_measurement: bool = False
    summary: str


class RawPrepBenchmarkTriRawRun(BaseModel):
    output_root: str
    manifest_path: str
    run_root: str
    benchmark_output_dir: str | None = None
    benchmark_status: str | None = None
    benchmark_report_status: str | None = None
    requested_reference_policy: TriRawReferencePolicy = "auto"
    manifest_sample_count: int = 0
    requested_sample_count: int = 0
    processed_count: int = 0
    measured_count: int = 0
    success_sample_ids: list[str] = Field(default_factory=list)
    measured_bucket_ids: list[str] = Field(default_factory=list)
    timing_ms_mean: float | None = None
    metric_mean_by_axis: dict[str, float] = Field(default_factory=dict)
    samples: list[RawPrepBenchmarkTriRawRunSample] = Field(default_factory=list)
    issues: list[RawPrepBenchmarkTriRawRunIssue] = Field(default_factory=list)
    summary: str


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
        raise ValueError("Manifest path value is required.")
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


def _resolve_manifest_path(path_value: str | None) -> Path:
    if path_value:
        raw = Path(path_value)
        return raw.resolve() if raw.is_absolute() else (repo_root() / raw).resolve()
    return _tri_raw_manifest_path().resolve()


def _resolve_run_root(path_value: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root).resolve()
    candidate = Path(path_value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("TriRaw benchmark run_root must stay inside the configured output root.") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _issue(
    *,
    sample_id: str | None,
    bucket_id: str | None,
    code: str,
    message: str,
) -> RawPrepBenchmarkTriRawRunIssue:
    return RawPrepBenchmarkTriRawRunIssue(
        sample_id=sample_id,
        bucket_id=bucket_id,
        code=code,
        message=message,
    )


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _metric_value(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    return None


def _derive_tri_raw_metrics(runtime_result: TriRawPreviewRuntimeResult) -> dict[str, float]:
    metrics: dict[str, float] = {}

    hdr_summary = runtime_result.hdr_summary if isinstance(runtime_result.hdr_summary, dict) else {}
    joint_denoise_summary = (
        runtime_result.joint_denoise_summary if isinstance(runtime_result.joint_denoise_summary, dict) else {}
    )
    confidence_summary = (
        runtime_result.confidence_summary if isinstance(runtime_result.confidence_summary, dict) else {}
    )
    alignment_guard_summary = (
        runtime_result.alignment_guard_summary if isinstance(runtime_result.alignment_guard_summary, dict) else {}
    )
    frontier_eval = runtime_result.frontier_eval if isinstance(runtime_result.frontier_eval, dict) else {}
    frontier_axis_scores = frontier_eval.get("axis_scores") if isinstance(frontier_eval.get("axis_scores"), dict) else {}

    metric_pairs = (
        ("frontier_total_score", _metric_value(frontier_eval, "total_score")),
        ("frontier_score_delta_vs_baseline", _metric_value(frontier_eval, "score_delta_vs_baseline")),
        ("frontier_alignment_confidence", _metric_value(frontier_axis_scores, "alignment_confidence")),
        ("frontier_ghost_control", _metric_value(frontier_axis_scores, "ghost_control")),
        ("frontier_denoise_detail_tradeoff", _metric_value(frontier_axis_scores, "denoise_detail_tradeoff")),
        ("frontier_hdr_recovery", _metric_value(frontier_axis_scores, "hdr_recovery")),
        ("frontier_fallback_safety", _metric_value(frontier_axis_scores, "fallback_safety")),
        ("hdr_gain_coverage", _metric_value(hdr_summary, "hdr_gain_coverage")),
        ("highlight_recovery_coverage", _metric_value(hdr_summary, "highlight_recovery_coverage")),
        ("shadow_lift_coverage", _metric_value(hdr_summary, "shadow_lift_coverage")),
        ("ev_span", _metric_value(hdr_summary, "ev_span")),
        ("noise_suppression_mean", _metric_value(joint_denoise_summary, "mean_suppression")),
        ("strong_suppression_coverage", _metric_value(joint_denoise_summary, "strong_suppression_coverage")),
        ("mean_confidence", _metric_value(confidence_summary, "mean_confidence")),
        ("ghost_risk_coverage", _metric_value(confidence_summary, "ghost_risk_coverage")),
        ("reference_holdout_coverage", _metric_value(confidence_summary, "reference_holdout_coverage")),
        ("alignment_pressure_score", _metric_value(alignment_guard_summary, "pressure_score")),
    )
    for key, value in metric_pairs:
        if value is not None:
            metrics[key] = value
    return metrics


def _derive_fallback_mode(runtime_result: TriRawPreviewRuntimeResult) -> str | None:
    fallback_strategy = runtime_result.fallback_strategy if isinstance(runtime_result.fallback_strategy, dict) else {}
    for key in ("selected_action", "selected_reason"):
        value = fallback_strategy.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if isinstance(runtime_result.fallback_reason, str) and runtime_result.fallback_reason.strip():
        return runtime_result.fallback_reason.strip()
    return None


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_tri_raw_runtime_report(
    *,
    report_path: Path,
    runtime_result: TriRawPreviewRuntimeResult,
    requested_reference_policy: TriRawReferencePolicy,
    timing_ms: float,
) -> None:
    payload = _read_json_object(report_path)
    payload.update(
        {
            "status": "preview_fused",
            "runtime_backend": runtime_result.backend,
            "baseline_backend": runtime_result.baseline_backend,
            "frontier_contract": runtime_result.frontier_contract,
            "merge_backend": runtime_result.baseline_backend,
            "requested_reference_policy": requested_reference_policy,
            "selected_single_raw": runtime_result.selected_reference_raw_path,
            "selected_single_index": runtime_result.selected_reference_index,
            "selected_single_preview_path": runtime_result.selected_reference_preview_path,
            "recommended_artifact": runtime_result.recommended_artifact_path,
            "merged_hdr_path": runtime_result.merged_hdr_path,
            "denoised_result_path": runtime_result.denoised_result_path,
            "recommended_label": runtime_result.recommended_label,
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
            "timing_report": {
                "runner_total_ms": round(timing_ms, 3),
            },
            "timing_summary": f"TriRaw preview runtime runner total: {round(timing_ms, 3)}ms",
        }
    )
    payload["notes"] = [
        *(payload.get("notes") if isinstance(payload.get("notes"), list) else []),
        *runtime_result.notes,
        "Derived from official TriRaw benchmark runner materialization.",
    ]
    _write_json(report_path, payload)


def run_rawprep_benchmark_tri_raw_samples(
    request: RawPrepBenchmarkTriRawRunRequest,
) -> RawPrepBenchmarkTriRawRun:
    manifest_path = _resolve_manifest_path(request.manifest_path)
    payload = _load_optional_manifest(manifest_path)
    if payload is None:
        raise FileNotFoundError(f"TriRaw benchmark manifest was not found: {manifest_path}")

    manifest_entries = [entry for entry in _sample_entries(payload) if str(entry.get("sample_id") or "").strip()]
    requested_sample_ids = {sample_id.strip() for sample_id in request.sample_ids if sample_id.strip()}
    selected_entries = [
        entry
        for entry in manifest_entries
        if not requested_sample_ids or str(entry.get("sample_id") or "").strip() in requested_sample_ids
    ]
    run_root = _resolve_run_root(request.run_root, output_root=request.output_root)

    samples: list[RawPrepBenchmarkTriRawRunSample] = []
    issues: list[RawPrepBenchmarkTriRawRunIssue] = []
    success_sample_ids: list[str] = []
    timing_values: list[float] = []
    metric_values: dict[str, list[float]] = {}
    measured_bucket_ids: set[str] = set()

    for entry in selected_entries:
        sample_id = str(entry.get("sample_id") or "").strip()
        bucket_id = str(entry.get("bucket_id") or "").strip()
        source_values = entry.get("source_paths")
        if not isinstance(source_values, list) or len(source_values) not in {3, 9}:
            issues.append(
                _issue(
                    sample_id=sample_id or None,
                    bucket_id=bucket_id or None,
                    code="tri_raw_manifest_invalid_source_paths",
                    message="Official TriRaw manifest entry must declare exactly three or nine source_paths.",
                )
            )
            continue

        try:
            source_paths = [
                _resolve_repo_or_output_path(str(path_value), output_root=request.output_root)
                for path_value in source_values
            ]
        except ValueError as exc:
            issues.append(
                _issue(
                    sample_id=sample_id,
                    bucket_id=bucket_id or None,
                    code="tri_raw_manifest_source_path_invalid",
                    message=str(exc),
                )
            )
            continue

        missing_sources = [path for path in source_paths if not path.exists() or not path.is_file()]
        if missing_sources:
            issues.append(
                _issue(
                    sample_id=sample_id,
                    bucket_id=bucket_id or None,
                    code="tri_raw_source_missing",
                    message=f"Official TriRaw sample source was not found: {missing_sources[0]}",
                )
            )
            continue

        session_root = run_root / request.requested_reference_policy / sample_id
        session_root.mkdir(parents=True, exist_ok=True)

        started_at = perf_counter()
        plan = build_tri_raw_foundation_plan(
            [str(path) for path in source_paths],
            bracket_id=sample_id,
            session_root=session_root,
        )
        plan = materialize_tri_raw_foundation_plan(plan)
        runtime_result = materialize_tri_raw_preview_runtime(
            plan,
            requested_reference_policy=request.requested_reference_policy,
        )
        timing_ms = round((perf_counter() - started_at) * 1000.0, 3)

        if runtime_result is None:
            issues.append(
                _issue(
                    sample_id=sample_id,
                    bucket_id=bucket_id or None,
                    code="tri_raw_runtime_unavailable",
                    message="TriRaw preview runtime could not resolve preview proxies for this bracket sample.",
                )
            )
            samples.append(
                RawPrepBenchmarkTriRawRunSample(
                    sample_id=sample_id,
                    bucket_id=bucket_id,
                    source_paths=[_repo_relative_string(path) for path in source_paths],
                    session_root=_repo_relative_string(session_root),
                    report_path=_repo_relative_string(Path(plan.report_path)),
                    manifest_path=_repo_relative_string(Path(plan.diagnostics_manifest_path)),
                    materialization_status=plan.materialization_status,
                    requested_reference_policy=request.requested_reference_policy,
                    timing_ms=timing_ms,
                    summary="TriRaw foundation plan was written, but preview runtime could not materialize benchmark artifacts.",
                )
            )
            continue

        _write_tri_raw_runtime_report(
            report_path=Path(plan.report_path),
            runtime_result=runtime_result,
            requested_reference_policy=request.requested_reference_policy,
            timing_ms=timing_ms,
        )

        metrics = _derive_tri_raw_metrics(runtime_result)
        fallback_mode = _derive_fallback_mode(runtime_result)

        sample_record = RawPrepBenchmarkTriRawRunSample(
            sample_id=sample_id,
            bucket_id=bucket_id,
            source_paths=[_repo_relative_string(path) for path in source_paths],
            session_root=_repo_relative_string(session_root),
            report_path=_repo_relative_string(Path(plan.report_path)),
            manifest_path=_repo_relative_string(Path(plan.diagnostics_manifest_path)),
            materialization_status="preview_fused",
            runtime_backend=runtime_result.backend,
            requested_reference_policy=request.requested_reference_policy,
            selected_reference_index=runtime_result.selected_reference_index,
            selected_reference_raw_path=_repo_relative_string(Path(runtime_result.selected_reference_raw_path)),
            selected_reference_preview_path=_repo_relative_string(Path(runtime_result.selected_reference_preview_path)),
            recommended_label=runtime_result.recommended_label,
            fallback_mode=fallback_mode,
            timing_ms=timing_ms,
            metrics=metrics,
            summary="TriRaw benchmark sample materialized successfully.",
        )

        success_sample_ids.append(sample_id)
        timing_values.append(timing_ms)
        for axis, value in metrics.items():
            metric_values.setdefault(axis, []).append(float(value))

        if request.write_measurements:
            measurement = write_rawprep_benchmark_measurement(
                RawPrepBenchmarkMeasurementWriteRequest(
                    sample_id=sample_id,
                    output_root=request.output_root,
                    timing_ms=timing_ms,
                    metrics=metrics,
                    fallback_mode=fallback_mode,
                    notes=[
                        "Derived from local TriRaw benchmark sample library materialization.",
                        f"Requested reference policy: {request.requested_reference_policy}",
                        f"Runtime backend: {runtime_result.backend}",
                        f"Recommended label: {runtime_result.recommended_label}",
                    ],
                )
            )
            sample_record.measurement_path = measurement.measurement_path
            sample_record.measurement_status = measurement.measurement_status
            sample_record.wrote_measurement = measurement.wrote_measurement
            if measurement.measurement_status == "measured":
                measured_bucket_ids.add(bucket_id)

        samples.append(sample_record)

    benchmark_status: str | None = None
    benchmark_report_status: str | None = None
    if request.benchmark_output_dir:
        benchmark_record = run_rawprep_benchmark(
            RawPrepBenchmarkRequest(
                output_dir=request.benchmark_output_dir,
                output_root=request.output_root,
                label=f"tri_raw_{request.requested_reference_policy}",
            )
        )
        benchmark_status = benchmark_record.status
        benchmark_report_status = benchmark_record.report_status

    measured_count = sum(1 for sample in samples if sample.measurement_status == "measured")
    if issues:
        summary = "TriRaw benchmark sample run completed with some skipped or failed samples."
    elif measured_count and measured_count == len(samples):
        summary = "TriRaw benchmark sample run completed and wrote measured evidence for every selected sample."
    elif samples:
        summary = "TriRaw benchmark sample run completed, but some selected samples still lack measured evidence."
    else:
        summary = "TriRaw benchmark sample run did not process any manifest entries."

    return RawPrepBenchmarkTriRawRun(
        output_root=request.output_root,
        manifest_path=str(manifest_path),
        run_root=str(run_root),
        benchmark_output_dir=request.benchmark_output_dir,
        benchmark_status=benchmark_status,
        benchmark_report_status=benchmark_report_status,
        requested_reference_policy=request.requested_reference_policy,
        manifest_sample_count=len(manifest_entries),
        requested_sample_count=len(selected_entries),
        processed_count=len(samples),
        measured_count=measured_count,
        success_sample_ids=success_sample_ids,
        measured_bucket_ids=sorted(bucket_id for bucket_id in measured_bucket_ids if bucket_id),
        timing_ms_mean=_mean(timing_values),
        metric_mean_by_axis={
            axis: mean_value
            for axis, values in metric_values.items()
            for mean_value in [_mean(values)]
            if mean_value is not None
        },
        samples=samples,
        issues=issues,
        summary=summary,
    )
