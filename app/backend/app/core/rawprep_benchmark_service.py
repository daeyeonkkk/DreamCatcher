from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_compare_memory import collect_compare_decisions
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    label: str | None = None


class RawPrepBenchmarkBucket(BaseModel):
    bucket_id: str
    label: str
    status: str = "defined"
    sample_count: int = 0
    hard_case: bool = False
    traits: list[str] = Field(default_factory=list)
    required_report_sections: list[str] = Field(default_factory=list)


class RawPrepBenchmarkRecord(BaseModel):
    output_dir: str
    output_root: str
    label: str | None = None
    status: str = "foundation_ready"
    summary: str
    catalog_version: str
    catalog_path: str
    specification_path: str
    single_raw_gold_set_defined: bool = False
    single_raw_gold_set_status: str = "undefined"
    single_raw_sample_count: int = 0
    single_raw_measured_sample_count: int = 0
    single_raw_missing_measurement_sample_ids: list[str] = Field(default_factory=list)
    single_raw_metric_mean_by_axis: dict[str, float] = Field(default_factory=dict)
    single_raw_metric_coverage_by_axis: dict[str, int] = Field(default_factory=dict)
    single_raw_timing_ms_mean: float | None = None
    single_raw_evaluation_axes: list[str] = Field(default_factory=list)
    single_raw_manifest_path: str | None = None
    single_raw_manifest_exists: bool = False
    single_raw_manifest_status: str = "missing"
    tri_raw_buckets: list[RawPrepBenchmarkBucket] = Field(default_factory=list)
    hard_case_bucket_defined: bool = False
    hard_case_member_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_manifest_path: str | None = None
    tri_raw_manifest_exists: bool = False
    tri_raw_manifest_status: str = "missing"
    tri_raw_populated_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_missing_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_measured_sample_count: int = 0
    tri_raw_measured_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_missing_measurement_sample_ids: list[str] = Field(default_factory=list)
    tri_raw_measured_counts_by_bucket: dict[str, int] = Field(default_factory=dict)
    tri_raw_metric_mean_by_axis: dict[str, float] = Field(default_factory=dict)
    tri_raw_metric_coverage_by_axis: dict[str, int] = Field(default_factory=dict)
    tri_raw_metric_mean_by_bucket: dict[str, dict[str, float]] = Field(default_factory=dict)
    tri_raw_timing_ms_mean: float | None = None
    tri_raw_timing_ms_mean_by_bucket: dict[str, float] = Field(default_factory=dict)
    tri_raw_fallback_mode_counts: dict[str, int] = Field(default_factory=dict)
    report_template_documented: bool = False
    report_sections: list[str] = Field(default_factory=list)
    compare_decision_logging_defined: bool = False
    compare_decision_storage: list[str] = Field(default_factory=list)
    compare_decision_count: int = 0
    compare_decision_summary: dict[str, Any] = Field(default_factory=dict)
    details: list[str] = Field(default_factory=list)
    report_path: str | None = None
    report_status: str = "missing"


class RawPrepBenchmarkReport(BaseModel):
    output_dir: str
    output_root: str
    label: str | None = None
    status: str = "foundation_ready"
    generated_at: str
    catalog_version: str
    record_path: str
    dataset_overview: dict[str, Any] = Field(default_factory=dict)
    single_raw_summary: dict[str, Any] = Field(default_factory=dict)
    tri_raw_summary: dict[str, Any] = Field(default_factory=dict)
    bucket_findings: list[dict[str, Any]] = Field(default_factory=list)
    fallback_behavior: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    open_risks: list[str] = Field(default_factory=list)
    operator_notes: list[str] = Field(default_factory=list)


class BenchmarkMeasurement(BaseModel):
    sample_id: str
    status: str = "measured"
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    fallback_mode: str | None = None
    notes: list[str] = Field(default_factory=list)


class RawPrepBenchmarkFoundationIssue(BaseModel):
    severity: str = "error"
    code: str
    scope: str
    message: str
    sample_id: str | None = None
    bucket_id: str | None = None
    path: str | None = None


class RawPrepBenchmarkFoundationHealth(BaseModel):
    output_root: str
    ok: bool = False
    status: str = "blocked"
    summary: str
    catalog_version: str
    single_raw_manifest_path: str | None = None
    tri_raw_manifest_path: str | None = None
    single_raw_sample_count: int = 0
    single_raw_measured_sample_count: int = 0
    tri_raw_sample_count: int = 0
    tri_raw_measured_sample_count: int = 0
    tri_raw_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_populated_bucket_ids: list[str] = Field(default_factory=list)
    tri_raw_missing_bucket_ids: list[str] = Field(default_factory=list)
    issue_counts: dict[str, int] = Field(default_factory=dict)
    issues: list[RawPrepBenchmarkFoundationIssue] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _benchmark_root() -> Path:
    benchmark_root = repo_root() / "benchmark"
    if benchmark_root.exists():
        return benchmark_root
    return repo_root() / "PROJECT_FOUNDATION"


def _catalog_path() -> Path:
    return _benchmark_root() / "BENCHMARK_CATALOG.json"


def _specification_path() -> Path:
    return _catalog_path()


