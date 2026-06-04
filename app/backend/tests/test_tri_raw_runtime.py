import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import tifffile

import app.raw_engine_v2.tri_raw.runtime as tri_raw_runtime
from app.raw_engine_v2.tri_raw.planner import build_tri_raw_foundation_plan, materialize_tri_raw_foundation_plan
from app.raw_engine_v2.tri_raw.runtime import materialize_tri_raw_preview_runtime


def _write_bracket_preview(path: Path, *, base_color: tuple[int, int, int], overlay_shift: int = 0) -> None:
    image = Image.new("RGB", (180, 120), base_color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((18 + overlay_shift, 18, 78 + overlay_shift, 66), fill=(245, 210, 160))
    draw.rectangle((104 - overlay_shift, 34, 156 - overlay_shift, 94), fill=(46, 62, 128))
    image.save(path, format="JPEG", quality=95)


def _write_piecewise_shift_preview(
    path: Path,
    *,
    base_color: tuple[int, int, int],
    left_shift: int = 0,
    right_shift: int = 0,
) -> None:
    image = Image.new("RGB", (180, 120), base_color)
    draw = ImageDraw.Draw(image)
    left_box = (18 + left_shift, 18, 78 + left_shift, 66)
    right_box = (104 + right_shift, 34, 156 + right_shift, 94)
    draw.rectangle(left_box, fill=(245, 210, 160))
    draw.rectangle(right_box, fill=(46, 62, 128))
    for x in range(int(left_box[0]) + 6, int(left_box[2]), 12):
        draw.line((x, left_box[1], x, left_box[3]), fill=(120, 82, 40), width=2)
    for y in range(int(left_box[1]) + 6, int(left_box[3]), 12):
        draw.line((left_box[0], y, left_box[2], y), fill=(255, 236, 196), width=1)
    for x in range(int(right_box[0]) + 4, int(right_box[2]), 10):
        draw.line((x, right_box[1], x, right_box[3]), fill=(220, 228, 255), width=2)
    for offset in range(0, int(right_box[2] - right_box[0]), 14):
        draw.line(
            (
                right_box[0] + offset,
                right_box[1],
                min(right_box[0] + offset + 18, right_box[2]),
                right_box[3],
            ),
            fill=(18, 28, 72),
            width=2,
        )
    image.save(path, format="JPEG", quality=95)


def test_materialize_tri_raw_preview_runtime_writes_confidence_and_fallback_diagnostics(tmp_path):
    raw_paths = []
    base_colors = [(82, 74, 70), (122, 110, 102), (168, 154, 142)]
    for index, base_color in enumerate(base_colors):
        raw_path = tmp_path / f"frame_{index + 1:03d}.dng"
        raw_path.write_bytes(b"raw")
        _write_bracket_preview(raw_path.with_suffix(".jpg"), base_color=base_color, overlay_shift=index * 3)
        raw_paths.append(str(raw_path))

    plan = materialize_tri_raw_foundation_plan(
        build_tri_raw_foundation_plan(
            raw_paths,
            bracket_id="bracket_demo",
            session_root=tmp_path / "outputs" / "session_demo",
        )
    )

    result = materialize_tri_raw_preview_runtime(plan)

    assert result is not None
    assert Path(result.preview_path).is_file()
    assert Path(result.scene_linear_path).is_file()
    assert Path(result.motion_map_path).is_file()
    assert Path(result.confidence_map_path).is_file()
    assert Path(result.confidence_preview_path).is_file()
    assert Path(result.ghost_risk_map_path).is_file()
    assert Path(result.highlight_map_path).is_file()
    assert Path(result.shadow_map_path).is_file()
    assert Path(result.deghost_mask_path).is_file()
    assert Path(result.hdr_gain_map_path).is_file()
    assert Path(result.noise_suppression_map_path).is_file()
    assert Path(result.alignment_offset_map_path).is_file()
    assert Path(result.alignment_residual_map_path).is_file()
    assert Path(result.alignment_vector_field_path).is_file()
    assert Path(result.alignment_refinement_map_path).is_file()
    assert Path(result.frontier_eval_path).is_file()
    assert result.learned_adapter["status"] == "disabled"
    assert any(entry["label"] == "best_single" for entry in result.candidate_scores)
    assert result.frontier_eval["eval_id"] == "tri_raw_frontier_eval_v1"
    assert result.frontier_eval["status"] == "measured"
    assert result.frontier_eval["recommended_label"] == result.recommended_label
    assert result.frontier_eval["axis_scores"]["evidence_completeness"] == 1.0
    assert "score_delta_vs_baseline" in result.frontier_eval
    assert result.fallback_strategy["selected_action"] in {
        "reference_frame_holdout",
        "guarded_fusion_holdout",
        "exposure_fusion_merge",
    }
    assert result.confidence_summary["mean_confidence"] >= 0.0
    assert result.alignment_summary["backend"] == "phase_correlation_piecewise_preview_offsets_v2"
    assert result.joint_denoise_summary["strategy"] == "preview_noise_aware_joint_denoise_v1"
    assert result.deghost_summary["strategy"] in {
        "reference_holdout_masked_fusion",
        "low_motion_guided_merge",
    }
    assert result.deghost_summary["alignment_refinement_backend"] == "prior_residual_refinement_bridge_v1"
    assert result.hdr_summary["strategy"] == "preview_exposure_fusion_bridge"

    diagnostics_payload = json.loads(Path(result.diagnostics_manifest_path).read_text(encoding="utf-8"))
    diagnostic_keys = {item["key"] for item in diagnostics_payload["diagnostics"]}
    assert {"confidence_preview", "ghost_risk_map", "highlight_map", "shadow_map", "deghost_mask", "hdr_gain_map", "noise_suppression_map", "alignment_offset_map", "alignment_residual_map", "alignment_vector_field", "alignment_refinement_map"} <= diagnostic_keys
    assert "frontier_eval" in diagnostic_keys
    assert "learned_adapter_output" in diagnostic_keys
    assert diagnostics_payload["frontier_eval"]["eval_id"] == "tri_raw_frontier_eval_v1"
    assert diagnostics_payload["learned_adapter"]["status"] == "disabled"
    confidence_map = tifffile.imread(Path(result.confidence_map_path))
    assert confidence_map.shape == (120, 180)
    assert str(confidence_map.dtype) == "float32"
    alignment_vector_field = tifffile.imread(Path(result.alignment_vector_field_path))
    assert alignment_vector_field.shape == (3, 120, 180, 2)
    assert str(alignment_vector_field.dtype) == "float32"
    assert result.alignment_vector_summary["layout"] == "frame,y,x,xy"
    assert result.alignment_refinement_summary["backend"] == "prior_residual_refinement_bridge_v1"
    assert diagnostics_payload["fallback_strategy"]["selected_action"] == result.fallback_strategy["selected_action"]
    assert diagnostics_payload["alignment_summary"]["backend"] == result.alignment_summary["backend"]
    assert diagnostics_payload["alignment_vector_summary"]["layout"] == result.alignment_vector_summary["layout"]
    assert diagnostics_payload["alignment_refinement_summary"]["backend"] == result.alignment_refinement_summary["backend"]
    assert diagnostics_payload["joint_denoise_summary"]["strategy"] == result.joint_denoise_summary["strategy"]
    assert diagnostics_payload["deghost_summary"]["strategy"] == result.deghost_summary["strategy"]
    assert diagnostics_payload["hdr_summary"]["strategy"] == result.hdr_summary["strategy"]


def test_materialize_tri_raw_preview_runtime_uses_guarded_fusion_for_motion_heavy_preview_brackets(tmp_path):
    raw_paths = []
    base_colors = [(72, 66, 60), (126, 118, 108), (170, 160, 148)]
    overlay_shifts = [0, 36, 6]
    for index, (base_color, shift) in enumerate(zip(base_colors, overlay_shifts)):
        raw_path = tmp_path / f"motion_{index + 1:03d}.dng"
        raw_path.write_bytes(b"raw")
        _write_bracket_preview(raw_path.with_suffix(".jpg"), base_color=base_color, overlay_shift=shift)
        raw_paths.append(str(raw_path))

    plan = materialize_tri_raw_foundation_plan(
        build_tri_raw_foundation_plan(
            raw_paths,
            bracket_id="motion_bracket",
            session_root=tmp_path / "outputs" / "session_demo",
            metadata_payloads=[
                {"ExposureTime": "1/80", "ISO": 400},
                {"ExposureTime": "1/20", "ISO": 400},
                {"ExposureTime": "1/5", "ISO": 400},
            ],
        )
    )

    result = materialize_tri_raw_preview_runtime(plan)

    assert result is not None
    assert result.recommended_label == "hybrid"
    assert result.fallback_reason == "motion_guard"
    assert result.fallback_strategy["selected_action"] == "guarded_fusion_holdout"
    assert result.alignment_summary["has_nonzero_offsets"] is True
    assert any(abs(frame.get("dx", 0)) > 0 or abs(frame.get("dy", 0)) > 0 for frame in result.alignment_summary["frames"])
    assert result.alignment_summary["piecewise_local_alignment"]["active_frame_count"] >= 0
    assert result.confidence_summary["reference_holdout_coverage"] > 0.0
    assert result.joint_denoise_summary["strong_suppression_coverage"] >= 0.0
    assert result.deghost_summary["holdout_coverage"] > 0.0
    assert result.hdr_summary["hdr_worth_it"] is True


def test_materialize_tri_raw_preview_runtime_reports_piecewise_local_alignment(tmp_path):
    raw_paths = []
    preview_specs = [
        {"base_color": (88, 82, 78), "left_shift": 0, "right_shift": 0},
        {"base_color": (126, 118, 110), "left_shift": 0, "right_shift": 14},
        {"base_color": (160, 150, 142), "left_shift": -8, "right_shift": 0},
    ]
    for index, spec in enumerate(preview_specs):
        raw_path = tmp_path / f"piecewise_{index + 1:03d}.dng"
        raw_path.write_bytes(b"raw")
        _write_piecewise_shift_preview(raw_path.with_suffix(".jpg"), **spec)
        raw_paths.append(str(raw_path))

    plan = materialize_tri_raw_foundation_plan(
        build_tri_raw_foundation_plan(
            raw_paths,
            bracket_id="piecewise_bracket",
            session_root=tmp_path / "outputs" / "session_demo",
            metadata_payloads=[
                {"ExposureTime": "1/60", "ISO": 320},
                {"ExposureTime": "1/15", "ISO": 320},
                {"ExposureTime": "1/4", "ISO": 320},
            ],
        )
    )

    result = materialize_tri_raw_preview_runtime(plan, requested_reference_policy="first")

    assert result is not None
    assert result.alignment_summary["backend"] == "phase_correlation_piecewise_preview_offsets_v2"
    assert result.alignment_summary["piecewise_local_alignment"]["active_frame_count"] >= 1
    assert result.alignment_summary["piecewise_local_alignment"]["max_local_offset"] >= 1.0
    assert Path(result.alignment_offset_map_path).is_file()
    assert Path(result.alignment_residual_map_path).is_file()
    assert Path(result.alignment_vector_field_path).is_file()
    assert Path(result.alignment_refinement_map_path).is_file()
    assert result.alignment_vector_summary["frame_count"] == 3
    assert result.alignment_guard_summary["guarded_merge_required"] is True
    assert result.alignment_guard_summary["severity"] in {"medium", "high"}
    assert result.alignment_refinement_summary["guarded_holdout_coverage"] > 0.0
    assert "alignment_guard_holdout" in result.fallback_strategy["triggered_rules"]
    candidate_scores = {entry["label"]: entry for entry in result.candidate_scores}
    assert candidate_scores["merged"]["score_components"]["alignment_guard_penalty"] > 0.0
    assert candidate_scores["hybrid"]["score_components"]["alignment_guard_bonus"] >= 0.0
    assert candidate_scores["hybrid"]["total_score"] >= candidate_scores["merged"]["total_score"]
    non_reference_frames = [frame for frame in result.alignment_summary["frames"] if not frame.get("is_reference")]
    assert any(int((frame.get("local_alignment") or {}).get("active_tile_count") or 0) >= 1 for frame in non_reference_frames)


def test_select_recommended_candidate_prefers_alignment_guard_before_full_merge():
    recommended_label, fallback_reason = tri_raw_runtime._select_recommended_candidate(
        ev_span=2.4,
        motion_coverage=0.04,
        alignment_guard_summary={
            "guarded_merge_required": True,
            "pressure_score": 0.61,
            "primary_signal": "piecewise_local_offsets",
        },
    )

    assert recommended_label == "hybrid"
    assert fallback_reason == "alignment_guard"


def test_alignment_guard_summary_marks_piecewise_residual_pressure():
    alignment_summary = {
        "max_offset": 6.5,
        "piecewise_local_alignment": {
            "active_frame_count": 2,
            "max_local_offset": 8.0,
        },
    }
    alignment_vector_field = np.zeros((3, 12, 16, 2), dtype=np.float32)
    alignment_vector_field[1, :, :, 0] = 2.0
    alignment_vector_field[2, 3:9, 4:12, 1] = -1.5
    alignment_vector_summary = {
        "max_abs_dx": 2.0,
        "max_abs_dy": 1.5,
    }
    alignment_residual = np.zeros((12, 16), dtype=np.float32)
    alignment_residual[2:10, 3:13] = 0.72

    summary = tri_raw_runtime._alignment_guard_summary(
        alignment_summary=alignment_summary,
        alignment_vector_field=alignment_vector_field,
        alignment_vector_summary=alignment_vector_summary,
        alignment_residual=alignment_residual,
    )

    assert summary["guarded_merge_required"] is True
    assert summary["severity"] in {"medium", "high"}
    assert summary["primary_signal"] in {"residual_hotspots", "piecewise_local_offsets"}
    assert summary["pressure_score"] > 0.0


def test_alignment_refinement_bridge_marks_holdout_hotspots():
    alignment_vector_field = np.zeros((3, 12, 16, 2), dtype=np.float32)
    alignment_vector_field[1, 2:10, 3:13, 0] = 1.8
    alignment_residual = np.zeros((12, 16), dtype=np.float32)
    alignment_residual[1:11, 4:12] = 0.74
    confidence_map = np.full((12, 16), 0.82, dtype=np.float32)
    confidence_map[2:10, 5:11] = 0.28
    ghost_risk_map = np.zeros((12, 16), dtype=np.float32)
    ghost_risk_map[3:9, 4:12] = 0.66

    refinement_map, summary = tri_raw_runtime._alignment_refinement_bridge(
        alignment_vector_field=alignment_vector_field,
        alignment_residual=alignment_residual,
        confidence_map=confidence_map,
        ghost_risk_map=ghost_risk_map,
    )

    assert refinement_map.shape == (12, 16)
    assert refinement_map.dtype == np.float32
    assert summary["backend"] == "prior_residual_refinement_bridge_v1"
    assert summary["guides_guarded_fusion"] is True
    assert summary["hotspot_coverage"] > 0.0
    assert summary["guarded_holdout_coverage"] > 0.0
