from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.raw_engine_v2.single_raw.planner import (
    SingleRawModePreference,
    build_single_raw_foundation_plan,
    materialize_single_raw_foundation_plan,
)

from .rawprep_benchmark_measurement import (
    write_rawprep_benchmark_measurement_from_single_raw_report,
    RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
)
from .rawprep_benchmark_service import (
    RawPrepBenchmarkRequest,
    _load_optional_manifest,
    _sample_entries,
    _single_raw_manifest_path,
    run_rawprep_benchmark,
)
from .studio_paths import repo_root, resolve_output_root


SingleRawQualityPreset = Literal["balanced", "safe"]
PREVIEW_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")


class RawPrepBenchmarkSingleRawRunRequest(BaseModel):
    output_root: str = "outputs"
    manifest_path: str | None = None
    run_root: str = "_benchmark_runs/single_raw"
    benchmark_output_dir: str | None = None
    sample_ids: list[str] = Field(default_factory=list)
    quality_preset: SingleRawQualityPreset = "balanced"
    mode_preference: SingleRawModePreference = "fast"
    write_measurements: bool = True


class RawPrepBenchmarkSingleRawRunIssue(BaseModel):
    sample_id: str | None = None
    severity: str = "error"
    code: str
    message: str


class RawPrepBenchmarkSingleRawRunSample(BaseModel):
    sample_id: str
    raw_path: str
    preview_source_path: str | None = None
    session_root: str
    report_path: str | None = None
    manifest_path: str | None = None
    materialization_status: str = "planned"
    resolved_mode: str | None = None
    runtime_profile: str | None = None
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    measurement_path: str | None = None
    measurement_status: str = "missing"
    wrote_measurement: bool = False
    summary: str


class RawPrepBenchmarkSingleRawRun(BaseModel):
    output_root: str
    manifest_path: str
    run_root: str
    benchmark_output_dir: str | None = None
    benchmark_status: str | None = None
    benchmark_report_status: str | None = None
    quality_preset: SingleRawQualityPreset = "balanced"
    mode_preference: SingleRawModePreference = "fast"
    manifest_sample_count: int = 0
    requested_sample_count: int = 0
    processed_count: int = 0
    measured_count: int = 0
    missing_preview_sample_ids: list[str] = Field(default_factory=list)
    success_sample_ids: list[str] = Field(default_factory=list)
    timing_ms_mean: float | None = None
    metric_mean_by_axis: dict[str, float] = Field(default_factory=dict)
    samples: list[RawPrepBenchmarkSingleRawRunSample] = Field(default_factory=list)
    issues: list[RawPrepBenchmarkSingleRawRunIssue] = Field(default_factory=list)
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
    return _single_raw_manifest_path().resolve()


