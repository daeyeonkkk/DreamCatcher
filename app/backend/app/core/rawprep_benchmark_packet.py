from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_gate import (
    RawPrepBenchmarkGate,
    load_rawprep_benchmark_gate,
    write_rawprep_benchmark_gate,
)
from .rawprep_benchmark_local_e2e_smoke import load_rawprep_benchmark_local_e2e_smoke
from .rawprep_benchmark_local_recovery_smoke import load_rawprep_benchmark_local_recovery_smoke
from .rawprep_benchmark_local_ui_language_smoke import load_rawprep_benchmark_local_ui_language_smoke
from .rawprep_benchmark_measurement_batch import (
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry,
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest,
    RawPrepBenchmarkMeasurementBatchEntry,
    RawPrepBenchmarkMeasurementBatchIssue,
    RawPrepBenchmarkMeasurementBatchRecord,
    RawPrepBenchmarkMeasurementBatchRequest,
    write_rawprep_benchmark_measurement_batch_from_single_raw_report,
    write_rawprep_benchmark_measurement_batch,
)
from .rawprep_benchmark_measurement_report_scaffold import (
    RawPrepBenchmarkMeasurementReportScaffold,
    RawPrepBenchmarkMeasurementReportScaffoldRequest,
    build_rawprep_benchmark_measurement_report_scaffold,
    write_rawprep_benchmark_measurement_report_batch_input,
)
from .rawprep_benchmark_review import (
    RawPrepBenchmarkReleaseReview,
    write_rawprep_benchmark_release_review,
)
from .rawprep_benchmark_runpod_smoke import (
    RawPrepBenchmarkRunPodSmokeEvidence,
    load_rawprep_benchmark_runpod_smoke,
    write_rawprep_benchmark_runpod_smoke,
)
from .rawprep_benchmark_service import (
    RawPrepBenchmarkRequest,
    RawPrepBenchmarkReport,
    build_rawprep_benchmark_foundation_health,
    load_rawprep_benchmark_report,
    run_rawprep_benchmark,
)
from .studio_paths import resolve_output_root


class RawPrepBenchmarkPacketRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    label: str | None = None
    measurement_entries: list[RawPrepBenchmarkMeasurementBatchEntry] = Field(default_factory=list)
    measurement_report_entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = Field(default_factory=list)
    measurement_report_scaffold_enabled: bool = False
    measurement_report_manifest_path: str | None = None
    measurement_report_search_root: str | None = None
    measurement_report_batch_input_path: str | None = None
    write_measurement_report_batch_input: bool = False
    include_existing_report_measurements: bool = False
    write_runpod_smoke: bool = True
    write_release_gate: bool = True
    write_release_review: bool = True


