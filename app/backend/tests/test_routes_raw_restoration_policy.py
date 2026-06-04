from fastapi.testclient import TestClient

from app.api.main import app


def test_rawprep_restoration_goals_are_manifest_backed_policy():
    client = TestClient(app)
    response = client.get("/api/rawprep/restoration-goals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "raw_restoration_policy_v1"
    assert payload["contract_id"] == "tri_raw_frontier_v1"
    assert payload["default_goal"] == "truth_preserving"
    assert payload["source_manifest"].endswith("app\\models\\model_manifest.yaml") or payload["source_manifest"].endswith(
        "app/models/model_manifest.yaml"
    )

    options = {item["id"]: item for item in payload["options"]}
    assert set(options) == {"truth_preserving", "aggressive_restore"}
    assert options["truth_preserving"]["delivery_default"] is True
    assert options["truth_preserving"]["label"] == "진실 보존"
    assert "고스팅" in options["truth_preserving"]["summary"]
    assert options["truth_preserving"]["requires_human_review"] is False
    assert options["aggressive_restore"]["label"] == "공격적 복원 후보"
    assert "검수" in options["aggressive_restore"]["summary"]
    assert options["aggressive_restore"]["requires_human_review"] is True
    assert "golden_session_runner" in options["aggressive_restore"]["review_gates"]
