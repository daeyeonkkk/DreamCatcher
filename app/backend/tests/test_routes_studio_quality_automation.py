from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app


def make_quality_image(path: Path, *, brightness: float, warmth: float = 0.0, flat: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 144, 96
    if flat:
        ramp = np.full((height, width), 128, dtype=np.float32)
    else:
        ramp = np.tile(np.linspace(20, 235, width, dtype=np.float32), (height, 1))
    red = np.clip(ramp * brightness + warmth * 42.0, 0, 255)
    green = np.clip(ramp * brightness, 0, 255)
    blue = np.clip(ramp * brightness - warmth * 42.0, 0, 255)
    rgb = np.stack([red, green, blue], axis=2).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(path)
    return str(path)


def make_quality_textured_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 144, 96
    yy, xx = np.mgrid[0:height, 0:width]
    pattern = 128 + 44 * np.sin(xx / 2.5) + 34 * np.cos(yy / 3.0)
    red = np.clip(pattern + 4, 0, 255)
    green = np.clip(pattern, 0, 255)
    blue = np.clip(pattern - 4, 0, 255)
    rgb = np.stack([red, green, blue], axis=2).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(path)
    return str(path)


def test_quality_automation_policy_disables_cloud_fallback():
    client = TestClient(app)
    response = client.get("/api/studio/quality-automation/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "quality_automation_v2"
    assert payload["qwen_judge_schema_version"] == "qwen_judge_signal_v2"
    assert payload["judge_evidence_packet_schema_version"] == "judge_evidence_packet_v1"
    assert payload["golden_calibration_version"] == "golden_calibration_v1"
    assert payload["primary_local_model"] == "Qwen3.6-35B-A3B-FP8"
    assert payload["primary_local_repo"] == "Qwen/Qwen3.6-35B-A3B-FP8"
    assert payload["cloud_fallback_enabled"] is False
    assert "qwen_vlm_judge" in payload["runtime_layers"]
    assert "axis_scoring" in payload["automation_allowed"]
    assert "evidence_packet_enrichment" in payload["automation_allowed"]
    assert "golden_score_calibration" in payload["automation_allowed"]
    assert "correction_plan" in payload["qwen_response_required_keys"]
    assert "auto_apply_code_change" in payload["automation_blocked"]


def test_quality_assessment_fuses_qwen_judge_and_metrics(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    reference = make_quality_image(session_root / "reference.png", brightness=0.86)
    result = make_quality_image(session_root / "result.png", brightness=1.25, warmth=0.55)

    response = client.post(
        "/api/studio/quality-automation/assess",
        json={
            "output_root": str(output_root),
            "session_id": "session_demo",
            "tool": "retouch",
            "reference_path": reference,
            "result_path": result,
            "task_intent": "Reduce blemishes while preserving natural skin texture.",
            "operation_context": {"edit_strength": 0.48, "denoise": "texture_preserving"},
            "user_preference_evidence": {"accepted_style": "natural editorial skin"},
            "qwen_judge_signal": {
                "schema_version": "qwen_judge_signal_v2",
                "verdict": "suspicious",
                "confidence": 0.62,
                "axis_scores": {
                    "intent_match": 0.88,
                    "technical_quality": 0.71,
                    "aesthetic_quality": 0.65,
                    "subject_preservation": 0.82,
                    "mask_boundary": 0.74,
                    "color_naturalness": 0.42,
                },
                "failure_tags": ["skin_tone_shift"],
                "localized_issues": [
                    {
                        "area": "skin",
                        "issue_type": "color_shift",
                        "severity": "warning",
                        "description": "Skin tone moved too warm versus the reference.",
                        "confidence": 0.77,
                        "bbox_norm": [0.2, 0.1, 0.5, 0.6],
                        "suggested_action": "Lock neutral skin tones before retry.",
                    }
                ],
                "correction_plan": {
                    "temperature_delta": -8,
                    "tint_delta": 3,
                    "saturation_delta": -6,
                    "edit_strength": 0.45,
                    "notes": "Use a conservative color-preservation pass.",
                },
                "retry_instruction": "Retry with color preservation and lower edit strength.",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_local_model"] == "Qwen3.6-35B-A3B-FP8"
    assert payload["cloud_fallback_enabled"] is False
    assert payload["version"] == "quality_automation_v2"
    assert payload["qwen_judge_schema_version"] == "qwen_judge_signal_v2"
    assert payload["qwen_judge_signal"]["axis_scores"]["color_naturalness"] == 0.42
    assert payload["qwen_judge_signal"]["localized_issues"][0]["issue_type"] == "color_shift"
    assert payload["qwen_judge_signal"]["correction_plan"]["temperature_delta"] == -8.0
    assert payload["judge_evidence_packet"]["schema_version"] == "judge_evidence_packet_v1"
    assert payload["judge_evidence_packet"]["operation_context"]["edit_strength"] == 0.48
    assert payload["judge_evidence_packet"]["user_preference_evidence"]["accepted_style"] == "natural editorial skin"
    assert payload["judge_evidence_packet"]["golden_context"]["profile_id"] == "frontier_retouch"
    assert payload["golden_calibration"]["schema_version"] == "golden_calibration_v1"
    assert payload["golden_calibration"]["profile_id"] == "frontier_retouch"
    assert payload["golden_calibration"]["applied"] is True
    assert payload["verdict"] in {"fail", "suspicious"}
    assert payload["human_approval_required"] is True
    assert "golden_calibration_applied" in payload["human_review_reason"]
    assert "skin_tone_shift" in payload["failure_tags"]
    assert "color_shift" in payload["failure_tags"]
    assert any("Draft correction plan" in item for item in payload["work_instructions"])
    assert payload["retry_plan"]["retry_allowed"] is True
    assert payload["code_tuning_gate"]["automatic_code_change"] is False
    assert Path(payload["artifact_path"]).exists()


def test_quality_assessment_pass_can_continue_with_sampling_note(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    result = make_quality_textured_image(session_root / "result.png")

    response = client.post(
        "/api/studio/quality-automation/assess",
        json={
            "output_root": str(output_root),
            "session_id": "session_demo",
            "tool": "compare",
            "result_path": result,
            "qwen_judge_signal": {
                "verdict": "pass",
                "confidence": 0.91,
                "axis_scores": {
                    "intent_match": 0.93,
                    "technical_quality": 0.9,
                    "aesthetic_quality": 0.88,
                    "subject_preservation": 0.95,
                    "mask_boundary": 0.92,
                    "color_naturalness": 0.9,
                },
                "failure_tags": [],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "pass"
    assert payload["human_approval_required"] is False
    assert "sample_passes_for_human_audit" in payload["human_review_reason"]
    assert payload["golden_calibration"]["calibrated_verdict"] == "pass"
    assert payload["retry_plan"]["retry_allowed"] is False


def test_quality_assessment_live_qwen_requires_local_judge(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    result = make_quality_image(session_root / "result.png", brightness=0.9)
    monkeypatch.setenv("DC_QWEN_JUDGE_BASE_URL", "http://127.0.0.1:9/v1")

    response = client.post(
        "/api/studio/quality-automation/assess",
        json={
            "output_root": str(output_root),
            "session_id": "session_demo",
            "tool": "compare",
            "result_path": result,
            "run_qwen_judge": True,
        },
    )

    assert response.status_code == 503
    assert "Qwen judge request failed" in response.json()["detail"]


def test_quality_tuning_proposal_is_proposal_only(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    reference = make_quality_image(session_root / "reference.png", brightness=0.88)
    result = make_quality_image(session_root / "result.png", brightness=1.22, warmth=0.5, flat=True)

    assessment_response = client.post(
        "/api/studio/quality-automation/assess",
        json={
            "output_root": str(output_root),
            "session_id": "session_demo",
            "tool": "enhance",
            "reference_path": reference,
            "result_path": result,
            "qwen_judge_signal": {
                "verdict": "fail",
                "confidence": 0.81,
                "axis_scores": {
                    "intent_match": 0.8,
                    "technical_quality": 0.32,
                    "aesthetic_quality": 0.44,
                    "subject_preservation": 0.7,
                    "mask_boundary": 0.7,
                    "color_naturalness": 0.38,
                },
                "failure_tags": ["detail_loss", "color_shift"],
            },
        },
    )
    assessment = assessment_response.json()

    response = client.post(
        "/api/studio/quality-automation/tuning/proposal",
        json={
            "output_root": str(output_root),
            "session_id": "session_demo",
            "assessment_paths": [assessment["artifact_path"]],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "quality_tuning_loop_v1"
    assert payload["automatic_code_tuning_enabled"] is False
    assert payload["human_approval_required"] is True
    assert payload["source_assessment_count"] == 1
    assert payload["failure_clusters"]["detail_loss"] >= 1
    assert "apply_code_without_human_approval" in payload["blocked_actions"]
    assert payload["golden_runner_plan"]["required_before_merge"] is True
    assert Path(payload["artifact_path"]).exists()