class RawPrepBenchmarkPacket(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    label: str | None = None
    packet_path: str | None = None
    measurement_batch_applied: bool = False
    measurement_report_batch_applied: bool = False
    measurement_report_scaffold_applied: bool = False
    measurement_batch_summary: str | None = None
    measurement_report_batch_summary: str | None = None
    measurement_report_scaffold_summary: str | None = None
    measurement_entry_count: int = 0
    measurement_report_entry_count: int = 0
    measurement_report_scaffold_entry_count: int = 0
    measurement_written_count: int = 0
    measurement_skipped_count: int = 0
    measurement_success_sample_ids: list[str] = Field(default_factory=list)
    measurement_issues: list[RawPrepBenchmarkMeasurementBatchIssue] = Field(default_factory=list)
    measurement_report_scaffold_batch_input_path: str | None = None
    measurement_report_scaffold_skipped_measured_sample_ids: list[str] = Field(default_factory=list)
    measurement_report_scaffold_missing_report_sample_ids: list[str] = Field(default_factory=list)
    measurement_report_scaffold_ambiguous_report_sample_ids: list[str] = Field(default_factory=list)
    benchmark_status: str = "foundation_ready"
    benchmark_report_status: str = "foundation_ready"
    foundation_status: str = "foundation_ready"
    runpod_smoke_status: str = "not_requested"
    release_gate_status: str = "not_requested"
    release_review_status: str = "not_requested"
    compare_decision_count: int = 0
    ready_for_default_review: bool = False
    ready_for_human_review: bool = False
    benchmark_record_path: str | None = None
    benchmark_report_path: str | None = None
    runpod_smoke_path: str | None = None
    local_e2e_smoke_path: str | None = None
    local_recovery_smoke_path: str | None = None
    local_ui_language_smoke_path: str | None = None
    release_gate_path: str | None = None
    release_review_path: str | None = None
    local_e2e_smoke_status: str = "missing"
    local_recovery_smoke_status: str = "missing"
    local_ui_language_smoke_status: str = "missing"
    report_open_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str


def _resolve_packet_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark packet output_dir must stay inside the configured output root.") from exc
    return resolved


def _packet_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_packet_output_dir(output_dir, output_root=output_root) / "rawprep_release_packet.json"


def _dedupe_actions(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _filter_measurement_report_scaffold(
    scaffold: RawPrepBenchmarkMeasurementReportScaffold,
    *,
    excluded_sample_ids: set[str],
) -> RawPrepBenchmarkMeasurementReportScaffold:
    if not excluded_sample_ids:
        return scaffold

    filtered_entries = [
        entry for entry in scaffold.entries if entry.sample_id not in excluded_sample_ids
    ]
    filtered_issues = [
        issue for issue in scaffold.issues if issue.sample_id not in excluded_sample_ids
    ]
    filtered_skipped = [
        sample_id
        for sample_id in scaffold.skipped_measured_sample_ids
        if sample_id not in excluded_sample_ids
    ]
    filtered_missing = [
        sample_id
        for sample_id in scaffold.missing_report_sample_ids
        if sample_id not in excluded_sample_ids
    ]
    filtered_ambiguous = [
        sample_id
        for sample_id in scaffold.ambiguous_report_sample_ids
        if sample_id not in excluded_sample_ids
    ]

    if filtered_issues:
        summary = "SingleRaw report batch scaffold completed with missing or ambiguous report mappings."
    elif filtered_entries:
        summary = "SingleRaw report batch scaffold is ready to feed the official benchmark measurement bridge."
    else:
        summary = "SingleRaw report batch scaffold did not add any automatic bridge entries after applying explicit overrides."

    return scaffold.model_copy(
        update={
            "entry_count": len(filtered_entries),
            "entries": filtered_entries,
            "issues": filtered_issues,
            "skipped_measured_sample_ids": filtered_skipped,
            "missing_report_sample_ids": filtered_missing,
            "ambiguous_report_sample_ids": filtered_ambiguous,
            "summary": summary,
            "wrote_batch_input": False,
            "batch_input_path": None,
        }
    )


def _merge_measurement_report_entries(
    *,
    explicit_entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry],
    scaffold_entries: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry],
) -> list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry]:
    merged: list[RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry] = []
    seen: set[str] = set()

    for entry in explicit_entries:
        if entry.sample_id in seen:
            continue
        seen.add(entry.sample_id)
        merged.append(entry)

    for entry in scaffold_entries:
        if entry.sample_id in seen:
            continue
        seen.add(entry.sample_id)
        merged.append(entry)

    return merged


def _load_gate_after_write(output_dir: str, *, output_root: str) -> RawPrepBenchmarkGate:
    try:
        return load_rawprep_benchmark_gate(output_dir, output_root=output_root)
    except FileNotFoundError:
        return write_rawprep_benchmark_gate(output_dir, output_root=output_root)


def _load_smoke_after_write(output_dir: str, *, output_root: str) -> RawPrepBenchmarkRunPodSmokeEvidence:
    try:
        return load_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    except FileNotFoundError:
        return write_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)


