from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app


def make_rgb_image(path: Path, color: tuple[int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 96), color).save(path)
    return str(path)


def make_mask_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (128, 96), 0)
    for x in range(22, 104):
        for y in range(18, 80):
            mask.putpixel((x, y), 220)
    mask.save(path)
    return str(path)


def test_selection_apply_route_persists_state(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (188, 154, 130))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_01" / "subject__mask.png")

    response = client.post(
        "/api/studio/selection/apply",
        json={
            "session_id": session_id,
            "output_root": str(output_root),
            "source_mask_path": source_mask_path,
            "source_asset_path": source_asset_path,
            "controls": {
                "threshold": 110,
                "expand_pixels": 3,
                "feather_radius": 5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["controls"]["expand_pixels"] == 3
    assert payload["coverage_ratio"] > 0.10
    assert Path(payload["preview_path"]).is_file()

    fetch_response = client.get(
        "/api/studio/selection",
        params={"session_id": session_id, "output_root": str(output_root)},
    )
    assert fetch_response.status_code == 200
    fetch_payload = fetch_response.json()
    assert fetch_payload["state_path"] == payload["state_path"]
    assert fetch_payload["current_mask_path"] == payload["current_mask_path"]


def test_selection_apply_route_reports_empty_selection(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (188, 154, 130))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_01" / "subject__mask.png")

    response = client.post(
        "/api/studio/selection/apply",
        json={
            "session_id": session_id,
            "output_root": str(output_root),
            "source_mask_path": source_mask_path,
            "source_asset_path": source_asset_path,
            "controls": {
                "threshold": 255,
                "expand_pixels": -32,
                "feather_radius": 0,
            },
        },
    )

    assert response.status_code == 400
    assert "선택 범위가 너무 작습니다" in response.json()["detail"]
