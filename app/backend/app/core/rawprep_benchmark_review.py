from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_gate import (
    RawPrepBenchmarkGate,
    RawPrepBenchmarkGateIssue,
    build_rawprep_benchmark_gate,
    write_rawprep_benchmark_gate,
)
from .rawprep_benchmark_local_e2e_smoke import load_rawprep_benchmark_local_e2e_smoke
from .rawprep_benchmark_local_recovery_smoke import load_rawprep_benchmark_local_recovery_smoke
from .rawprep_benchmark_local_ui_language_smoke import load_rawprep_benchmark_local_ui_language_smoke
from .rawprep_benchmark_runpod_smoke import write_rawprep_benchmark_runpod_smoke
from .rawprep_benchmark_service import (
    RawPrepBenchmarkReport,
    build_rawprep_benchmark_foundation_health,
    load_rawprep_benchmark_report,
)
from .studio_paths import resolve_output_root


class RawPrepBenchmarkReleaseReviewRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"


class RawPrepBenchmarkReleaseReview(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "evidence_incomplete"
    ready_for_human_review: bool = False
    summary: str
    review_path: str | None = None
    gate_path: str | None = None
    runpod_smoke_path: str | None = None
    local_e2e_smoke_path: str | None = None
    local_recovery_smoke_path: str | None = None
    local_ui_language_smoke_path: str | None = None
    benchmark_record_path: str | None = None
    benchmark_report_path: str | None = None
    bootstrap_summary_path: str | None = None
    rawprep_healthcheck_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    gate_status: str = "missing"
    foundation_status: str = "missing"
    benchmark_report_status: str = "missing"
    runpod_smoke_status: str = "missing"
    local_e2e_smoke_status: str = "missing"
    local_recovery_smoke_status: str = "missing"
    local_ui_language_smoke_status: str = "missing"
    compare_decision_count: int = 0
    artifact_presence: dict[str, bool] = Field(default_factory=dict)
    report_open_risks: list[str] = Field(default_factory=list)
    report_operator_notes: list[str] = Field(default_factory=list)
    blockers: list[RawPrepBenchmarkGateIssue] = Field(default_factory=list)
    warnings: list[RawPrepBenchmarkGateIssue] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _resolve_review_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark review output_dir must stay inside the configured output root.") from exc
    return resolved


def _review_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_review_output_dir(output_dir, output_root=output_root) / "rawprep_release_review.json"


def _build_release_review_from_gate(
    gate: RawPrepBenchmarkGate,
    *,
    output_dir: str,
    output_root: str,
) -> RawPrepBenchmarkReleaseReview:
    report: RawPrepBenchmarkReport | None = None
    local_e2e_smoke = None
    local_recovery_smoke = None
    local_ui_language_smoke = None
    try:
        report = load_rawprep_benchmark_report(output_dir, output_root=output_root)
    except FileNotFoundError:
        report = None
    try:
        local_e2e_smoke = load_rawprep_benchmark_local_e2e_smoke(output_dir, output_root=output_root)
    except FileNotFoundError:
        local_e2e_smoke = None
    try:
        local_recovery_smoke = load_rawprep_benchmark_local_recovery_smoke(output_dir, output_root=output_root)
    except FileNotFoundError:
        local_recovery_smoke = None
    try:
        local_ui_language_smoke = load_rawprep_benchmark_local_ui_language_smoke(output_dir, output_root=output_root)
    except FileNotFoundError:
        local_ui_language_smoke = None

    foundation = build_rawprep_benchmark_foundation_health(output_root=output_root)
    artifact_presence = {
        "benchmark_record": bool(gate.benchmark_record_path and Path(gate.benchmark_record_path).exists()),
        "benchmark_report": bool(gate.benchmark_report_path and Path(gate.benchmark_report_path).exists()),
        "runpod_smoke": bool(gate.runpod_smoke_path and Path(gate.runpod_smoke_path).exists()),
        "local_e2e_smoke": bool(local_e2e_smoke and local_e2e_smoke.smoke_path and Path(local_e2e_smoke.smoke_path).exists()),
        "local_recovery_smoke": bool(local_recovery_smoke and local_recovery_smoke.smoke_path and Path(local_recovery_smoke.smoke_path).exists()),
        "local_ui_language_smoke": bool(local_ui_language_smoke and local_ui_language_smoke.smoke_path and Path(local_ui_language_smoke.smoke_path).exists()),
        "release_gate": bool(gate.gate_path and Path(gate.gate_path).exists()),
        "bootstrap_summary": bool(gate.bootstrap_summary_path and Path(gate.bootstrap_summary_path).exists()),
        "rawprep_healthcheck": bool(gate.rawprep_healthcheck_path and Path(gate.rawprep_healthcheck_path).exists()),
        "single_raw_healthcheck": bool(gate.single_raw_healthcheck_path and Path(gate.single_raw_healthcheck_path).exists()),
    }

    if gate.ready_for_default_review:
        status = "ready_for_human_review"
        summary = "Measured benchmark, RunPod smoke, and release gate evidence are assembled; human default-engine review can proceed."
    else:
        status = "evidence_incomplete"
        summary = gate.summary

    recommended_actions = list(gate.recommended_actions)
    if report is not None and report.open_risks:
        recommended_actions.append("Review benchmark report open_risks before promoting v2 to the default engine.")
    if local_e2e_smoke is None:
        recommended_actions.append("Run the local end-to-end smoke on curated benchmark samples and keep rawprep_local_e2e_smoke.json next to the measured run.")
    elif local_e2e_smoke.status != "passed":
        recommended_actions.append("Fix the local SingleRaw/TriRaw/DreamISP handoff issues reported by rawprep_local_e2e_smoke.json before treating local evidence as complete.")
    if local_recovery_smoke is None:
        recommended_actions.append("Run the local recovery smoke and keep rawprep_local_recovery_smoke.json next to the measured run so result retrieval readiness is captured as release evidence.")
    elif local_recovery_smoke.status != "passed":
        recommended_actions.append("Fix the recovery export and provider-pause readiness issues reported by rawprep_local_recovery_smoke.json before treating local evidence as complete.")
    if local_ui_language_smoke is None:
        recommended_actions.append("Run the local UI language smoke and keep rawprep_local_ui_language_smoke.json next to the measured run so Korean UI coverage is captured as release evidence.")
    elif local_ui_language_smoke.status != "passed":
        recommended_actions.append("Fix the remaining English display literals reported by rawprep_local_ui_language_smoke.json before treating the UI release evidence as complete.")

    return RawPrepBenchmarkReleaseReview(
        output_dir=output_dir,
        output_root=output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        ready_for_human_review=gate.ready_for_default_review,
        summary=summary,
        review_path=str(_review_path(output_dir, output_root=output_root)),
        gate_path=gate.gate_path,
        runpod_smoke_path=gate.runpod_smoke_path,
        local_e2e_smoke_path=(local_e2e_smoke.smoke_path if local_e2e_smoke is not None else None),
        local_recovery_smoke_path=(local_recovery_smoke.smoke_path if local_recovery_smoke is not None else None),
        local_ui_language_smoke_path=(local_ui_language_smoke.smoke_path if local_ui_language_smoke is not None else None),
        benchmark_record_path=gate.benchmark_record_path,
        benchmark_report_path=gate.benchmark_report_path,
        bootstrap_summary_path=gate.bootstrap_summary_path,
        rawprep_healthcheck_path=gate.rawprep_healthcheck_path,
        single_raw_healthcheck_path=gate.single_raw_healthcheck_path,
        gate_status=gate.status,
        foundation_status=foundation.status,
        benchmark_report_status=report.status if report is not None else "missing",
        runpod_smoke_status=gate.runpod_smoke_status,
        local_e2e_smoke_status=(local_e2e_smoke.status if local_e2e_smoke is not None else "missing"),
        local_recovery_smoke_status=(local_recovery_smoke.status if local_recovery_smoke is not None else "missing"),
        local_ui_language_smoke_status=(local_ui_language_smoke.status if local_ui_language_smoke is not None else "missing"),
        compare_decision_count=gate.compare_decision_count,
        artifact_presence=artifact_presence,
        report_open_risks=report.open_risks if report is not None else [],
        report_operator_notes=report.operator_notes if report is not None else [],
        blockers=gate.blockers,
        warnings=gate.warnings,
        recommended_actions=recommended_actions,
    )


def build_rawprep_benchmark_release_review(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkReleaseReview:
    gate = build_rawprep_benchmark_gate(output_dir, output_root=output_root)
    return _build_release_review_from_gate(gate, output_dir=output_dir, output_root=output_root)


def write_rawprep_benchmark_release_review(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkReleaseReview:
    write_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    gate = write_rawprep_benchmark_gate(output_dir, output_root=output_root)
    review = _build_release_review_from_gate(gate, output_dir=output_dir, output_root=output_root)
    path = _review_path(output_dir, output_root=output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def load_rawprep_benchmark_release_review(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkReleaseReview:
    path = _review_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark release review artifact was not found: {path}")
    return RawPrepBenchmarkReleaseReview(**json.loads(path.read_text(encoding="utf-8")))