def write_rawprep_benchmark_packet(request: RawPrepBenchmarkPacketRequest) -> RawPrepBenchmarkPacket:
    measurement_batch: RawPrepBenchmarkMeasurementBatchRecord | None = None
    measurement_report_batch: RawPrepBenchmarkMeasurementBatchRecord | None = None
    measurement_report_scaffold: RawPrepBenchmarkMeasurementReportScaffold | None = None
    measurement_report_scaffold_batch_input_path: str | None = None

    measurement_report_entries = list(request.measurement_report_entries)
    if request.measurement_report_scaffold_enabled:
        measurement_report_scaffold = build_rawprep_benchmark_measurement_report_scaffold(
            RawPrepBenchmarkMeasurementReportScaffoldRequest(
                output_root=request.output_root,
                manifest_path=request.measurement_report_manifest_path,
                search_root=request.measurement_report_search_root,
                skip_existing_measurements=not request.include_existing_report_measurements,
            )
        )
        measurement_report_scaffold = _filter_measurement_report_scaffold(
            measurement_report_scaffold,
            excluded_sample_ids={entry.sample_id for entry in measurement_report_entries},
        )
        measurement_report_entries = _merge_measurement_report_entries(
            explicit_entries=measurement_report_entries,
            scaffold_entries=measurement_report_scaffold.entries,
        )
        if request.write_measurement_report_batch_input:
            measurement_report_scaffold_batch_input_path = str(
                write_rawprep_benchmark_measurement_report_batch_input(
                    measurement_report_scaffold.entries,
                    output_root=request.output_root,
                    batch_input_path=request.measurement_report_batch_input_path,
                )
            )

    if measurement_report_entries:
        measurement_report_batch = write_rawprep_benchmark_measurement_batch_from_single_raw_report(
            RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest(
                output_root=request.output_root,
                entries=measurement_report_entries,
            )
        )
    if request.measurement_entries:
        measurement_batch = write_rawprep_benchmark_measurement_batch(
            RawPrepBenchmarkMeasurementBatchRequest(
                output_root=request.output_root,
                entries=request.measurement_entries,
            )
        )

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir=request.output_dir,
            output_root=request.output_root,
            label=request.label,
        )
    )
    report: RawPrepBenchmarkReport = load_rawprep_benchmark_report(
        request.output_dir,
        output_root=request.output_root,
    )
    foundation = build_rawprep_benchmark_foundation_health(output_root=request.output_root)

    smoke: RawPrepBenchmarkRunPodSmokeEvidence | None = None
    gate: RawPrepBenchmarkGate | None = None
    review: RawPrepBenchmarkReleaseReview | None = None
    local_e2e_smoke = None
    local_recovery_smoke = None
    local_ui_language_smoke = None

    if request.write_release_review:
        review = write_rawprep_benchmark_release_review(
            request.output_dir,
            output_root=request.output_root,
        )
        gate = _load_gate_after_write(request.output_dir, output_root=request.output_root)
        smoke = _load_smoke_after_write(request.output_dir, output_root=request.output_root)
    elif request.write_release_gate:
        gate = write_rawprep_benchmark_gate(
            request.output_dir,
            output_root=request.output_root,
        )
        smoke = _load_smoke_after_write(request.output_dir, output_root=request.output_root)
    elif request.write_runpod_smoke:
        smoke = write_rawprep_benchmark_runpod_smoke(
            request.output_dir,
            output_root=request.output_root,
        )
    try:
        local_e2e_smoke = load_rawprep_benchmark_local_e2e_smoke(
            request.output_dir,
            output_root=request.output_root,
        )
    except FileNotFoundError:
        local_e2e_smoke = None
    try:
        local_recovery_smoke = load_rawprep_benchmark_local_recovery_smoke(
            request.output_dir,
            output_root=request.output_root,
        )
    except FileNotFoundError:
        local_recovery_smoke = None
    try:
        local_ui_language_smoke = load_rawprep_benchmark_local_ui_language_smoke(
            request.output_dir,
            output_root=request.output_root,
        )
    except FileNotFoundError:
        local_ui_language_smoke = None

    benchmark_dir = _resolve_packet_output_dir(request.output_dir, output_root=request.output_root)
    benchmark_record_path = benchmark_dir / "rawprep_benchmark.json"
    benchmark_report_path = benchmark_dir / "rawprep_benchmark_report.json"

    recommended_actions = list(foundation.recommended_actions)
    if measurement_report_scaffold is not None and measurement_report_scaffold.issues:
        recommended_actions.append(
            "Fix missing or ambiguous SingleRaw report mappings and rerun the benchmark packet so report-derived measurements can be imported."
        )
    if (
        measurement_report_scaffold is not None
        and not measurement_report_scaffold.entries
        and not request.measurement_report_entries
    ):
        recommended_actions.append(
            "Populate SingleRaw session report.json artifacts under outputs or pass explicit measurement_report_entries before rerunning the benchmark packet."
        )
    if measurement_report_batch is not None and measurement_report_batch.skipped_count > 0:
        recommended_actions.append(
            "Fix skipped SingleRaw report bridge entries and rerun the benchmark packet so every bridged sample gets measured evidence."
        )
    if measurement_batch is not None and measurement_batch.skipped_count > 0:
        recommended_actions.append(
            "Fix skipped batch measurement entries and rerun the benchmark packet so every declared sample gets measured evidence."
        )
    if smoke is not None:
        recommended_actions.extend(smoke.recommended_actions)
    if local_e2e_smoke is None:
        recommended_actions.append(
            "Run the local end-to-end smoke on curated benchmark samples so rawprep_local_e2e_smoke.json sits next to the measured run packet."
        )
    elif local_e2e_smoke.status != "passed":
        recommended_actions.append(
            "Fix the local SingleRaw/TriRaw/DreamISP handoff issues reported by rawprep_local_e2e_smoke.json before treating local evidence as complete."
        )
    if local_recovery_smoke is None:
        recommended_actions.append(
            "Run the local recovery smoke so rawprep_local_recovery_smoke.json verifies result retrieval and provider-pause readiness next to the measured run packet."
        )
    elif local_recovery_smoke.status != "passed":
        recommended_actions.append(
            "Fix the recovery export and provider-pause readiness issues reported by rawprep_local_recovery_smoke.json before treating local evidence as complete."
        )
    if local_ui_language_smoke is None:
        recommended_actions.append(
            "Run the local UI language smoke so rawprep_local_ui_language_smoke.json proves the curated studio surfaces stay Korean-first."
        )
    elif local_ui_language_smoke.status != "passed":
        recommended_actions.append(
            "Fix the remaining English display literals reported by rawprep_local_ui_language_smoke.json before treating the UI release evidence as complete."
        )
    if gate is not None:
        recommended_actions.extend(gate.recommended_actions)
    if review is not None:
        recommended_actions.extend(review.recommended_actions)
    recommended_actions = _dedupe_actions(recommended_actions)

    if review is not None and review.ready_for_human_review:
        summary = "Benchmark release packet is complete and ready for human default-engine review."
    elif gate is not None and gate.ready_for_default_review:
        summary = "Benchmark release packet is measured and release-gate ready; review snapshot was not requested."
    elif measurement_report_scaffold is not None and measurement_report_scaffold.issues:
        summary = "Benchmark packet was assembled, but some SingleRaw report scaffold mappings are still missing or ambiguous."
    elif (
        (measurement_report_batch is not None and measurement_report_batch.skipped_count > 0)
        or (measurement_batch is not None and measurement_batch.skipped_count > 0)
    ):
        summary = "Benchmark packet was assembled, but some batch measurement entries were skipped and release evidence is still incomplete."
    else:
        summary = "Benchmark packet was assembled, but measured benchmark or RunPod smoke evidence is still incomplete."

    combined_success_sample_ids: list[str] = []
    for batch in (measurement_report_batch, measurement_batch):
        if batch is None:
            continue
        for sample_id in batch.success_sample_ids:
            if sample_id not in combined_success_sample_ids:
                combined_success_sample_ids.append(sample_id)

    combined_issues: list[RawPrepBenchmarkMeasurementBatchIssue] = []
    if measurement_report_scaffold is not None:
        combined_issues.extend(measurement_report_scaffold.issues)
    for batch in (measurement_report_batch, measurement_batch):
        if batch is None:
            continue
        combined_issues.extend(batch.issues)

    measurement_batch_summary_parts = [
        batch.summary
        for batch in (measurement_report_batch, measurement_batch)
        if batch is not None and batch.summary
    ]

    packet = RawPrepBenchmarkPacket(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        label=request.label,
        packet_path=str(_packet_path(request.output_dir, output_root=request.output_root)),
        measurement_batch_applied=measurement_batch is not None,
        measurement_report_batch_applied=measurement_report_batch is not None,
        measurement_report_scaffold_applied=measurement_report_scaffold is not None,
        measurement_batch_summary=" / ".join(measurement_batch_summary_parts) if measurement_batch_summary_parts else None,
        measurement_report_batch_summary=measurement_report_batch.summary if measurement_report_batch is not None else None,
        measurement_report_scaffold_summary=measurement_report_scaffold.summary if measurement_report_scaffold is not None else None,
        measurement_entry_count=(measurement_batch.entry_count if measurement_batch is not None else 0),
        measurement_report_entry_count=(measurement_report_batch.entry_count if measurement_report_batch is not None else 0),
        measurement_report_scaffold_entry_count=(
            measurement_report_scaffold.entry_count if measurement_report_scaffold is not None else 0
        ),
        measurement_written_count=(
            (measurement_report_batch.written_count if measurement_report_batch is not None else 0)
            + (measurement_batch.written_count if measurement_batch is not None else 0)
        ),
        measurement_skipped_count=(
            (len(measurement_report_scaffold.issues) if measurement_report_scaffold is not None else 0)
            + (measurement_report_batch.skipped_count if measurement_report_batch is not None else 0)
            + (measurement_batch.skipped_count if measurement_batch is not None else 0)
        ),
        measurement_success_sample_ids=combined_success_sample_ids,
        measurement_issues=combined_issues,
        measurement_report_scaffold_batch_input_path=measurement_report_scaffold_batch_input_path,
        measurement_report_scaffold_skipped_measured_sample_ids=(
            measurement_report_scaffold.skipped_measured_sample_ids if measurement_report_scaffold is not None else []
        ),
        measurement_report_scaffold_missing_report_sample_ids=(
            measurement_report_scaffold.missing_report_sample_ids if measurement_report_scaffold is not None else []
        ),
        measurement_report_scaffold_ambiguous_report_sample_ids=(
            measurement_report_scaffold.ambiguous_report_sample_ids if measurement_report_scaffold is not None else []
        ),
        benchmark_status=record.status,
        benchmark_report_status=report.status,
        foundation_status=foundation.status,
        runpod_smoke_status=smoke.status if smoke is not None else "not_requested",
        release_gate_status=gate.status if gate is not None else "not_requested",
        release_review_status=review.status if review is not None else "not_requested",
        compare_decision_count=record.compare_decision_count,
        ready_for_default_review=bool(gate and gate.ready_for_default_review),
        ready_for_human_review=bool(review and review.ready_for_human_review),
        benchmark_record_path=str(benchmark_record_path),
        benchmark_report_path=str(benchmark_report_path),
        runpod_smoke_path=smoke.smoke_path if smoke is not None else None,
        local_e2e_smoke_path=(local_e2e_smoke.smoke_path if local_e2e_smoke is not None else None),
        local_recovery_smoke_path=(local_recovery_smoke.smoke_path if local_recovery_smoke is not None else None),
        local_ui_language_smoke_path=(local_ui_language_smoke.smoke_path if local_ui_language_smoke is not None else None),
        release_gate_path=gate.gate_path if gate is not None else None,
        release_review_path=review.review_path if review is not None else None,
        local_e2e_smoke_status=(local_e2e_smoke.status if local_e2e_smoke is not None else "missing"),
        local_recovery_smoke_status=(local_recovery_smoke.status if local_recovery_smoke is not None else "missing"),
        local_ui_language_smoke_status=(local_ui_language_smoke.status if local_ui_language_smoke is not None else "missing"),
        report_open_risks=report.open_risks,
        recommended_actions=recommended_actions,
        summary=summary,
    )
    path = _packet_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return packet


def load_rawprep_benchmark_packet(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkPacket:
    path = _packet_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark release packet artifact was not found: {path}")
    return RawPrepBenchmarkPacket(**json.loads(path.read_text(encoding="utf-8")))
