from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .rawprep_benchmark_service import (
    BenchmarkMeasurement,
    _load_measurement,
    _load_optional_manifest,
    _resolve_manifest_relative_path,
    _sample_entries,
    _single_raw_manifest_path,
    _tri_raw_manifest_path,
    build_rawprep_benchmark_foundation_health,
)


class RawPrepBenchmarkMeasurementRequest(BaseModel):
    sample_id: str
    output_root: str = "outputs"


class RawPrepBenchmarkMeasurementWriteRequest(RawPrepBenchmarkMeasurementRequest):
    status: Literal["pending_measurement", "measured"] = "measured"
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    fallback_mode: str | None = None
    notes: list[str] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementFromSingleRawReportRequest(RawPrepBenchmarkMeasurementRequest):
    report_path: str
    status: Literal["pending_measurement", "measured"] = "measured"
    notes: list[str] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementRecord(BaseModel):
    sample_id: str
    output_root: str
    scope: Literal["single_raw", "tri_raw"]
    bucket_id: str | None = None
    manifest_path: str
    measurement_path: str
    measurement_exists: bool = False
    measurement_status: str = "missing"
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    fallback_mode: str | None = None
    notes: list[str] = Field(default_factory=list)
    wrote_measurement: bool = False
    foundation_status: str = "missing"
    summary: str


class _ResolvedBenchmarkMeasurementTarget(BaseModel):
    sample_id: str
    scope: Literal["single_raw", "tri_raw"]
    bucket_id: str | None = None
    manifest_path: str
    manifest_entry: dict
    measurement_path: str
    resolved_measurement_path: str


def _resolve_existing_repo_or_output_path(path_value: str, *, output_root: str) -> Path:
    normalized = path_value.strip()
    if not normalized:
        raise ValueError("report_path is required.")
    resolved = _resolve_manifest_relative_path(normalized, output_root=output_root)
    if resolved is None:
        raise ValueError("report_path must stay inside the repository or output root.")
    if not resolved.exists():
        raise FileNotFoundError(f"SingleRaw report was not found: {resolved}")
    return resolved


def _load_single_raw_report_payload(report_path: str, *, output_root: str) -> tuple[Path, dict]:
    resolved = _resolve_existing_repo_or_output_path(report_path, output_root=output_root)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SingleRaw report must be a JSON object.")
    return resolved, payload


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clamp_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(1.0, float(value))), 4)


def _first_mapping(*values: object) -> dict[str, object]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _derive_single_raw_report_metrics(payload: dict[str, object]) -> dict[str, float]:
    decode = payload.get("decode")
    decode_payload = decode if isinstance(decode, dict) else {}
    noise_report = _first_mapping(payload.get("noise_report"), decode_payload.get("noise_report"))
    artifact_suppression = _first_mapping(
        payload.get("artifact_suppression"),
        decode_payload.get("artifact_suppression"),
    )
    recovery_report = _first_mapping(payload.get("recovery_report"), decode_payload.get("recovery_report"))

    metrics: dict[str, float] = {}

    noise_reduction = _clamp_ratio(_coerce_float(noise_report.get("suppression_ratio")))
    if noise_reduction is not None:
        metrics["noise_reduction"] = noise_reduction

    detail_components: list[float] = []
    texture_suppression = _clamp_ratio(_coerce_float(artifact_suppression.get("texture_suppression_ratio")))
    if texture_suppression is not None:
        detail_components.append(round(1.0 - texture_suppression, 4))
    lowlight_detail_gain = _clamp_ratio(_coerce_float(recovery_report.get("lowlight_detail_gain_ratio")))
    if lowlight_detail_gain is not None:
        detail_components.append(lowlight_detail_gain)
    if detail_components:
        metrics["detail_preservation"] = round(sum(detail_components) / len(detail_components), 4)

    color_stability = _clamp_ratio(_coerce_float(artifact_suppression.get("saturation_suppression_ratio")))
    if color_stability is not None:
        metrics["color_stability"] = round(1.0 - color_stability, 4)

    return metrics


def _derive_single_raw_report_fallback_mode(payload: dict[str, object]) -> str | None:
    decode = payload.get("decode")
    decode_payload = decode if isinstance(decode, dict) else {}
    fallback_decision = _first_mapping(payload.get("fallback_decision"), decode_payload.get("fallback_decision"))
    for key in ("reason_key", "selected_variant"):
        value = fallback_decision.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _derive_measurement_from_single_raw_report(
    request: RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
) -> RawPrepBenchmarkMeasurementWriteRequest:
    resolved_report_path, payload = _load_single_raw_report_payload(request.report_path, output_root=request.output_root)
    decode_payload = payload.get("decode")
    decode = decode_payload if isinstance(decode_payload, dict) else {}
    timing_payload = payload.get("timing_report")
    timing_report = timing_payload if isinstance(timing_payload, dict) else {}
    if not timing_report and isinstance(decode.get("timing_report"), dict):
        timing_report = dict(decode["timing_report"])

    planner_total_ms = _coerce_float(timing_report.get("planner_total_ms"))
    total_ms = _coerce_float(timing_report.get("total_ms"))
    timing_ms = planner_total_ms if planner_total_ms is not None else total_ms
    if timing_ms is None:
        raise ValueError("SingleRaw report does not contain timing_report.planner_total_ms or timing_report.total_ms.")

    timing_summary = str(payload.get("timing_summary") or timing_report.get("summary") or "").strip()
    resolved_mode = str(payload.get("resolved_mode") or decode.get("runtime_execution_mode") or "").strip()
    runtime_profile = str(payload.get("runtime_profile") or decode.get("runtime_profile") or "").strip()
    materialization_status = str(payload.get("status") or payload.get("materialization_status") or "").strip()

    derived_notes = [f"Derived from SingleRaw report: {resolved_report_path}"]
    if timing_summary:
        derived_notes.append(timing_summary)
    if resolved_mode:
        derived_notes.append(f"Resolved mode: {resolved_mode}")
    if runtime_profile:
        derived_notes.append(f"Runtime profile: {runtime_profile}")
    if materialization_status:
        derived_notes.append(f"Materialization status: {materialization_status}")
    derived_notes.extend(str(note) for note in request.notes if isinstance(note, str) and note.strip())
    derived_metrics = _derive_single_raw_report_metrics(payload)
    fallback_mode = _derive_single_raw_report_fallback_mode(payload)

    return RawPrepBenchmarkMeasurementWriteRequest(
        sample_id=request.sample_id,
        output_root=request.output_root,
        status=request.status,
        timing_ms=round(timing_ms, 3),
        metrics=derived_metrics,
        fallback_mode=fallback_mode,
        notes=derived_notes,
    )


