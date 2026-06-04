from __future__ import annotations

from pathlib import Path
from typing import Any


TRI_RAW_FRONTIER_EVAL_ID = "tri_raw_frontier_eval_v1"


def _float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _candidate_score(candidate_scores: list[dict[str, Any]], label: str) -> tuple[float, dict[str, Any]]:
    for entry in candidate_scores:
        if entry.get("label") != label:
            continue
        value = entry.get("total_score")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value), entry
    return 0.0, {}


def _artifact_exists(path_value: str | None) -> bool:
    if not path_value:
        return False
    try:
        return Path(path_value).is_file()
    except OSError:
        return False


def _evidence_summary(artifact_paths: dict[str, str | None]) -> dict[str, Any]:
    required = {
        "merged_hdr_path",
        "denoised_result_path",
        "confidence_map_path",
        "ghost_risk_map_path",
        "alignment_vector_field_path",
    }
    checks = {
        key: {
            "path": artifact_paths.get(key),
            "required": key in required,
            "exists": _artifact_exists(artifact_paths.get(key)),
        }
        for key in sorted(artifact_paths)
    }
    missing_required = [key for key in sorted(required) if not checks.get(key, {}).get("exists")]
    return {
        "complete": not missing_required,
        "missing_required": missing_required,
        "checks": checks,
    }


def _axis_scores(
    *,
    recommended_candidate: dict[str, Any],
    confidence_summary: dict[str, Any],
    joint_denoise_summary: dict[str, Any],
    deghost_summary: dict[str, Any],
    hdr_summary: dict[str, Any],
    alignment_guard_summary: dict[str, Any],
    alignment_refinement_summary: dict[str, Any],
    fallback_strategy: dict[str, Any],
    evidence_complete: bool,
) -> dict[str, float]:
    recommended_components = recommended_candidate.get("score_components")
    if not isinstance(recommended_components, dict):
        recommended_components = {}

    mean_confidence = _float(confidence_summary, "mean_confidence", 0.0)
    high_confidence_coverage = _float(confidence_summary, "high_confidence_coverage", 0.0)
    alignment_pressure = _float(alignment_guard_summary, "pressure_score", 0.0)
    residual_hotspots = _float(alignment_guard_summary, "residual_hotspot_coverage", 0.0)
    alignment_confidence = _clip(
        (mean_confidence * 0.72)
        + (high_confidence_coverage * 0.18)
        + ((1.0 - alignment_pressure) * 0.10)
        - (residual_hotspots * 0.08)
    )

    ghost_risk = _float(confidence_summary, "ghost_risk_coverage", _float(deghost_summary, "ghost_risk_coverage", 0.0))
    holdout_coverage = _float(deghost_summary, "holdout_coverage", 0.0)
    refinement_holdout = _float(alignment_refinement_summary, "guarded_holdout_coverage", 0.0)
    ghost_control = _clip(
        1.0
        - (ghost_risk * 0.55)
        - (alignment_pressure * 0.16)
        + (holdout_coverage * 0.16)
        + (refinement_holdout * 0.10)
    )

    mean_suppression = _float(joint_denoise_summary, "mean_suppression", 0.0)
    strong_suppression = _float(joint_denoise_summary, "strong_suppression_coverage", 0.0)
    detail_component = _float(recommended_components, "detail_component", 0.0)
    denoise_detail_tradeoff = _clip(
        (detail_component * 0.54)
        + (min(mean_suppression * 2.4, 1.0) * 0.28)
        + ((1.0 - abs(strong_suppression - 0.18)) * 0.18)
        - max(0.0, strong_suppression - 0.48) * 0.22
    )

    ev_span = _float(hdr_summary, "ev_span", 0.0)
    hdr_gain = _float(hdr_summary, "hdr_gain_coverage", 0.0)
    highlight_recovery = _float(hdr_summary, "highlight_recovery_coverage", 0.0)
    shadow_lift = _float(hdr_summary, "shadow_lift_coverage", 0.0)
    hdr_expected = 1.0 if ev_span >= 1.2 else 0.58
    hdr_recovery = _clip(
        ((min(ev_span / 2.4, 1.0) * 0.24) + (hdr_gain * 0.34) + (highlight_recovery * 0.22) + (shadow_lift * 0.20))
        / hdr_expected
    )

    selected_action = str(fallback_strategy.get("selected_action") or "")
    triggered_rules = fallback_strategy.get("triggered_rules")
    if not isinstance(triggered_rules, list):
        triggered_rules = []
    unsafe_full_merge = selected_action == "exposure_fusion_merge" and (
        ghost_risk >= 0.20 or alignment_pressure >= 0.48 or "low_confidence_guard" in triggered_rules
    )
    fallback_safety = _clip(
        (0.88 if selected_action in {"reference_frame_holdout", "guarded_fusion_holdout"} else 0.74)
        + (0.10 if triggered_rules else 0.0)
        - (0.36 if unsafe_full_merge else 0.0)
        - (0.12 if mean_confidence < 0.50 else 0.0)
    )

    evidence_completeness = 1.0 if evidence_complete else 0.35

    return {
        "alignment_confidence": round(alignment_confidence, 4),
        "ghost_control": round(ghost_control, 4),
        "denoise_detail_tradeoff": round(denoise_detail_tradeoff, 4),
        "hdr_recovery": round(hdr_recovery, 4),
        "fallback_safety": round(fallback_safety, 4),
        "evidence_completeness": round(evidence_completeness, 4),
    }


