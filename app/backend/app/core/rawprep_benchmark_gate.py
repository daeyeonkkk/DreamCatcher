from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_runpod_smoke import (
    RawPrepBenchmarkRunPodSmokeIssue,
    build_rawprep_benchmark_runpod_smoke,
    write_rawprep_benchmark_runpod_smoke,
)
from .rawprep_benchmark_service import (
    RawPrepBenchmarkFoundationHealth,
    RawPrepBenchmarkRecord,
    RawPrepBenchmarkReport,
    build_rawprep_benchmark_foundation_health,
    load_rawprep_benchmark_record,
    load_rawprep_benchmark_report,
)
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkGateRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"


class RawPrepBenchmarkGateIssue(BaseModel):
    severity: str = "error"
    code: str
    message: str
    path: str | None = None


class RawPrepBenchmarkGate(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    ok: bool = False
    ready_for_default_review: bool = False
    status: str = "blocked"
    summary: str
    foundation_status: str = "missing"
    benchmark_record_status: str = "missing"
    benchmark_report_status: str = "missing"
    runpod_smoke_status: str = "missing"
    compare_decision_count: int = 0
    gate_path: str | None = None
    runpod_smoke_path: str | None = None
    benchmark_record_path: str | None = None
    benchmark_report_path: str | None = None
    bootstrap_summary_path: str | None = None
    rawprep_healthcheck_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    blockers: list[RawPrepBenchmarkGateIssue] = Field(default_factory=list)
    warnings: list[RawPrepBenchmarkGateIssue] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _resolve_gate_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark gate output_dir must stay inside the configured output root.") from exc
    return resolved


def _gate_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_gate_output_dir(output_dir, output_root=output_root) / "rawprep_release_gate.json"


def _append_issue(
    issues: list[RawPrepBenchmarkGateIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    issues.append(
        RawPrepBenchmarkGateIssue(
            severity=severity,
            code=code,
            message=message,
            path=path,
        )
    )


def _gate_issue_from_smoke(issue: RawPrepBenchmarkRunPodSmokeIssue) -> RawPrepBenchmarkGateIssue:
    return RawPrepBenchmarkGateIssue(
        severity=issue.severity,
        code=issue.code,
        message=issue.message,
        path=issue.path,
    )


def build_rawprep_benchmark_gate(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkGate:
    blockers: list[RawPrepBenchmarkGateIssue] = []
    warnings: list[RawPrepBenchmarkGateIssue] = []
    recommended_actions: list[str] = []

    foundation_health = build_rawprep_benchmark_foundation_health(output_root=output_root)
    record: RawPrepBenchmarkRecord | None = None
    report: RawPrepBenchmarkReport | None = None

    try:
        record = load_rawprep_benchmark_record(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_record_missing",
            message=str(exc),
        )
    try:
        report = load_rawprep_benchmark_report(output_dir, output_root=output_root)
    except FileNotFoundError as exc:
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_report_missing",
            message=str(exc),
        )

    if not foundation_health.ok:
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_foundation_invalid",
            message="Benchmark foundation has structural issues that must be fixed before release review.",
        )
    elif foundation_health.status != "measured_ready":
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_foundation_not_measured_ready",
            message=f"Benchmark foundation status is '{foundation_health.status}', so measured release evidence is not complete yet.",
        )

    if record is not None and record.status != "measured":
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_record_not_measured",
            message=f"Benchmark record status is '{record.status}', so release evidence is not fully measured yet.",
            path=record.report_path,
        )
    if report is not None and report.status != "measured":
        _append_issue(
            blockers,
            severity="error",
            code="benchmark_report_not_measured",
            message=f"Benchmark report status is '{report.status}', so release evidence is not fully measured yet.",
            path=report.record_path,
        )

    if record is not None and record.compare_decision_count <= 0:
        _append_issue(
            warnings,
            severity="warning",
            code="compare_decision_evidence_missing",
            message="Operator compare decision evidence has not accumulated yet.",
        )

    smoke = build_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    blockers.extend(_gate_issue_from_smoke(issue) for issue in smoke.blockers)
    warnings.extend(_gate_issue_from_smoke(issue) for issue in smoke.warnings)

    if not foundation_health.ok:
        recommended_actions.append("Fix benchmark foundation issues reported by /api/rawprep/benchmark/foundation before reviewing release readiness.")
    elif foundation_health.status != "measured_ready":
        recommended_actions.extend(foundation_health.recommended_actions)

    if record is None or report is None:
        recommended_actions.append("Run /api/rawprep/benchmark after populating manifests so a benchmark record and report exist for release review.")
    elif record.status != "measured" or report.status != "measured":
        recommended_actions.append("Promote the benchmark run to measured status by attaching measured result JSON for every declared sample.")

    if smoke.status != "passed":
        recommended_actions.extend(smoke.recommended_actions)

    benchmark_blocked = any(issue.code.startswith("benchmark_") for issue in blockers)
    smoke_blocked = any(issue.code.startswith("runpod_") for issue in blockers)
    if not blockers:
        status = "ready_for_default_review"
        summary = "Measured benchmark evidence and RunPod smoke evidence are both present; v2 can now be reviewed for default-engine promotion."
    elif benchmark_blocked and smoke_blocked:
        status = "benchmark_and_smoke_pending"
        summary = "Release gate is blocked by both benchmark evidence gaps and missing RunPod smoke evidence."
    elif benchmark_blocked:
        status = "benchmark_pending"
        summary = "Release gate is blocked by benchmark evidence gaps."
    elif smoke_blocked:
        status = "runpod_smoke_pending"
        summary = "Release gate is blocked by missing or failing RunPod smoke evidence."
    else:
        status = "blocked"
        summary = "Release gate is blocked by unresolved evidence issues."

    return RawPrepBenchmarkGate(
        output_dir=output_dir,
        output_root=output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ok=not blockers,
        ready_for_default_review=not blockers,
        status=status,
        summary=summary,
        foundation_status=foundation_health.status,
        benchmark_record_status=record.status if record is not None else "missing",
        benchmark_report_status=report.status if report is not None else "missing",
        runpod_smoke_status=smoke.status,
        compare_decision_count=record.compare_decision_count if record is not None else 0,
        gate_path=str(_gate_path(output_dir, output_root=output_root)),
        runpod_smoke_path=smoke.smoke_path,
        benchmark_record_path=(str(Path(record.report_path).with_name("rawprep_benchmark.json")) if record is not None and record.report_path else None),
        benchmark_report_path=(record.report_path if record is not None else None),
        bootstrap_summary_path=smoke.bootstrap_summary_path,
        rawprep_healthcheck_path=smoke.rawprep_healthcheck_path,
        single_raw_healthcheck_path=smoke.single_raw_healthcheck_path,
        blockers=blockers,
        warnings=warnings,
        recommended_actions=recommended_actions,
    )


def write_rawprep_benchmark_gate(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkGate:
    write_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    gate = build_rawprep_benchmark_gate(output_dir, output_root=output_root)
    path = _gate_path(output_dir, output_root=output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gate.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return gate


def load_rawprep_benchmark_gate(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkGate:
    path = _gate_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark gate artifact was not found: {path}")
    return RawPrepBenchmarkGate(**json.loads(path.read_text(encoding="utf-8")))