def _resolve_run_root(path_value: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root).resolve()
    candidate = Path(path_value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("SingleRaw benchmark run_root must stay inside the configured output root.") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _find_preview_source(raw_path: Path) -> Path | None:
    parent = raw_path.parent
    stem_lower = raw_path.stem.lower()
    for entry in sorted(parent.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in PREVIEW_EXTENSIONS:
            continue
        if entry.stem.lower() == stem_lower:
            return entry.resolve()
    return None


def _issue(*, sample_id: str | None, code: str, message: str) -> RawPrepBenchmarkSingleRawRunIssue:
    return RawPrepBenchmarkSingleRawRunIssue(sample_id=sample_id, code=code, message=message)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def run_rawprep_benchmark_single_raw_samples(
    request: RawPrepBenchmarkSingleRawRunRequest,
) -> RawPrepBenchmarkSingleRawRun:
    manifest_path = _resolve_manifest_path(request.manifest_path)
    payload = _load_optional_manifest(manifest_path)
    if payload is None:
        raise FileNotFoundError(f"SingleRaw benchmark manifest was not found: {manifest_path}")

    manifest_entries = [entry for entry in _sample_entries(payload) if str(entry.get("sample_id") or "").strip()]
    requested_sample_ids = {sample_id.strip() for sample_id in request.sample_ids if sample_id.strip()}
    selected_entries = [
        entry
        for entry in manifest_entries
        if not requested_sample_ids or str(entry.get("sample_id") or "").strip() in requested_sample_ids
    ]
    run_root = _resolve_run_root(request.run_root, output_root=request.output_root)

    samples: list[RawPrepBenchmarkSingleRawRunSample] = []
    issues: list[RawPrepBenchmarkSingleRawRunIssue] = []
    success_sample_ids: list[str] = []
    missing_preview_sample_ids: list[str] = []
    timing_values: list[float] = []
    metric_values: dict[str, list[float]] = {}

    for entry in selected_entries:
        sample_id = str(entry.get("sample_id") or "").strip()
        raw_path_value = str(entry.get("raw_path") or "").strip()
        if not raw_path_value:
            issues.append(
                _issue(
                    sample_id=sample_id or None,
                    code="single_raw_manifest_missing_raw_path",
                    message="Official SingleRaw manifest entry is missing raw_path.",
                )
            )
            continue
        try:
            raw_path = _resolve_repo_or_output_path(raw_path_value, output_root=request.output_root)
        except ValueError as exc:
            issues.append(_issue(sample_id=sample_id, code="single_raw_manifest_raw_path_invalid", message=str(exc)))
            continue
        if not raw_path.exists() or not raw_path.is_file():
            issues.append(
                _issue(
                    sample_id=sample_id,
                    code="single_raw_source_missing",
                    message=f"Official SingleRaw sample source was not found: {raw_path}",
                )
            )
            continue

        preview_source = _find_preview_source(raw_path)
        if preview_source is None:
            missing_preview_sample_ids.append(sample_id)

        session_root = run_root / request.mode_preference / sample_id
        session_root.mkdir(parents=True, exist_ok=True)

        plan = build_single_raw_foundation_plan(
            str(raw_path),
            session_root=session_root,
            quality_preset=request.quality_preset,
            mode_preference=request.mode_preference,
        )
        plan = materialize_single_raw_foundation_plan(
            plan,
            source_preview_path=str(preview_source) if preview_source is not None else None,
        )

        timing_report = plan.decode.get("timing_report") if isinstance(plan.decode, dict) else None
        timing_ms = None
        if isinstance(timing_report, dict):
            planner_total_ms = timing_report.get("planner_total_ms")
            total_ms = timing_report.get("total_ms")
            if isinstance(planner_total_ms, (int, float)):
                timing_ms = round(float(planner_total_ms), 3)
            elif isinstance(total_ms, (int, float)):
                timing_ms = round(float(total_ms), 3)

        sample_record = RawPrepBenchmarkSingleRawRunSample(
            sample_id=sample_id,
            raw_path=_repo_relative_string(raw_path),
            preview_source_path=_repo_relative_string(preview_source) if preview_source is not None else None,
            session_root=_repo_relative_string(session_root),
            report_path=_repo_relative_string(Path(plan.report_path)) if plan.report_path else None,
            manifest_path=_repo_relative_string(Path(plan.manifest_path)) if plan.manifest_path else None,
            materialization_status=plan.materialization_status,
            resolved_mode=plan.resolved_mode,
            runtime_profile=str(plan.decode.get("runtime_profile") or "") if isinstance(plan.decode, dict) else None,
            timing_ms=timing_ms,
            summary=(
                "SingleRaw benchmark sample materialized successfully."
                if plan.materialization_status != "planned"
                else "SingleRaw benchmark sample stayed in planned status because neither sensor decode nor preview bootstrap could materialize artifacts."
            ),
        )

        if request.write_measurements and sample_record.report_path and plan.materialization_status != "planned":
            try:
                measurement = write_rawprep_benchmark_measurement_from_single_raw_report(
                    RawPrepBenchmarkMeasurementFromSingleRawReportRequest(
                        sample_id=sample_id,
                        report_path=sample_record.report_path,
                        output_root=request.output_root,
                        notes=[
                            "Derived from local benchmark sample library materialization.",
                            f"Mode preference: {request.mode_preference}",
                        ],
                    )
                )
            except (FileNotFoundError, ValueError) as exc:
                issues.append(_issue(sample_id=sample_id, code="single_raw_measurement_write_failed", message=str(exc)))
            else:
                sample_record.measurement_path = measurement.measurement_path
                sample_record.measurement_status = measurement.measurement_status
                sample_record.wrote_measurement = measurement.wrote_measurement
                sample_record.metrics = measurement.metrics
                if measurement.timing_ms is not None:
                    sample_record.timing_ms = round(float(measurement.timing_ms), 3)
                success_sample_ids.append(sample_id)
                if sample_record.timing_ms is not None:
                    timing_values.append(float(sample_record.timing_ms))
                for axis, value in measurement.metrics.items():
                    metric_values.setdefault(axis, []).append(float(value))

        samples.append(sample_record)

    benchmark_status: str | None = None
    benchmark_report_status: str | None = None
    if request.benchmark_output_dir:
        benchmark_record = run_rawprep_benchmark(
            RawPrepBenchmarkRequest(
                output_dir=request.benchmark_output_dir,
                output_root=request.output_root,
                label=f"single_raw_{request.mode_preference}",
            )
        )
        benchmark_status = benchmark_record.status
        benchmark_report_status = benchmark_record.report_status

    measured_count = sum(1 for sample in samples if sample.measurement_status == "measured")
    if issues:
        summary = "SingleRaw benchmark sample run completed with some skipped or failed samples."
    elif measured_count and measured_count == len(samples):
        summary = "SingleRaw benchmark sample run completed and wrote measured evidence for every selected sample."
    elif samples:
        summary = "SingleRaw benchmark sample run completed, but some selected samples still lack measured evidence."
    else:
        summary = "SingleRaw benchmark sample run did not process any manifest entries."

    return RawPrepBenchmarkSingleRawRun(
        output_root=request.output_root,
        manifest_path=str(manifest_path),
        run_root=str(run_root),
        benchmark_output_dir=request.benchmark_output_dir,
        benchmark_status=benchmark_status,
        benchmark_report_status=benchmark_report_status,
        quality_preset=request.quality_preset,
        mode_preference=request.mode_preference,
        manifest_sample_count=len(manifest_entries),
        requested_sample_count=len(selected_entries),
        processed_count=len(samples),
        measured_count=measured_count,
        missing_preview_sample_ids=missing_preview_sample_ids,
        success_sample_ids=success_sample_ids,
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
