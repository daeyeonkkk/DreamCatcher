from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_packet import (
    RawPrepBenchmarkPacket,
    RawPrepBenchmarkPacketRequest,
    load_rawprep_benchmark_packet,
    write_rawprep_benchmark_packet,
)
from .rawprep_benchmark_review import (
    RawPrepBenchmarkReleaseReview,
    load_rawprep_benchmark_release_review,
)
from .rawprep_benchmark_service import (
    RawPrepBenchmarkReport,
    load_rawprep_benchmark_report,
)
from .studio_paths import resolve_output_root


class RawPrepBenchmarkDefaultDecisionRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    label: str | None = None


class RawPrepBenchmarkDefaultDecision(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "benchmark_evidence_incomplete"
    promotion_recommendation: str = "hold_default_promotion"
    benchmark_evidence_ready: bool = False
    release_promotion_ready: bool = False
    summary: str
    decision_path: str | None = None
    benchmark_report_path: str | None = None
    release_packet_path: str | None = None
    release_review_path: str | None = None
    benchmark_status: str = "missing"
    foundation_status: str = "missing"
    benchmark_report_status: str = "missing"
    release_gate_status: str = "missing"
    release_review_status: str = "missing"
    runpod_smoke_status: str = "missing"
    local_e2e_smoke_status: str = "missing"
    local_recovery_smoke_status: str = "missing"
    local_ui_language_smoke_status: str = "missing"
    single_raw_sample_count: int = 0
    single_raw_measured_sample_count: int = 0
    tri_raw_bucket_count: int = 0
    tri_raw_measured_sample_count: int = 0
    tri_raw_measured_bucket_ids: list[str] = Field(default_factory=list)
    compare_decision_count: int = 0
    single_raw_timing_ms_mean: float | None = None
    tri_raw_timing_ms_mean: float | None = None
    blockers: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _resolve_decision_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark default decision output_dir must stay inside the configured output root.") from exc
    return resolved


def _decision_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_decision_output_dir(output_dir, output_root=output_root) / "rawprep_default_engine_decision.json"


def _dedupe_actions(actions: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for action in actions:
        normalized = action.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _load_decision_inputs(
    output_dir: str,
    *,
    output_root: str,
) -> tuple[RawPrepBenchmarkPacket, RawPrepBenchmarkReleaseReview, RawPrepBenchmarkReport]:
    packet = load_rawprep_benchmark_packet(output_dir, output_root=output_root)
    review = load_rawprep_benchmark_release_review(output_dir, output_root=output_root)
    report = load_rawprep_benchmark_report(output_dir, output_root=output_root)
    return packet, review, report


def _build_default_decision(
    packet: RawPrepBenchmarkPacket,
    review: RawPrepBenchmarkReleaseReview,
    report: RawPrepBenchmarkReport,
    *,
    output_dir: str,
    output_root: str,
) -> RawPrepBenchmarkDefaultDecision:
    benchmark_evidence_ready = (
        packet.benchmark_status == "measured"
        and packet.foundation_status == "measured_ready"
        and review.benchmark_report_status == "measured"
    )
    release_promotion_ready = review.ready_for_human_review

    rationale = [
        f"SingleRaw measured coverage는 {report.dataset_overview.get('single_raw_measured_sample_count', 0)}/{report.dataset_overview.get('single_raw_sample_count', 0)}이다.",
        f"TriRaw measured coverage는 {report.dataset_overview.get('tri_raw_measured_sample_count', 0)}개 sample, {len(report.dataset_overview.get('tri_raw_measured_bucket_ids', []))}/{report.dataset_overview.get('tri_raw_bucket_count', 0)}개 bucket이다.",
        f"Local smoke 상태는 end-to-end={packet.local_e2e_smoke_status}, recovery={packet.local_recovery_smoke_status}, ui-language={packet.local_ui_language_smoke_status}이다.",
        f"RunPod smoke 상태는 {review.runpod_smoke_status}이다.",
    ]
    blockers = [issue.code for issue in review.blockers]

    if not benchmark_evidence_ready:
        status = "benchmark_evidence_incomplete"
        promotion_recommendation = "collect_more_benchmark_evidence"
        summary = "Measured benchmark evidence is not complete enough to judge default-engine promotion yet."
    elif review.runpod_smoke_status != "passed":
        status = "hold_runpod_smoke_pending"
        promotion_recommendation = "hold_default_promotion"
        summary = "Benchmark evidence is ready, but default-engine promotion should stay on hold until BUILD_MANUAL RunPod smoke evidence is attached."
    elif release_promotion_ready:
        status = "ready_for_default_review"
        promotion_recommendation = "ready_for_human_default_review"
        summary = "Benchmark evidence and RunPod smoke evidence are ready; human default-engine review can proceed."
    else:
        status = "hold_review_pending"
        promotion_recommendation = "hold_default_promotion"
        summary = "Benchmark evidence exists, but additional release review work is still required before promoting v2 by default."

    recommended_actions = _dedupe_actions(packet.recommended_actions + review.recommended_actions)

    return RawPrepBenchmarkDefaultDecision(
        output_dir=output_dir,
        output_root=output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        promotion_recommendation=promotion_recommendation,
        benchmark_evidence_ready=benchmark_evidence_ready,
        release_promotion_ready=release_promotion_ready,
        summary=summary,
        decision_path=str(_decision_path(output_dir, output_root=output_root)),
        benchmark_report_path=packet.benchmark_report_path,
        release_packet_path=packet.packet_path,
        release_review_path=review.review_path,
        benchmark_status=packet.benchmark_status,
        foundation_status=packet.foundation_status,
        benchmark_report_status=review.benchmark_report_status,
        release_gate_status=packet.release_gate_status,
        release_review_status=packet.release_review_status,
        runpod_smoke_status=review.runpod_smoke_status,
        local_e2e_smoke_status=packet.local_e2e_smoke_status,
        local_recovery_smoke_status=packet.local_recovery_smoke_status,
        local_ui_language_smoke_status=packet.local_ui_language_smoke_status,
        single_raw_sample_count=report.dataset_overview.get("single_raw_sample_count", 0),
        single_raw_measured_sample_count=report.dataset_overview.get("single_raw_measured_sample_count", 0),
        tri_raw_bucket_count=report.dataset_overview.get("tri_raw_bucket_count", 0),
        tri_raw_measured_sample_count=report.dataset_overview.get("tri_raw_measured_sample_count", 0),
        tri_raw_measured_bucket_ids=list(report.dataset_overview.get("tri_raw_measured_bucket_ids", [])),
        compare_decision_count=packet.compare_decision_count,
        single_raw_timing_ms_mean=report.single_raw_summary.get("timing_ms_mean"),
        tri_raw_timing_ms_mean=report.tri_raw_summary.get("timing_ms_mean"),
        blockers=blockers,
        rationale=rationale,
        recommended_actions=recommended_actions,
    )


def build_rawprep_benchmark_default_decision(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkDefaultDecision:
    packet, review, report = _load_decision_inputs(output_dir, output_root=output_root)
    return _build_default_decision(packet, review, report, output_dir=output_dir, output_root=output_root)


def write_rawprep_benchmark_default_decision(
    request: RawPrepBenchmarkDefaultDecisionRequest,
) -> RawPrepBenchmarkDefaultDecision:
    write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir=request.output_dir,
            output_root=request.output_root,
            label=request.label,
        )
    )
    packet, review, report = _load_decision_inputs(request.output_dir, output_root=request.output_root)
    decision = _build_default_decision(packet, review, report, output_dir=request.output_dir, output_root=request.output_root)
    path = _decision_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


def load_rawprep_benchmark_default_decision(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkDefaultDecision:
    path = _decision_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark default decision artifact was not found: {path}")
    return RawPrepBenchmarkDefaultDecision(**json.loads(path.read_text(encoding="utf-8")))
