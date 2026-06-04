from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app


def make_compare_image(path: Path, *, brightness: float, warmth: float = 0.0, saturation_boost: float = 0.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 144, 96
    ramp = np.tile(np.linspace(20, 235, width, dtype=np.float32), (height, 1))
    red = np.clip(ramp * brightness + (warmth * 40.0), 0, 255)
    green = np.clip(ramp * brightness + (saturation_boost * 10.0), 0, 255)
    blue = np.clip(ramp * brightness - (warmth * 40.0) - (saturation_boost * 18.0), 0, 255)
    rgb = np.stack([red, green, blue], axis=2).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(path)
    return str(path)


def test_compare_advice_flags_practical_risks(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    primary = make_compare_image(session_root / "select.png", brightness=0.86)
    candidate = make_compare_image(
        session_root / "candidate.png",
        brightness=1.18,
        warmth=0.55,
        saturation_boost=0.7,
    )

    response = client.post(
        "/api/studio/compare/advice",
        json={
            "output_root": str(output_root),
            "primary_path": primary,
            "candidate_path": candidate,
            "tool": "retouch",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "retouch"
    assert payload["risk_level"] in {"medium", "high"}
    assert payload["signals"]
    assert any("하이라이트" in signal["title"] or "노출" in signal["title"] for signal in payload["signals"])
    assert "대안 후보" in payload["summary"]
    assert payload["prior_guardrails"]
    assert any("Frontier" in guardrail for guardrail in payload["prior_guardrails"])
    assert payload["priority_dimensions"]


def test_compare_advice_rejects_non_images(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    text_path = session_root / "not_an_image.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text("not an image", encoding="utf-8")

    response = client.post(
        "/api/studio/compare/advice",
        json={
            "output_root": str(output_root),
            "primary_path": str(text_path),
            "candidate_path": str(text_path),
        },
    )

    assert response.status_code == 400
    assert "읽지 못했습니다" in response.json()["detail"]


def test_compare_decision_records_winner(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    primary = make_compare_image(session_root / "select.png", brightness=0.9)
    candidate = make_compare_image(session_root / "candidate.png", brightness=1.04, warmth=0.2)

    response = client.post(
        "/api/studio/compare/decision",
        json={
            "session_id": "session_demo",
            "output_root": str(output_root),
            "tool": "retouch",
            "primary_path": primary,
            "candidate_path": candidate,
            "winner_path": candidate,
            "action": "accept_candidate",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["winner_role"] == "candidate"
    assert payload["winner_path"] == candidate

    decision_dir = output_root / "session_demo" / "04_compare" / "decisions"
    assert any(path.name.startswith("compare_decision_") for path in decision_dir.glob("*.json"))
    aggregate_path = output_root / "_compare_learning" / "compare_decisions.jsonl"
    assert aggregate_path.exists()


def test_compare_advice_includes_motion_watch_context(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    primary = make_compare_image(session_root / "select.png", brightness=0.92)
    candidate = make_compare_image(session_root / "scene_base_16.png", brightness=1.06, warmth=0.18)
    overlay = make_compare_image(session_root / "scene_motion_overlay.jpg", brightness=0.78, saturation_boost=0.15)

    response = client.post(
        "/api/studio/compare/advice",
        json={
            "output_root": str(output_root),
            "primary_path": primary,
            "candidate_path": candidate,
            "tool": "compare",
            "motion_overlay_path": overlay,
            "motion_overlay_summary": "Motion watch highlights active motion zones.",
            "motion_overlay_coverage": 0.14,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["motion_watch"] is not None
    assert payload["motion_watch"]["path"] == overlay
    assert payload["motion_watch"]["summary"] == "Motion watch highlights active motion zones."
    assert payload["motion_watch"]["compares_overlay"] is False
    assert any("움직임" in signal["title"] for signal in payload["signals"])


def test_compare_advice_marks_overlay_as_diagnostic(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo" / "02_manual"
    primary = make_compare_image(session_root / "select.png", brightness=0.9)
    overlay = make_compare_image(session_root / "scene_motion_overlay.jpg", brightness=0.82)

    response = client.post(
        "/api/studio/compare/advice",
        json={
            "output_root": str(output_root),
            "primary_path": primary,
            "candidate_path": overlay,
            "tool": "compare",
            "motion_overlay_path": overlay,
            "motion_overlay_summary": "Overlay is active.",
            "motion_overlay_coverage": 0.09,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["motion_watch"] is not None
    assert payload["motion_watch"]["compares_overlay"] is True
    assert any("진단" in signal["title"] for signal in payload["signals"])