def _single_raw_manifest_path() -> Path:
    return _benchmark_root() / "SINGLE_RAW_GOLD_SET_MANIFEST.json"


def _tri_raw_manifest_path() -> Path:
    return _benchmark_root() / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json"


def load_benchmark_catalog() -> dict:
    path = _catalog_path()
    if not path.exists():
        raise FileNotFoundError(f"Benchmark catalog was not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark catalog must be a JSON object.")
    return payload


def _load_optional_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark manifest must be a JSON object: {path}")
    return payload


def _round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return _round_float(sum(values) / len(values))


def _resolve_manifest_relative_path(path_value: str, *, output_root: str) -> Path | None:
    if not path_value:
        return None

    candidate = Path(path_value)
    resolved = candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    allowed_roots = [repo_root().resolve(), resolve_output_root(output_root).resolve()]
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    return None


def _load_measurement(path_value: str, *, output_root: str) -> BenchmarkMeasurement | None:
    path = _resolve_manifest_relative_path(path_value, output_root=output_root)
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark measurement must be a JSON object: {path}")
    return BenchmarkMeasurement(
        sample_id=str(payload.get("sample_id") or "unknown"),
        status=str(payload.get("status") or "measured"),
        timing_ms=(
            float(payload["timing_ms"])
            if payload.get("timing_ms") is not None
            else None
        ),
        metrics={
            str(key): float(value)
            for key, value in payload.get("metrics", {}).items()
            if isinstance(key, str) and isinstance(value, (int, float))
        },
        fallback_mode=str(payload.get("fallback_mode")) if payload.get("fallback_mode") else None,
        notes=[str(value) for value in payload.get("notes", []) if isinstance(value, str)],
    )


def _sample_entries(payload: dict | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    samples = payload.get("samples", [])
    if not isinstance(samples, list):
        return []
    return [entry for entry in samples if isinstance(entry, dict)]


def _append_foundation_issue(
    issues: list[RawPrepBenchmarkFoundationIssue],
    *,
    severity: str,
    code: str,
    scope: str,
    message: str,
    sample_id: str | None = None,
    bucket_id: str | None = None,
    path: str | None = None,
) -> None:
    issues.append(
        RawPrepBenchmarkFoundationIssue(
            severity=severity,
            code=code,
            scope=scope,
            message=message,
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=path,
        )
    )


def _validate_measurement_reference(
    issues: list[RawPrepBenchmarkFoundationIssue],
    *,
    scope: str,
    sample_id: str,
    output_root: str,
    measurement_path_value: str,
    bucket_id: str | None = None,
) -> None:
    resolved = _resolve_manifest_relative_path(measurement_path_value, output_root=output_root)
    if resolved is None:
        _append_foundation_issue(
            issues,
            severity="error",
            code="measurement_path_outside_root",
            scope=scope,
            message="benchmark_result_path must stay inside the repository or output root.",
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=measurement_path_value,
        )
        return
    if not resolved.exists():
        _append_foundation_issue(
            issues,
            severity="error",
            code="measurement_missing",
            scope=scope,
            message="benchmark_result_path does not exist yet.",
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=str(resolved),
        )
        return
    try:
        measurement = _load_measurement(measurement_path_value, output_root=output_root)
    except (ValueError, json.JSONDecodeError) as exc:
        _append_foundation_issue(
            issues,
            severity="error",
            code="measurement_invalid",
            scope=scope,
            message=str(exc),
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=str(resolved),
        )
        return
    if measurement is None:
        _append_foundation_issue(
            issues,
            severity="error",
            code="measurement_unreadable",
            scope=scope,
            message="benchmark_result_path exists but could not be loaded.",
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=str(resolved),
        )
        return
    if measurement.sample_id != sample_id:
        _append_foundation_issue(
            issues,
            severity="error",
            code="measurement_sample_id_mismatch",
            scope=scope,
            message=f"Measurement sample_id '{measurement.sample_id}' does not match manifest sample_id '{sample_id}'.",
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=str(resolved),
        )
    if measurement.status != "measured":
        _append_foundation_issue(
            issues,
            severity="warning",
            code="measurement_status_not_measured",
            scope=scope,
            message=f"Measurement JSON status is '{measurement.status}', so it should not be treated as final measured evidence yet.",
            sample_id=sample_id,
            bucket_id=bucket_id,
            path=str(resolved),
        )


def _single_raw_manifest_stats(*, output_root: str) -> dict[str, Any]:
    path = _single_raw_manifest_path()
    payload = _load_optional_manifest(path)
    if payload is None:
        return {
            "path": str(path),
            "exists": False,
            "status": "missing",
            "sample_count": 0,
            "measured_sample_count": 0,
            "missing_measurement_sample_ids": [],
            "metric_mean_by_axis": {},
            "metric_coverage_by_axis": {},
            "timing_ms_mean": None,
        }
    samples = payload.get("samples", [])
    sample_count = sum(1 for entry in samples if isinstance(entry, dict))
    measured_sample_count = 0
    missing_measurement_sample_ids: list[str] = []
    metric_values: dict[str, list[float]] = defaultdict(list)
    timing_values: list[float] = []
    for index, entry in enumerate(samples, start=1):
        if not isinstance(entry, dict):
            continue
        sample_id = str(entry.get("sample_id") or f"single_raw_{index:03d}")
        measurement_path = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "")
        measurement = _load_measurement(measurement_path, output_root=output_root) if measurement_path else None
        if measurement is None:
            missing_measurement_sample_ids.append(sample_id)
            continue
        if measurement.status != "measured":
            missing_measurement_sample_ids.append(sample_id)
            continue
        measured_sample_count += 1
        if measurement.timing_ms is not None:
            timing_values.append(float(measurement.timing_ms))
        for axis, value in measurement.metrics.items():
            metric_values[axis].append(float(value))
    return {
        "path": str(path),
        "exists": True,
        "status": str(payload.get("status") or ("partially_populated" if sample_count > 0 else "unpopulated")),
        "sample_count": sample_count,
        "measured_sample_count": measured_sample_count,
        "missing_measurement_sample_ids": missing_measurement_sample_ids,
        "metric_mean_by_axis": {axis: _mean_or_none(values) for axis, values in metric_values.items()},
        "metric_coverage_by_axis": {axis: len(values) for axis, values in metric_values.items()},
        "timing_ms_mean": _mean_or_none(timing_values),
    }