def _resolve_measurement_target(sample_id: str, *, output_root: str) -> _ResolvedBenchmarkMeasurementTarget:
    normalized_sample_id = sample_id.strip()
    if not normalized_sample_id:
        raise ValueError("sample_id is required.")

    matches: list[_ResolvedBenchmarkMeasurementTarget] = []
    for scope, manifest_path in (
        ("single_raw", _single_raw_manifest_path()),
        ("tri_raw", _tri_raw_manifest_path()),
    ):
        payload = _load_optional_manifest(manifest_path)
        for entry in _sample_entries(payload):
            if str(entry.get("sample_id") or "").strip() != normalized_sample_id:
                continue
            measurement_path = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "").strip()
            if not measurement_path:
                raise ValueError(
                    f"Official manifest entry for sample '{normalized_sample_id}' does not declare benchmark_result_path yet."
                )
            resolved_path = _resolve_manifest_relative_path(measurement_path, output_root=output_root)
            if resolved_path is None:
                raise ValueError(
                    f"benchmark_result_path for sample '{normalized_sample_id}' must stay inside the repository or output root."
                )
            matches.append(
                _ResolvedBenchmarkMeasurementTarget(
                    sample_id=normalized_sample_id,
                    scope=scope,
                    bucket_id=str(entry.get("bucket_id") or "").strip() or None,
                    manifest_path=str(manifest_path),
                    manifest_entry=dict(entry),
                    measurement_path=measurement_path,
                    resolved_measurement_path=str(resolved_path),
                )
            )

    if not matches:
        raise FileNotFoundError(
            f"Official benchmark manifest entry was not found for sample '{normalized_sample_id}'. Populate the manifest first."
        )
    if len(matches) > 1:
        scopes = ", ".join(match.scope for match in matches)
        raise ValueError(
            f"Sample '{normalized_sample_id}' appears in multiple official manifests ({scopes}). Resolve the duplicate before writing measurement evidence."
        )
    return matches[0]


def build_rawprep_benchmark_measurement(sample_id: str, *, output_root: str = "outputs") -> RawPrepBenchmarkMeasurementRecord:
    target = _resolve_measurement_target(sample_id, output_root=output_root)
    measurement = _load_measurement(target.measurement_path, output_root=output_root)
    foundation_status = build_rawprep_benchmark_foundation_health(output_root=output_root).status

    if measurement is None:
        summary = "Official manifest entry exists, but measured benchmark evidence has not been written yet."
        return RawPrepBenchmarkMeasurementRecord(
            sample_id=target.sample_id,
            output_root=output_root,
            scope=target.scope,
            bucket_id=target.bucket_id,
            manifest_path=target.manifest_path,
            measurement_path=target.measurement_path,
            measurement_exists=False,
            measurement_status="missing",
            foundation_status=foundation_status,
            summary=summary,
        )

    summary = "Official benchmark measurement evidence is present for this sample."
    return RawPrepBenchmarkMeasurementRecord(
        sample_id=target.sample_id,
        output_root=output_root,
        scope=target.scope,
        bucket_id=target.bucket_id,
        manifest_path=target.manifest_path,
        measurement_path=target.measurement_path,
        measurement_exists=True,
        measurement_status=measurement.status,
        timing_ms=measurement.timing_ms,
        metrics=measurement.metrics,
        fallback_mode=measurement.fallback_mode,
        notes=measurement.notes,
        foundation_status=foundation_status,
        summary=summary,
    )


def write_rawprep_benchmark_measurement(
    request: RawPrepBenchmarkMeasurementWriteRequest,
) -> RawPrepBenchmarkMeasurementRecord:
    target = _resolve_measurement_target(request.sample_id, output_root=request.output_root)
    resolved_path = Path(target.resolved_measurement_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    payload = BenchmarkMeasurement(
        sample_id=target.sample_id,
        status=request.status,
        timing_ms=request.timing_ms,
        metrics={
            str(key): float(value)
            for key, value in request.metrics.items()
            if isinstance(key, str) and isinstance(value, (int, float))
        },
        fallback_mode=request.fallback_mode,
        notes=[str(note) for note in request.notes],
    )
    resolved_path.write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    record = build_rawprep_benchmark_measurement(request.sample_id, output_root=request.output_root)
    record.wrote_measurement = True
    record.summary = "Official benchmark measurement evidence was written to the manifest-declared benchmark_result_path."
    return record


def write_rawprep_benchmark_measurement_from_single_raw_report(
    request: RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
) -> RawPrepBenchmarkMeasurementRecord:
    write_request = _derive_measurement_from_single_raw_report(request)
    record = write_rawprep_benchmark_measurement(write_request)
    record.summary = "Official benchmark measurement evidence was derived from a SingleRaw report timing artifact."
    return record
