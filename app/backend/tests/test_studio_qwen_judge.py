import json
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.studio_quality_automation import apply_golden_calibration, build_judge_evidence_packet
from app.core.studio_qwen_judge import _coerce_json_object, _normalize_signal


REPO_ROOT = Path(__file__).resolve().parents[3]


def make_judge_test_image(path: Path, *, flat: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 96, 64
    if flat:
        ramp = np.full((height, width), 128, dtype=np.float32)
    else:
        ramp = np.tile(np.linspace(24, 232, width, dtype=np.float32), (height, 1))
    rgb = np.stack([ramp + 2, ramp, ramp - 2], axis=2).clip(0, 255).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(path)
    return str(path)


def test_qwen_judge_v2_normalizes_nested_response_contract():
    payload = {
        "schema_version": "qwen_judge_signal_v2",
        "verdict": "FAIL",
        "confidence": 1.8,
        "axis_scores": {
            "intent_match": 0.92,
            "technical_quality": "-0.5",
            "aesthetic_quality": 0.61,
            "subject_preservation": 0.84,
            "mask_boundary": 0.3,
            "color_naturalness": 0.42,
        },
        "failure_tags": ["Skin Tone Shift", " mask boundary failure "],
        "localized_issues": [
            {
                "area": "skin",
                "issue_type": "Color Shift",
                "severity": "critical",
                "description": "Skin tone moved too warm.",
                "confidence": "0.76",
                "bbox_norm": [0.1, -1.0, 1.4, 0.5],
                "suggested_action": "Lock neutral skin tones.",
            },
            {"area": "", "issue_type": "ignored", "description": "missing area"},
        ],
        "correction_plan": {
            "exposure_delta": 9,
            "temperature_delta": -12,
            "tint_delta": "4",
            "denoise_strength": 1.5,
            "edit_strength": 0.45,
            "crop_box_norm": [0.0, 0.1, 0.8, 0.7],
            "notes": "Use a conservative retry.",
        },
        "rationale": "Obvious color cast and boundary damage.",
        "retry_instruction": "Retry with lower edit strength.",
        "work_instruction": "Inspect at 100 percent crop.",
    }

    signal = _normalize_signal(payload)

    assert signal.schema_version == "qwen_judge_signal_v2"
    assert signal.verdict == "fail"
    assert signal.confidence == 1.0
    assert signal.axis_scores.intent_match == 0.92
    assert signal.axis_scores.technical_quality == 0.0
    assert signal.failure_tags == ["skin_tone_shift", "mask_boundary_failure"]
    assert len(signal.localized_issues) == 1
    assert signal.localized_issues[0].issue_type == "color_shift"
    assert signal.localized_issues[0].bbox_norm == [0.1, 0.0, 1.0, 0.5]
    assert signal.correction_plan.exposure_delta == 3.0
    assert signal.correction_plan.temperature_delta == -12.0
    assert signal.correction_plan.denoise_strength == 1.0
    assert signal.correction_plan.crop_box_norm == [0.0, 0.1, 0.8, 0.7]


def test_qwen_judge_json_coercion_accepts_markdown_fenced_json():
    text = """```json
    {"verdict": "pass", "confidence": 0.9, "failure_tags": []}
    ```"""

    assert _coerce_json_object(text)["verdict"] == "pass"


def test_qwen_judge_v2_schema_artifact_is_shipped_with_seed_bundle():
    schema_path = REPO_ROOT / "seed_bundle" / "runtime_priors" / "evaluator" / "qwen_judge_signal_v2.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$id"] == "dreamcatcher.qwen_judge_signal_v2"
    assert "axis_scores" in schema["required"]
    assert "localized_issues" in schema["required"]
    assert "correction_plan" in schema["required"]
    assert schema["properties"]["schema_version"]["const"] == "qwen_judge_signal_v2"


def test_quality_evidence_and_calibration_schema_artifacts_are_shipped_with_seed_bundle():
    evaluator_root = REPO_ROOT / "seed_bundle" / "runtime_priors" / "evaluator"
    evidence_schema = json.loads((evaluator_root / "judge_evidence_packet_v1.schema.json").read_text(encoding="utf-8"))
    calibration_schema = json.loads((evaluator_root / "golden_calibration_v1.schema.json").read_text(encoding="utf-8"))
    calibration_seed = json.loads((evaluator_root / "golden_quality_calibration.seed.json").read_text(encoding="utf-8"))

    assert evidence_schema["$id"] == "dreamcatcher.judge_evidence_packet_v1"
    assert evidence_schema["properties"]["schema_version"]["const"] == "judge_evidence_packet_v1"
    assert "golden_context" in evidence_schema["required"]
    assert calibration_schema["$id"] == "dreamcatcher.golden_calibration_v1"
    assert calibration_schema["properties"]["schema_version"]["const"] == "golden_calibration_v1"
    assert calibration_seed["schema_version"] == "golden_quality_calibration_seed_v1"


def test_judge_evidence_packet_carries_metrics_context_and_golden_rubric(tmp_path):
    output_root = tmp_path / "outputs"
    result = make_judge_test_image(output_root / "session" / "result.png")

    packet = build_judge_evidence_packet(
        result_path=result,
        output_root=str(output_root),
        tool="retouch",
        task_intent="Keep skin natural while reducing blemishes.",
        operation_context={"edit_strength": 0.42, "denoise": "conservative"},
        user_preference_evidence={"accepted_style": "natural skin texture"},
    )

    assert packet.schema_version == "judge_evidence_packet_v1"
    assert packet.tool == "retouch"
    assert packet.task_intent.startswith("Keep skin")
    assert "deterministic_metrics" in packet.available_evidence
    assert packet.operation_context["edit_strength"] == 0.42
    assert packet.user_preference_evidence["accepted_style"] == "natural skin texture"
    assert packet.golden_context["profile_id"] == "frontier_retouch"
    assert "highlight_clip_ratio" in packet.metric_units


def test_golden_calibration_demotes_overconfident_pass_when_required_evidence_is_missing(tmp_path):
    output_root = tmp_path / "outputs"
    result = make_judge_test_image(output_root / "session" / "result.png")
    packet = build_judge_evidence_packet(
        result_path=result,
        output_root=str(output_root),
        tool="removeBg",
        task_intent="Remove the background without damaging hair.",
    )
    signal = _normalize_signal(
        {
            "verdict": "pass",
            "confidence": 0.95,
            "axis_scores": {
                "intent_match": 0.9,
                "technical_quality": 0.9,
                "aesthetic_quality": 0.88,
                "subject_preservation": 0.92,
                "mask_boundary": 0.91,
                "color_naturalness": 0.86,
            },
            "failure_tags": [],
        }
    )

    calibration = apply_golden_calibration(
        qwen_judge_signal=signal,
        judge_evidence_packet=packet,
        metric_signals=[],
    )

    assert calibration.applied is True
    assert calibration.profile_id == "frontier_mask_edit"
    assert calibration.calibrated_verdict == "suspicious"
    assert calibration.calibrated_confidence == 0.68
    assert "missing_required_evidence" in calibration.added_failure_tags