def _tri_raw_manifest_stats(bucket_ids: list[str], *, output_root: str) -> dict[str, Any]:
    path = _tri_raw_manifest_path()
    payload = _load_optional_manifest(path)
    if payload is None:
        return {
            "path": str(path),
            "exists": False,
            "status": "missing",
            "bucket_counts": {bucket_id: 0 for bucket_id in bucket_ids},
            "populated_bucket_ids": [],
            "missing_bucket_ids": list(bucket_ids),
            "sample_count": 0,
            "measured_sample_count": 0,
            "measured_bucket_ids": [],
            "missing_measurement_sample_ids": [],
            "measured_counts_by_bucket": {bucket_id: 0 for bucket_id in bucket_ids},
            "metric_mean_by_axis": {},
            "metric_coverage_by_axis": {},
            "metric_mean_by_bucket": {},
            "timing_ms_mean": None,
            "timing_ms_mean_by_bucket": {},
            "fallback_mode_counts": {},
        }
    samples = payload.get("samples", [])
    bucket_counts = {bucket_id: 0 for bucket_id in bucket_ids}
    sample_count = 0
    measured_sample_count = 0
    missing_measurement_sample_ids: list[str] = []
    measured_counts_by_bucket = {bucket_id: 0 for bucket_id in bucket_ids}
    metric_values: dict[str, list[float]] = defaultdict(list)
    bucket_metric_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    timing_values: list[float] = []
    bucket_timing_values: dict[str, list[float]] = defaultdict(list)
    fallback_mode_counts: dict[str, int] = defaultdict(int)
    for entry in samples:
        if not isinstance(entry, dict):
            continue
        sample_count += 1
        sample_id = str(entry.get("sample_id") or f"tri_raw_{sample_count:03d}")
        bucket_id = str(entry.get("bucket_id") or "")
        if bucket_id in bucket_counts:
            bucket_counts[bucket_id] += 1
        measurement_path = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "")
        measurement = _load_measurement(measurement_path, output_root=output_root) if measurement_path else None
        if measurement is None:
            missing_measurement_sample_ids.append(sample_id)
            continue
        if measurement.status != "measured":
            missing_measurement_sample_ids.append(sample_id)
            continue
        measured_sample_count += 1
        if bucket_id in measured_counts_by_bucket:
            measured_counts_by_bucket[bucket_id] += 1
        if measurement.timing_ms is not None:
            timing_values.append(float(measurement.timing_ms))
            if bucket_id:
                bucket_timing_values[bucket_id].append(float(measurement.timing_ms))
        for axis, value in measurement.metrics.items():
            metric_values[axis].append(float(value))
            if bucket_id:
                bucket_metric_values[bucket_id][axis].append(float(value))
        if measurement.fallback_mode:
            fallback_mode_counts[measurement.fallback_mode] += 1
    populated_bucket_ids = [bucket_id for bucket_id, count in bucket_counts.items() if count > 0]
    missing_bucket_ids = [bucket_id for bucket_id in bucket_ids if bucket_counts.get(bucket_id, 0) <= 0]
    measured_bucket_ids = [bucket_id for bucket_id, count in measured_counts_by_bucket.items() if count > 0]
    return {
        "path": str(path),
        "exists": True,
        "status": str(payload.get("status") or ("partially_populated" if sample_count > 0 else "unpopulated")),
        "bucket_counts": bucket_counts,
        "populated_bucket_ids": populated_bucket_ids,
        "missing_bucket_ids": missing_bucket_ids,
        "sample_count": sample_count,
        "measured_sample_count": measured_sample_count,
        "measured_bucket_ids": measured_bucket_ids,
        "missing_measurement_sample_ids": missing_measurement_sample_ids,
        "measured_counts_by_bucket": measured_counts_by_bucket,
        "metric_mean_by_axis": {axis: _mean_or_none(values) for axis, values in metric_values.items()},
        "metric_coverage_by_axis": {axis: len(values) for axis, values in metric_values.items()},
        "metric_mean_by_bucket": {
            bucket_id: {axis: _mean_or_none(values) for axis, values in axis_values.items()}
            for bucket_id, axis_values in bucket_metric_values.items()
        },
        "timing_ms_mean": _mean_or_none(timing_values),
        "timing_ms_mean_by_bucket": {
            bucket_id: _mean_or_none(values) for bucket_id, values in bucket_timing_values.items()
        },
        "fallback_mode_counts": dict(fallback_mode_counts),
    }


