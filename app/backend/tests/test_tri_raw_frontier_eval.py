from pathlib import Path

from app.raw_engine_v2.tri_raw.frontier_eval import build_tri_raw_frontier_eval


def _artifact_paths(tmp_path: Path) -> dict[str, str]:
    paths: dict[str, str] = {}
    for key in (
        "merged_hdr_path",
        "denoised_result_path",
        "confidence_map_path",
        "ghost_risk_map_path",
        "alignment_vector_field_path",
    ):
        path = tmp_path / f"{key}.bin"
        path.write_bytes(b"ok")
        paths[key] = str(path)
    return paths


def test_build_tri_raw_frontier_eval_marks_improved_candidate(tmp_path):
    payload = build_tri_raw_frontier_eval(
        frame_count=3,
        recommended_label="merged",
        candidate_scores=[
            {"label": "best_single", "total_score": 0.58, "score_components": {"detail_component": 0.72}},
            {"label": "merged", "total_score": 0.68, "score_components": {"detail_component": 0.76}},
            {"label": "hybrid", "total_score": 0.64, "score_components": {"detail_component": 0.74}},
        ],
        confidence_summary={"mean_confidence": 0.82, "high_confidence_coverage": 0.68, "ghost_risk_coverage": 0.03},
        joint_denoise_summary={"mean_suppression": 0.18, "strong_suppression_coverage": 0.12},
        deghost_summary={"holdout_coverage": 0.04, "ghost_risk_coverage": 0.03},
        hdr_summary={
            "ev_span": 2.1,
            "hdr_gain_coverage": 0.34,
            "highlight_recovery_coverage": 0.28,
            "shadow_lift_coverage": 0.21,
        },
        alignment_guard_summary={"pressure_score": 0.08, "residual_hotspot_coverage": 0.0},
        alignment_refinement_summary={"guarded_holdout_coverage": 0.0},
        fallback_strategy={"selected_action": "exposure_fusion_merge", "triggered_rules": ["full_merge_allowed"]},
        capture_summary={"ev_span": 2.1},
        artifact_paths=_artifact_paths(tmp_path),
    )

    assert payload["eval_id"] == "tri_raw_frontier_eval_v1"
    assert payload["decision"] == "frontier_candidate_improved"
    assert payload["improved_over_baseline"] is True
    assert payload["score_delta_vs_baseline"] == 0.1
    assert payload["axis_scores"]["evidence_completeness"] == 1.0


def test_build_tri_raw_frontier_eval_keeps_baseline_when_frontier_is_not_better(tmp_path):
    payload = build_tri_raw_frontier_eval(
        frame_count=3,
        recommended_label="best_single",
        candidate_scores=[
            {"label": "best_single", "total_score": 0.62, "score_components": {"detail_component": 0.70}},
            {"label": "merged", "total_score": 0.56, "score_components": {"detail_component": 0.58}},
            {"label": "hybrid", "total_score": 0.60, "score_components": {"detail_component": 0.62}},
        ],
        confidence_summary={"mean_confidence": 0.58, "high_confidence_coverage": 0.31, "ghost_risk_coverage": 0.18},
        joint_denoise_summary={"mean_suppression": 0.08, "strong_suppression_coverage": 0.02},
        deghost_summary={"holdout_coverage": 0.18, "ghost_risk_coverage": 0.18},
        hdr_summary={
            "ev_span": 0.8,
            "hdr_gain_coverage": 0.02,
            "highlight_recovery_coverage": 0.02,
            "shadow_lift_coverage": 0.01,
        },
        alignment_guard_summary={"pressure_score": 0.20, "residual_hotspot_coverage": 0.06},
        alignment_refinement_summary={"guarded_holdout_coverage": 0.05},
        fallback_strategy={"selected_action": "reference_frame_holdout", "triggered_rules": ["narrow_bracket_holdout"]},
        capture_summary={"ev_span": 0.8},
        artifact_paths=_artifact_paths(tmp_path),
    )

    assert payload["decision"] == "baseline_preferred"
    assert payload["improved_over_baseline"] is False
    assert "reference_frame_remains_best" in payload["decision_reasons"]


def test_build_tri_raw_frontier_eval_blocks_quality_claim_when_evidence_is_missing(tmp_path):
    paths = _artifact_paths(tmp_path)
    Path(paths["confidence_map_path"]).unlink()

    payload = build_tri_raw_frontier_eval(
        frame_count=3,
        recommended_label="merged",
        candidate_scores=[
            {"label": "best_single", "total_score": 0.50, "score_components": {"detail_component": 0.60}},
            {"label": "merged", "total_score": 0.72, "score_components": {"detail_component": 0.78}},
        ],
        confidence_summary={"mean_confidence": 0.90, "high_confidence_coverage": 0.80, "ghost_risk_coverage": 0.01},
        joint_denoise_summary={"mean_suppression": 0.18, "strong_suppression_coverage": 0.10},
        deghost_summary={"holdout_coverage": 0.02, "ghost_risk_coverage": 0.01},
        hdr_summary={
            "ev_span": 2.4,
            "hdr_gain_coverage": 0.40,
            "highlight_recovery_coverage": 0.35,
            "shadow_lift_coverage": 0.22,
        },
        alignment_guard_summary={"pressure_score": 0.04, "residual_hotspot_coverage": 0.0},
        alignment_refinement_summary={"guarded_holdout_coverage": 0.0},
        fallback_strategy={"selected_action": "exposure_fusion_merge", "triggered_rules": ["full_merge_allowed"]},
        capture_summary={"ev_span": 2.4},
        artifact_paths=paths,
    )

    assert payload["decision"] == "evidence_incomplete"
    assert payload["axis_scores"]["evidence_completeness"] == 0.35
    assert payload["evidence"]["missing_required"] == ["confidence_map_path"]
