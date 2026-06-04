from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
    RawPrepBenchmarkMeasurementRecord,
    RawPrepBenchmarkMeasurementWriteRequest,
    write_rawprep_benchmark_measurement_from_single_raw_report,
    write_rawprep_benchmark_measurement,
)


class RawPrepBenchmarkMeasurementBatchEntry(BaseModel):
    sample_id: str
    status: str = "measured"
    timing_ms: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    fallback_mode: str | None = None
    notes: list[str] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(BaseModel):
    sample_id: str
    report_path: str
    status: str = "measured"
    notes: list[str] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementBatchIssue(BaseModel):
    sample_id: str | None = None
    severity: str = "error"
    code: str
    message: str


class RawPrepBenchmarkMeasurementBatchRequest(BaseModel):
    output_root: str = "outputs"
    entries: list[RawPrepBenchmarkMeasurementBatchEntry] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest(BaseModel):
    output_root: str = "outputs"
    entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = Field(default_factory=list)


class RawPrepBenchmarkMeasurementBatchRecord(BaseModel):
    output_root: str
    entry_count: int = 0
    written_count: int = 0
    skipped_count: int = 0
    success_sample_ids: list[str] = Field(default_factory=list)
    records: list[RawPrepBenchmarkMeasurementRecord] = Field(default_factory=list)
    issues: list[RawPrepBenchmarkMeasurementBatchIssue] = Field(default_factory=list)
    summary: str


def _issue(*, sample_id: str | None, code: str, message: str) -> RawPrepBenchmarkMeasurementBatchIssue:
    return RawPrepBenchmarkMeasurementBatchIssue(
        sample_id=sample_id,
        code=code,
        message=message,
    )


def _finalize_batch_record(
    *,
    output_root: str,
    entry_count: int,
    records: list[RawPrepBenchmarkMeasurementRecord],
    issues: list[RawPrepBenchmarkMeasurementBatchIssue],
    success_sample_ids: list[str],
    success_summary: str,
    partial_summary: str,
) -> RawPrepBenchmarkMeasurementBatchRecord:
    written_count = len(records)
    skipped_count = len(issues)
    summary = partial_summary if issues else success_summary
    return RawPrepBenchmarkMeasurementBatchRecord(
        output_root=output_root,
        entry_count=entry_count,
        written_count=written_count,
        skipped_count=skipped_count,
        success_sample_ids=success_sample_ids,
        records=records,
        issues=issues,
        summary=summary,
    )


def write_rawprep_benchmark_measurement_batch(
    request: RawPrepBenchmarkMeasurementBatchRequest,
) -> RawPrepBenchmarkMeasurementBatchRecord:
    records: list[RawPrepBenchmarkMeasurementRecord] = []
    issues: list[RawPrepBenchmarkMeasurementBatchIssue] = []
    success_sample_ids: list[str] = []

    for entry in request.entries:
        try:
            record = write_rawprep_benchmark_measurement(
                RawPrepBenchmarkMeasurementWriteRequest(
                    sample_id=entry.sample_id,
                    output_root=request.output_root,
                    status=entry.status,
                    timing_ms=entry.timing_ms,
                    metrics=entry.metrics,
                    fallback_mode=entry.fallback_mode,
                    notes=entry.notes,
                )
            )
        except (FileNotFoundError, ValueError) as exc:
            issues.append(
                _issue(
                    sample_id=entry.sample_id,
                    code="measurement_write_failed",
                    message=str(exc),
                )
            )
            continue
        records.append(record)
        success_sample_ids.append(record.sample_id)

    return _finalize_batch_record(
        output_root=request.output_root,
        entry_count=len(request.entries),
        records=records,
        issues=issues,
        success_sample_ids=success_sample_ids,
        success_summary="Batch measurement write completed for every provided sample.",
        partial_summary="Batch measurement write completed with some skipped entries.",
    )


def write_rawprep_benchmark_measurement_batch_from_single_raw_report(
    request: RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest,
) -> RawPrepBenchmarkMeasurementBatchRecord:
    records: list[RawPrepBenchmarkMeasurementRecord] = []
    issues: list[RawPrepBenchmarkMeasurementBatchIssue] = []
    success_sample_ids: list[str] = []

    for entry in request.entries:
        try:
            record = write_rawprep_benchmark_measurement_from_single_raw_report(
                RawPrepBenchmarkMeasurementFromSingleRawReportRequest(
                    sample_id=entry.sample_id,
                    report_path=entry.report_path,
                    output_root=request.output_root,
                    status=entry.status,
                    notes=entry.notes,
                )
            )
        except (FileNotFoundError, ValueError) as exc:
            issues.append(
                _issue(
                    sample_id=entry.sample_id,
                    code="measurement_report_bridge_failed",
                    message=str(exc),
                )
            )
            continue
        records.append(record)
        success_sample_ids.append(record.sample_id)

    return _finalize_batch_record(
        output_root=request.output_root,
        entry_count=len(request.entries),
        records=records,
        issues=issues,
        success_sample_ids=success_sample_ids,
        success_summary="Batch SingleRaw report bridge completed for every provided sample.",
        partial_summary="Batch SingleRaw report bridge completed with some skipped entries.",
    )


def load_rawprep_benchmark_measurement_batch_entries(input_path: str) -> list[RawPrepBenchmarkMeasurementBatchEntry]:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Measurement batch input was not found: {path}")

    if path.suffix.lower() == ".jsonl":
        entries: list[RawPrepBenchmarkMeasurementBatchEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("Each JSONL line must be a JSON object.")
            entries.append(RawPrepBenchmarkMeasurementBatchEntry(**payload))
        return entries

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if "entries" in payload and isinstance(payload["entries"], list):
            return [RawPrepBenchmarkMeasurementBatchEntry(**entry) for entry in payload["entries"] if isinstance(entry, dict)]
        return [RawPrepBenchmarkMeasurementBatchEntry(**payload)]
    if isinstance(payload, list):
        return [RawPrepBenchmarkMeasurementBatchEntry(**entry) for entry in payload if isinstance(entry, dict)]
    raise ValueError("Measurement batch input must be a JSON object, JSON array, or JSONL file.")


def load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries(
    input_path: str,
) -> list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry]:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Measurement report batch input was not found: {path}")

    if path.suffix.lower() == ".jsonl":
        entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("Each JSONL line must be a JSON object.")
            entries.append(RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(**payload))
        return entries

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if "entries" in payload and isinstance(payload["entries"], list):
            return [
                RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(**entry)
                for entry in payload["entries"]
                if isinstance(entry, dict)
            ]
        return [RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(**payload)]
    if isinstance(payload, list):
        return [
            RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(**entry)
            for entry in payload
            if isinstance(entry, dict)
        ]
    raise ValueError("Measurement report batch input must be a JSON object, JSON array, or JSONL file.")