def _record_path(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark output_dir must stay inside the configured output root.") from exc
    return resolved / "rawprep_benchmark.json"


def _report_path(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark output_dir must stay inside the configured output root.") from exc
    return resolved / "rawprep_benchmark_report.json"


def _bucket_models(payload: dict) -> list[RawPrepBenchmarkBucket]:
    raw_buckets = payload.get("tri_raw", {}).get("bucket_definitions", [])
    if not isinstance(raw_buckets, list):
        return []

    buckets: list[RawPrepBenchmarkBucket] = []
    for entry in raw_buckets:
        if not isinstance(entry, dict):
            continue
        buckets.append(
            RawPrepBenchmarkBucket(
                bucket_id=str(entry.get("bucket_id") or "unknown"),
                label=str(entry.get("label") or "Unknown"),
                status=str(entry.get("status") or "defined"),
                sample_count=int(entry.get("sample_count") or 0),
                hard_case=bool(entry.get("hard_case") or False),
                traits=[str(value) for value in entry.get("traits", []) if isinstance(value, str)],
                required_report_sections=[
                    str(value) for value in entry.get("required_report_sections", []) if isinstance(value, str)
                ],
            )
        )
    return buckets


def build_rawprep_benchmark_record(request: RawPrepBenchmarkRequest) -> RawPrepBenchmarkRecord:
    catalog = load_benchmark_catalog()
    spec_path = _specification_path()
    if not spec_path.exists():
        raise FileNotFoundError(f"Benchmark specification catalog was not found: {spec_path}")

    single_raw = catalog.get("single_raw", {}).get("gold_set", {})
    tri_raw = catalog.get("tri_raw", {})
    hard_case = tri_raw.get("hard_case_bucket", {})
    report_template = catalog.get("report_template", {})
    product_metrics = catalog.get("product_metrics", {})
    compare_logging = product_metrics.get("compare_decision_logging", {})
    tri_raw_buckets = _bucket_models(catalog)
    tri_raw_bucket_ids = [bucket.bucket_id for bucket in tri_raw_buckets]
    single_raw_manifest = _single_raw_manifest_stats(output_root=request.output_root)
    tri_raw_manifest = _tri_raw_manifest_stats(tri_raw_bucket_ids, output_root=request.output_root)
    single_raw_sample_count = int(single_raw_manifest["sample_count"])
    for bucket in tri_raw_buckets:
        bucket.sample_count = int(tri_raw_manifest["bucket_counts"].get(bucket.bucket_id, bucket.sample_count))
        if bucket.sample_count > 0 and bucket.status == "spec_only":
            bucket.status = "partially_populated"
    hard_case_members = [
        str(value) for value in hard_case.get("member_bucket_ids", []) if isinstance(value, str)
    ]
    compare_decision_storage = [
        str(value) for value in compare_logging.get("storage", []) if isinstance(value, str)
    ]
    compare_decisions, compare_decision_summary = collect_compare_decisions([resolve_output_root(request.output_root)])
    compare_decision_count = len(compare_decisions)
    single_raw_measured_sample_count = int(single_raw_manifest["measured_sample_count"])
    tri_raw_measured_sample_count = int(tri_raw_manifest["measured_sample_count"])
    has_full_measurement = (
        single_raw_sample_count > 0
        and not tri_raw_manifest["missing_bucket_ids"]
        and single_raw_measured_sample_count == single_raw_sample_count
        and tri_raw_measured_sample_count == int(tri_raw_manifest["sample_count"])
    )
    if has_full_measurement:
        benchmark_status = "measured"
    elif single_raw_sample_count > 0 or int(tri_raw_manifest["sample_count"]) > 0:
        benchmark_status = "partially_populated"
    else:
        benchmark_status = "foundation_ready"
    benchmark_summary = {
        "measured": "Benchmark manifests and measured reports are populated; release evidence can now be reviewed.",
        "partially_populated": "Benchmark manifests are partially populated; measured reports and release evidence are still pending.",
        "foundation_ready": "Benchmark foundation is defined; dataset population and measured reports are the next step.",
    }[benchmark_status]

    details = [
        "Benchmark foundation is defined in benchmark/ and can now be exported as a structured report.",
        f"SingleRaw gold set manifest is {'present' if single_raw_manifest['exists'] else 'missing'} and currently lists {single_raw_sample_count} sample(s).",
        f"SingleRaw measured evidence currently covers {single_raw_measured_sample_count} sample(s).",
        f"TriRaw benchmark buckets are defined as: {', '.join(bucket.bucket_id for bucket in tri_raw_buckets) or 'none'}.",
        f"TriRaw sample manifest is {'present' if tri_raw_manifest['exists'] else 'missing'} and currently covers bucket(s): {', '.join(tri_raw_manifest['populated_bucket_ids']) or 'none'}.",
        f"TriRaw measured evidence currently covers {tri_raw_measured_sample_count} sample(s) across bucket(s): {', '.join(tri_raw_manifest['measured_bucket_ids']) or 'none'}.",
        f"Hard-case umbrella bucket covers: {', '.join(hard_case_members) or 'none'}.",
        f"Report template sections are fixed as: {', '.join(str(value) for value in report_template.get('sections', []))}.",
        f"Compare decision logging is {'defined' if compare_logging.get('defined') else 'not defined'} and currently captures {compare_decision_count} decision(s).",
    ]

    return RawPrepBenchmarkRecord(
        output_dir=request.output_dir,
        output_root=request.output_root,
        label=request.label,
        status=benchmark_status,
        summary=benchmark_summary,
        catalog_version=str(catalog.get("catalog_version") or "unknown"),
        catalog_path=str(_catalog_path()),
        specification_path=str(spec_path),
        single_raw_gold_set_defined=bool(single_raw.get("defined") or False),
        single_raw_gold_set_status=str(single_raw.get("status") or "undefined"),
        single_raw_sample_count=single_raw_sample_count,
        single_raw_measured_sample_count=single_raw_measured_sample_count,
        single_raw_missing_measurement_sample_ids=[
            str(value) for value in single_raw_manifest["missing_measurement_sample_ids"]
        ],
        single_raw_metric_mean_by_axis={
            str(key): float(value)
            for key, value in single_raw_manifest["metric_mean_by_axis"].items()
            if value is not None
        },
        single_raw_metric_coverage_by_axis={
            str(key): int(value) for key, value in single_raw_manifest["metric_coverage_by_axis"].items()
        },
        single_raw_timing_ms_mean=single_raw_manifest["timing_ms_mean"],
        single_raw_evaluation_axes=[
            str(value) for value in single_raw.get("evaluation_axes", []) if isinstance(value, str)
        ],
        single_raw_manifest_path=single_raw_manifest["path"],
        single_raw_manifest_exists=bool(single_raw_manifest["exists"]),
        single_raw_manifest_status=str(single_raw_manifest["status"]),
        tri_raw_buckets=tri_raw_buckets,
        hard_case_bucket_defined=bool(hard_case.get("defined") or False),
        hard_case_member_bucket_ids=hard_case_members,
        tri_raw_manifest_path=tri_raw_manifest["path"],
        tri_raw_manifest_exists=bool(tri_raw_manifest["exists"]),
        tri_raw_manifest_status=str(tri_raw_manifest["status"]),
        tri_raw_populated_bucket_ids=[str(value) for value in tri_raw_manifest["populated_bucket_ids"]],
        tri_raw_missing_bucket_ids=[str(value) for value in tri_raw_manifest["missing_bucket_ids"]],
        tri_raw_measured_sample_count=tri_raw_measured_sample_count,
        tri_raw_measured_bucket_ids=[str(value) for value in tri_raw_manifest["measured_bucket_ids"]],
        tri_raw_missing_measurement_sample_ids=[
            str(value) for value in tri_raw_manifest["missing_measurement_sample_ids"]
        ],
        tri_raw_measured_counts_by_bucket={
            str(key): int(value) for key, value in tri_raw_manifest["measured_counts_by_bucket"].items()
        },
        tri_raw_metric_mean_by_axis={
            str(key): float(value)
            for key, value in tri_raw_manifest["metric_mean_by_axis"].items()
            if value is not None
        },
        tri_raw_metric_coverage_by_axis={
            str(key): int(value) for key, value in tri_raw_manifest["metric_coverage_by_axis"].items()
        },
        tri_raw_metric_mean_by_bucket={
            str(bucket_id): {
                str(axis): float(value)
                for axis, value in axis_values.items()
                if value is not None
            }
            for bucket_id, axis_values in tri_raw_manifest["metric_mean_by_bucket"].items()
        },
        tri_raw_timing_ms_mean=tri_raw_manifest["timing_ms_mean"],
        tri_raw_timing_ms_mean_by_bucket={
            str(key): float(value)
            for key, value in tri_raw_manifest["timing_ms_mean_by_bucket"].items()
            if value is not None
        },
        tri_raw_fallback_mode_counts={
            str(key): int(value) for key, value in tri_raw_manifest["fallback_mode_counts"].items()
        },
        report_template_documented=bool(report_template.get("defined") or False),
        report_sections=[str(value) for value in report_template.get("sections", []) if isinstance(value, str)],
        compare_decision_logging_defined=bool(compare_logging.get("defined") or False),
        compare_decision_storage=compare_decision_storage,
        compare_decision_count=compare_decision_count,
        compare_decision_summary=compare_decision_summary,
        details=details,
        report_path=str(_report_path(request.output_dir, output_root=request.output_root)),
        report_status=benchmark_status,
    )


def build_rawprep_benchmark_report(record: RawPrepBenchmarkRecord) -> RawPrepBenchmarkReport:
    bucket_findings = [
        {
            "bucket_id": bucket.bucket_id,
            "label": bucket.label,
            "status": bucket.status,
            "sample_count": bucket.sample_count,
            "measured_sample_count": int(record.tri_raw_measured_counts_by_bucket.get(bucket.bucket_id, 0)),
            "hard_case": bucket.hard_case,
            "traits": bucket.traits,
            "required_report_sections": bucket.required_report_sections,
            "timing_ms_mean": record.tri_raw_timing_ms_mean_by_bucket.get(bucket.bucket_id),
            "metric_mean_by_axis": record.tri_raw_metric_mean_by_bucket.get(bucket.bucket_id, {}),
            "coverage_note": (
                "Bucket has measured sample coverage."
                if int(record.tri_raw_measured_counts_by_bucket.get(bucket.bucket_id, 0)) > 0
                else (
                    "Bucket has sample coverage but is still missing measured benchmark evidence."
                    if bucket.sample_count > 0
                    else "Bucket is defined but still missing real benchmark samples."
                )
            ),
        }
        for bucket in record.tri_raw_buckets
    ]
    open_risks: list[str] = []
    if not record.single_raw_manifest_exists or record.single_raw_sample_count <= 0:
        open_risks.append("SingleRaw gold set manifest is still empty, so checklist 9.1 remains open.")
    if record.single_raw_missing_measurement_sample_ids:
        open_risks.append(
            "SingleRaw measured evidence is still missing for: "
            + ", ".join(record.single_raw_missing_measurement_sample_ids)
            + "."
        )
    if record.tri_raw_missing_bucket_ids:
        open_risks.append(
            f"TriRaw sample manifest is missing bucket coverage for: {', '.join(record.tri_raw_missing_bucket_ids)}."
        )
    if record.tri_raw_missing_measurement_sample_ids:
        open_risks.append(
            "TriRaw measured evidence is still missing for: "
            + ", ".join(record.tri_raw_missing_measurement_sample_ids)
            + "."
        )
    if record.status != "measured":
        open_risks.append("Measured benchmark data is still missing, so this report is not release-decision evidence yet.")
    if record.compare_decision_count <= 0:
        open_risks.append("Operator compare decisions have not accumulated yet.")

    operator_notes = [
        "This report is generated from benchmark/ definitions plus any currently populated manifests.",
        "Bucket findings should be treated as governance coverage until real measured samples and results are attached.",
    ]
    if record.compare_decision_count > 0:
        operator_notes.append(
            f"Operator compare logs currently provide {record.compare_decision_count} decision(s) of supporting evidence."
        )
    if record.status == "measured":
        operator_notes.append("Every declared benchmark sample currently points to a measured benchmark result JSON.")

    return RawPrepBenchmarkReport(
        output_dir=record.output_dir,
        output_root=record.output_root,
        label=record.label,
        status=record.status,
        generated_at=datetime.now(timezone.utc).isoformat(),
        catalog_version=record.catalog_version,
        record_path=str(_record_path(record.output_dir, output_root=record.output_root)),
        dataset_overview={
            "single_raw_sample_count": record.single_raw_sample_count,
            "single_raw_measured_sample_count": record.single_raw_measured_sample_count,
            "single_raw_manifest_status": record.single_raw_manifest_status,
            "tri_raw_bucket_count": len(record.tri_raw_buckets),
            "tri_raw_populated_bucket_ids": record.tri_raw_populated_bucket_ids,
            "tri_raw_missing_bucket_ids": record.tri_raw_missing_bucket_ids,
            "tri_raw_measured_sample_count": record.tri_raw_measured_sample_count,
            "tri_raw_measured_bucket_ids": record.tri_raw_measured_bucket_ids,
            "compare_decision_count": record.compare_decision_count,
        },
        single_raw_summary={
            "manifest_path": record.single_raw_manifest_path,
            "manifest_exists": record.single_raw_manifest_exists,
            "manifest_status": record.single_raw_manifest_status,
            "sample_count": record.single_raw_sample_count,
            "measured_sample_count": record.single_raw_measured_sample_count,
            "missing_measurement_sample_ids": record.single_raw_missing_measurement_sample_ids,
            "evaluation_axes": record.single_raw_evaluation_axes,
            "metric_mean_by_axis": record.single_raw_metric_mean_by_axis,
            "metric_coverage_by_axis": record.single_raw_metric_coverage_by_axis,
            "timing_ms_mean": record.single_raw_timing_ms_mean,
        },
        tri_raw_summary={
            "manifest_path": record.tri_raw_manifest_path,
            "manifest_exists": record.tri_raw_manifest_exists,
            "manifest_status": record.tri_raw_manifest_status,
            "populated_bucket_ids": record.tri_raw_populated_bucket_ids,
            "missing_bucket_ids": record.tri_raw_missing_bucket_ids,
            "measured_sample_count": record.tri_raw_measured_sample_count,
            "measured_bucket_ids": record.tri_raw_measured_bucket_ids,
            "missing_measurement_sample_ids": record.tri_raw_missing_measurement_sample_ids,
            "metric_mean_by_axis": record.tri_raw_metric_mean_by_axis,
            "metric_coverage_by_axis": record.tri_raw_metric_coverage_by_axis,
            "timing_ms_mean": record.tri_raw_timing_ms_mean,
            "hard_case_member_bucket_ids": record.hard_case_member_bucket_ids,
        },
        bucket_findings=bucket_findings,
        fallback_behavior={
            "compare_decision_summary": record.compare_decision_summary,
            "hard_case_bucket_defined": record.hard_case_bucket_defined,
            "missing_bucket_ids": record.tri_raw_missing_bucket_ids,
            "fallback_mode_counts": record.tri_raw_fallback_mode_counts,
            "status_note": (
                "Fallback behavior is still governance-only until measured benchmark results are attached."
                if record.status != "measured"
                else "Fallback behavior includes measured benchmark evidence."
            ),
        },
        timing={
            "status": "unmeasured" if record.status != "measured" else "measured",
            "single_raw_timing_ms_mean": record.single_raw_timing_ms_mean,
            "tri_raw_timing_ms_mean": record.tri_raw_timing_ms_mean,
            "tri_raw_timing_ms_mean_by_bucket": record.tri_raw_timing_ms_mean_by_bucket,
            "note": (
                "Processing time sections stay unmeasured until every declared sample has a benchmark result JSON."
                if record.status != "measured"
                else "Processing time summary is aggregated from benchmark result JSON files."
            ),
        },
        open_risks=open_risks,
        operator_notes=operator_notes,
    )


def build_rawprep_benchmark_foundation_health(*, output_root: str = "outputs") -> RawPrepBenchmarkFoundationHealth:
    record = build_rawprep_benchmark_record(
        RawPrepBenchmarkRequest(
            output_dir="_benchmark_foundation_health",
            output_root=output_root,
            label="foundation_health",
        )
    )
    issues: list[RawPrepBenchmarkFoundationIssue] = []

    single_manifest_path = _single_raw_manifest_path()
    tri_manifest_path = _tri_raw_manifest_path()
    single_payload = _load_optional_manifest(single_manifest_path)
    tri_payload = _load_optional_manifest(tri_manifest_path)

    if single_payload is None:
        _append_foundation_issue(
            issues,
            severity="error",
            code="single_raw_manifest_missing",
            scope="single_raw",
            message="SingleRaw gold-set manifest is missing.",
            path=str(single_manifest_path),
        )
    if tri_payload is None:
        _append_foundation_issue(
            issues,
            severity="error",
            code="tri_raw_manifest_missing",
            scope="tri_raw",
            message="TriRaw bucket sample manifest is missing.",
            path=str(tri_manifest_path),
        )

    single_entries = _sample_entries(single_payload)
    tri_entries = _sample_entries(tri_payload)
    single_manifest_status = str(single_payload.get("status") or "") if single_payload else ""
    tri_manifest_status = str(tri_payload.get("status") or "") if tri_payload else ""

    seen_single_ids: set[str] = set()
    for index, entry in enumerate(single_entries, start=1):
        sample_id = str(entry.get("sample_id") or "").strip()
        if not sample_id:
            sample_id = f"single_raw_{index:03d}"
            _append_foundation_issue(
                issues,
                severity="error",
                code="single_raw_sample_id_missing",
                scope="single_raw",
                message="SingleRaw sample is missing sample_id.",
                sample_id=sample_id,
                path=str(single_manifest_path),
            )
        elif sample_id in seen_single_ids:
            _append_foundation_issue(
                issues,
                severity="error",
                code="single_raw_duplicate_sample_id",
                scope="single_raw",
                message="SingleRaw sample_id must be unique inside the official manifest.",
                sample_id=sample_id,
                path=str(single_manifest_path),
            )
        seen_single_ids.add(sample_id)

        raw_path = str(entry.get("raw_path") or "").strip()
        if not raw_path:
            _append_foundation_issue(
                issues,
                severity="error",
                code="single_raw_raw_path_missing",
                scope="single_raw",
                message="SingleRaw sample is missing raw_path.",
                sample_id=sample_id,
                path=str(single_manifest_path),
            )

        measurement_path_value = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "").strip()
        if single_manifest_status == "measured" and not measurement_path_value:
            _append_foundation_issue(
                issues,
                severity="error",
                code="single_raw_measurement_path_missing",
                scope="single_raw",
                message="Measured SingleRaw manifest entries must declare benchmark_result_path.",
                sample_id=sample_id,
                path=str(single_manifest_path),
            )
        elif measurement_path_value:
            _validate_measurement_reference(
                issues,
                scope="single_raw",
                sample_id=sample_id,
                output_root=output_root,
                measurement_path_value=measurement_path_value,
            )

    known_bucket_ids = {bucket.bucket_id for bucket in record.tri_raw_buckets}
    seen_tri_ids: set[str] = set()
    for index, entry in enumerate(tri_entries, start=1):
        sample_id = str(entry.get("sample_id") or "").strip()
        if not sample_id:
            sample_id = f"tri_raw_{index:03d}"
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_sample_id_missing",
                scope="tri_raw",
                message="TriRaw sample is missing sample_id.",
                sample_id=sample_id,
                path=str(tri_manifest_path),
            )
        elif sample_id in seen_tri_ids:
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_duplicate_sample_id",
                scope="tri_raw",
                message="TriRaw sample_id must be unique inside the official manifest.",
                sample_id=sample_id,
                path=str(tri_manifest_path),
            )
        seen_tri_ids.add(sample_id)

        bucket_id = str(entry.get("bucket_id") or "").strip()
        if not bucket_id:
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_bucket_missing",
                scope="tri_raw",
                message="TriRaw sample is missing bucket_id.",
                sample_id=sample_id,
                path=str(tri_manifest_path),
            )
        elif bucket_id not in known_bucket_ids:
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_unknown_bucket",
                scope="tri_raw",
                message=f"TriRaw sample bucket_id '{bucket_id}' is not defined in BENCHMARK_CATALOG.json.",
                sample_id=sample_id,
                bucket_id=bucket_id,
                path=str(tri_manifest_path),
            )

        source_paths = entry.get("source_paths")
        valid_source_paths = isinstance(source_paths, list) and all(isinstance(value, str) and value.strip() for value in source_paths)
        if not valid_source_paths or len(source_paths) != 3:
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_source_paths_invalid",
                scope="tri_raw",
                message="TriRaw sample must declare exactly 3 source_paths entries.",
                sample_id=sample_id,
                bucket_id=bucket_id or None,
                path=str(tri_manifest_path),
            )

        measurement_path_value = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "").strip()
        if tri_manifest_status == "measured" and not measurement_path_value:
            _append_foundation_issue(
                issues,
                severity="error",
                code="tri_raw_measurement_path_missing",
                scope="tri_raw",
                message="Measured TriRaw manifest entries must declare benchmark_result_path.",
                sample_id=sample_id,
                bucket_id=bucket_id or None,
                path=str(tri_manifest_path),
            )
        elif measurement_path_value:
            _validate_measurement_reference(
                issues,
                scope="tri_raw",
                sample_id=sample_id,
                bucket_id=bucket_id or None,
                output_root=output_root,
                measurement_path_value=measurement_path_value,
            )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    if error_count > 0:
        status = "blocked"
        summary = "Benchmark foundation has structural issues that should be fixed before population or release checks continue."
    elif record.status == "measured":
        status = "measured_ready"
        summary = "Benchmark foundation is populated and every declared sample currently has measured evidence."
    elif record.single_raw_sample_count <= 0 and sum(1 for entry in tri_entries) <= 0:
        status = "foundation_ready"
        summary = "Benchmark foundation files are structurally valid, but official samples have not been populated yet."
    elif record.single_raw_sample_count <= 0 or record.tri_raw_missing_bucket_ids:
        status = "population_incomplete"
        summary = "Benchmark manifests are structurally valid, but official sample coverage is still incomplete."
    else:
        status = "measurement_incomplete"
        summary = "Benchmark manifests are populated, but measured result JSON evidence is still incomplete."

    recommended_actions: list[str] = []
    if error_count > 0:
        recommended_actions.append("Fix duplicate sample IDs, bucket IDs, source_paths, and benchmark_result_path references before accumulating benchmark evidence.")
    if record.single_raw_sample_count <= 0:
        recommended_actions.append("Populate benchmark/SINGLE_RAW_GOLD_SET_MANIFEST.json with official SingleRaw gold-set samples.")
    if record.tri_raw_missing_bucket_ids:
        recommended_actions.append(
            "Populate benchmark/TRI_RAW_BUCKET_SAMPLE_MANIFEST.json for bucket(s): "
            + ", ".join(record.tri_raw_missing_bucket_ids)
            + "."
        )
    if record.single_raw_missing_measurement_sample_ids or record.tri_raw_missing_measurement_sample_ids:
        recommended_actions.append("Attach benchmark_result_path JSON files for every declared sample before treating the report as measured evidence.")
    if status == "measured_ready":
        recommended_actions.append("Accumulate measured benchmark runs and compare-decision evidence before deciding whether v2 becomes the default engine.")

    return RawPrepBenchmarkFoundationHealth(
        output_root=output_root,
        ok=error_count <= 0,
        status=status,
        summary=summary,
        catalog_version=record.catalog_version,
        single_raw_manifest_path=record.single_raw_manifest_path,
        tri_raw_manifest_path=record.tri_raw_manifest_path,
        single_raw_sample_count=record.single_raw_sample_count,
        single_raw_measured_sample_count=record.single_raw_measured_sample_count,
        tri_raw_sample_count=len(tri_entries),
        tri_raw_measured_sample_count=record.tri_raw_measured_sample_count,
        tri_raw_bucket_ids=[bucket.bucket_id for bucket in record.tri_raw_buckets],
        tri_raw_populated_bucket_ids=record.tri_raw_populated_bucket_ids,
        tri_raw_missing_bucket_ids=record.tri_raw_missing_bucket_ids,
        issue_counts={"error": error_count, "warning": warning_count},
        issues=issues,
        recommended_actions=recommended_actions,
    )


def run_rawprep_benchmark(request: RawPrepBenchmarkRequest) -> RawPrepBenchmarkRecord:
    record = build_rawprep_benchmark_record(request)
    report = build_rawprep_benchmark_report(record)
    path = _record_path(request.output_dir, output_root=request.output_root)
    report_path = _report_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_rawprep_benchmark_record(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkRecord:
    path = _record_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark record was not found: {path}")
    return RawPrepBenchmarkRecord(**json.loads(path.read_text(encoding="utf-8")))


def load_rawprep_benchmark_report(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkReport:
    path = _report_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark report was not found: {path}")
    return RawPrepBenchmarkReport(**json.loads(path.read_text(encoding="utf-8")))
