from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_measurement_batch import (
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry,
    RawPrepBenchmarkMeasurementBatchIssue,
)
from .rawprep_benchmark_service import (
    _load_measurement,
    _load_optional_manifest,
    _resolve_manifest_relative_path,
    _sample_entries,
    _single_raw_manifest_path,
)
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkMeasurementReportScaffoldRequest(BaseModel):
    output_root: str = "outputs"
    manifest_path: str | None = None
    search_root: str | None = None
    batch_input_path: str | None = None
    write_batch_input: bool = False
    skip_existing_measurements: bool = True


class RawPrepBenchmarkMeasurementReportScaffold(BaseModel):
    output_root: str
    manifest_path: str
    search_root: str
    batch_input_path: str | None = None
    wrote_batch_input: bool = False
    skip_existing_measurements: bool = True
    manifest_sample_count: int = 0
    entry_count: int = 0
    skipped_measured_sample_ids: list[str] = Field(default_factory=list)
    missing_report_sample_ids: list[str] = Field(default_factory=list)
    ambiguous_report_sample_ids: list[str] = Field(default_factory=list)
    entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = Field(default_factory=list)
    issues: list[RawPrepBenchmarkMeasurementBatchIssue] = Field(default_factory=list)
    summary: str


def _resolve_local_path(path_value: str) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (repo_root() / path).resolve()


def _resolve_manifest_path(path_value: str | None) -> Path:
    if path_value:
        return _resolve_local_path(path_value)
    return _single_raw_manifest_path().resolve()


def _resolve_search_root(request: RawPrepBenchmarkMeasurementReportScaffoldRequest) -> Path:
    if request.search_root:
        resolved = _resolve_local_path(request.search_root)
    else:
        resolved = resolve_output_root(request.output_root).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"Benchmark report scaffold search_root was not found or is not a directory: {resolved}")
    return resolved


def _resolve_batch_input_path(request: RawPrepBenchmarkMeasurementReportScaffoldRequest) -> Path:
    if request.batch_input_path:
        resolved = _resolve_manifest_relative_path(request.batch_input_path, output_root=request.output_root)
        if resolved is None:
            raise ValueError("batch_input_path must stay inside the repository or output root.")
        return resolved
    return (resolve_output_root(request.output_root) / "_benchmark_inputs" / "single_raw_report_batch.jsonl").resolve()


def write_rawprep_benchmark_measurement_report_batch_input(
    entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry],
    *,
    output_root: str = "outputs",
    batch_input_path: str | None = None,
) -> Path:
    request = RawPrepBenchmarkMeasurementReportScaffoldRequest(
        output_root=output_root,
        batch_input_path=batch_input_path,
    )
    resolved_path = _resolve_batch_input_path(request)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(entry.model_dump(), ensure_ascii=False) for entry in entries]
    resolved_path.write_text("\n".join(lines), encoding="utf-8")
    return resolved_path


def _issue(*, sample_id: str | None, code: str, message: str) -> RawPrepBenchmarkMeasurementBatchIssue:
    return RawPrepBenchmarkMeasurementBatchIssue(
        sample_id=sample_id,
        code=code,
        message=message,
    )


def _report_candidates(search_root: Path, sample_id: str) -> list[Path]:
    pattern = f"**/01_single_raw/{sample_id}/report.json"
    return sorted(path.resolve() for path in search_root.glob(pattern) if path.is_file())


def build_rawprep_benchmark_measurement_report_scaffold(
    request: RawPrepBenchmarkMeasurementReportScaffoldRequest,
) -> RawPrepBenchmarkMeasurementReportScaffold:
    manifest_path = _resolve_manifest_path(request.manifest_path)
    payload = _load_optional_manifest(manifest_path)
    if payload is None:
        raise FileNotFoundError(f"SingleRaw benchmark manifest was not found: {manifest_path}")

    search_root = _resolve_search_root(request)
    entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = []
    issues: list[RawPrepBenchmarkMeasurementBatchIssue] = []
    skipped_measured_sample_ids: list[str] = []
    missing_report_sample_ids: list[str] = []
    ambiguous_report_sample_ids: list[str] = []

    manifest_entries = _sample_entries(payload)
    for entry in manifest_entries:
        sample_id = str(entry.get("sample_id") or "").strip()
        if not sample_id:
            continue

        measurement_path_value = str(entry.get("benchmark_result_path") or entry.get("measurement_path") or "").strip()
        if request.skip_existing_measurements and measurement_path_value:
            measurement = _load_measurement(measurement_path_value, output_root=request.output_root)
            if measurement is not None:
                skipped_measured_sample_ids.append(sample_id)
                continue

        candidates = _report_candidates(search_root, sample_id)
        if not candidates:
            missing_report_sample_ids.append(sample_id)
            issues.append(
                _issue(
                    sample_id=sample_id,
                    code="single_raw_report_missing",
                    message="SingleRaw report.json was not found under the configured search_root.",
                )
            )
            continue
        if len(candidates) > 1:
            ambiguous_report_sample_ids.append(sample_id)
            issues.append(
                _issue(
                    sample_id=sample_id,
                    code="single_raw_report_ambiguous",
                    message=f"Multiple SingleRaw report.json files were found for sample '{sample_id}'. Narrow the search_root or clean old session outputs.",
                )
            )
            continue

        report_path = candidates[0]
        try:
            repo_relative = report_path.relative_to(repo_root().resolve()).as_posix()
        except ValueError:
            repo_relative = str(report_path)
        entries.append(
            RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(
                sample_id=sample_id,
                report_path=repo_relative,
            )
        )

    batch_input_path: Path | None = None
    wrote_batch_input = False
    if request.write_batch_input:
        batch_input_path = write_rawprep_benchmark_measurement_report_batch_input(
            entries,
            output_root=request.output_root,
            batch_input_path=request.batch_input_path,
        )
        wrote_batch_input = True

    if issues:
        summary = "SingleRaw report batch scaffold completed with missing or ambiguous report mappings."
    elif entries:
        summary = "SingleRaw report batch scaffold is ready to feed the official benchmark measurement bridge."
    else:
        summary = "SingleRaw report batch scaffold did not find any report entries to bridge."

    return RawPrepBenchmarkMeasurementReportScaffold(
        output_root=request.output_root,
        manifest_path=str(manifest_path),
        search_root=str(search_root),
        batch_input_path=str(batch_input_path) if batch_input_path is not None else None,
        wrote_batch_input=wrote_batch_input,
        skip_existing_measurements=request.skip_existing_measurements,
        manifest_sample_count=len(manifest_entries),
        entry_count=len(entries),
        skipped_measured_sample_ids=skipped_measured_sample_ids,
        missing_report_sample_ids=missing_report_sample_ids,
        ambiguous_report_sample_ids=ambiguous_report_sample_ids,
        entries=entries,
        issues=issues,
        summary=summary,
    )