def _weighted_total(axis_scores: dict[str, float]) -> float:
    weights = {
        "alignment_confidence": 0.20,
        "ghost_control": 0.20,
        "denoise_detail_tradeoff": 0.18,
        "hdr_recovery": 0.18,
        "fallback_safety": 0.14,
        "evidence_completeness": 0.10,
    }
    total = sum(axis_scores[key] * weight for key, weight in weights.items())
    return round(_clip(total), 4)


def _decision(
    *,
    evidence_complete: bool,
    recommended_label: str,
    score_delta_vs_baseline: float,
    total_score: float,
    axis_scores: dict[str, float],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not evidence_complete:
        reasons.append("required_evidence_missing")
        return "evidence_incomplete", reasons

    if axis_scores["ghost_control"] < 0.48:
        reasons.append("ghost_control_low")
    if axis_scores["alignment_confidence"] < 0.48:
        reasons.append("alignment_confidence_low")
    if axis_scores["denoise_detail_tradeoff"] < 0.45:
        reasons.append("denoise_detail_tradeoff_low")
    if axis_scores["hdr_recovery"] < 0.35:
        reasons.append("hdr_gain_limited")

    if recommended_label == "best_single" and score_delta_vs_baseline <= 0.02:
        reasons.append("reference_frame_remains_best")
        return "baseline_preferred", reasons

    if score_delta_vs_baseline >= 0.04 and total_score >= 0.62 and not reasons[:2]:
        reasons.append("frontier_candidate_beats_reference_score")
        return "frontier_candidate_improved", reasons

    if score_delta_vs_baseline >= -0.02 and total_score >= 0.58:
        reasons.append("frontier_candidate_safe_but_needs_visual_review")
        return "frontier_candidate_acceptable", reasons

    reasons.append("frontier_candidate_needs_more_evidence")
    return "inconclusive", reasons


def build_tri_raw_frontier_eval(
    *,
    frame_count: int,
    recommended_label: str,
    candidate_scores: list[dict[str, Any]],
    confidence_summary: dict[str, Any],
    joint_denoise_summary: dict[str, Any],
    deghost_summary: dict[str, Any],
    hdr_summary: dict[str, Any],
    alignment_guard_summary: dict[str, Any],
    alignment_refinement_summary: dict[str, Any],
    fallback_strategy: dict[str, Any],
    capture_summary: dict[str, Any],
    artifact_paths: dict[str, str | None],
) -> dict[str, Any]:
    baseline_score, baseline_candidate = _candidate_score(candidate_scores, "best_single")
    recommended_score, recommended_candidate = _candidate_score(candidate_scores, recommended_label)
    merged_score, _ = _candidate_score(candidate_scores, "merged")
    hybrid_score, _ = _candidate_score(candidate_scores, "hybrid")
    evidence = _evidence_summary(artifact_paths)
    axis_scores = _axis_scores(
        recommended_candidate=recommended_candidate,
        confidence_summary=confidence_summary,
        joint_denoise_summary=joint_denoise_summary,
        deghost_summary=deghost_summary,
        hdr_summary=hdr_summary,
        alignment_guard_summary=alignment_guard_summary,
        alignment_refinement_summary=alignment_refinement_summary,
        fallback_strategy=fallback_strategy,
        evidence_complete=bool(evidence["complete"]),
    )
    total_score = _weighted_total(axis_scores)
    score_delta = round(recommended_score - baseline_score, 4)
    decision, reasons = _decision(
        evidence_complete=bool(evidence["complete"]),
        recommended_label=recommended_label,
        score_delta_vs_baseline=score_delta,
        total_score=total_score,
        axis_scores=axis_scores,
    )
    return {
        "eval_id": TRI_RAW_FRONTIER_EVAL_ID,
        "status": "measured",
        "frame_count": frame_count,
        "baseline_label": "best_single",
        "recommended_label": recommended_label,
        "decision": decision,
        "improved_over_baseline": decision == "frontier_candidate_improved",
        "needs_visual_review": decision in {"frontier_candidate_acceptable", "inconclusive"},
        "decision_reasons": reasons,
        "total_score": total_score,
        "axis_scores": axis_scores,
        "score_delta_vs_baseline": score_delta,
        "candidate_scores": {
            "best_single": round(baseline_score, 4),
            "merged": round(merged_score, 4),
            "hybrid": round(hybrid_score, 4),
            recommended_label: round(recommended_score, 4),
        },
        "baseline_candidate": baseline_candidate,
        "recommended_candidate": recommended_candidate,
        "evidence": evidence,
        "inputs": {
            "capture_summary": capture_summary,
            "confidence_summary": confidence_summary,
            "joint_denoise_summary": joint_denoise_summary,
            "deghost_summary": deghost_summary,
            "hdr_summary": hdr_summary,
            "alignment_guard_summary": alignment_guard_summary,
            "alignment_refinement_summary": alignment_refinement_summary,
            "fallback_strategy": fallback_strategy,
        },
    }
