from fastapi.testclient import TestClient

from app.api.main import app


def test_runpod_model_profiles_endpoint_exposes_single_frontier_profile(monkeypatch):
    monkeypatch.delenv("DC_MODEL_PROFILE", raising=False)
    client = TestClient(app)
    response = client.get("/api/runpod/model-profiles")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_profile"] == "frontier"
    assert [profile["profile_id"] for profile in payload["profiles"]] == ["frontier"]
    frontier_profile = payload["profiles"][0]
    assert frontier_profile["min_vram_class"] == "48GB"
    assert any(item["model_set_id"] == "qwen_image_2512" for item in frontier_profile["model_sets"])
    longcat = next(item for item in payload["available_model_sets"] if item["model_set_id"] == "longcat_image_edit_turbo")
    assert longcat["integration_status"] == "workflow_needed"


def test_runpod_template_policy_endpoint_exposes_ephemeral_template_contract(monkeypatch):
    for key in (
        "RUNPOD_TEMPLATE_PRIMARY_IMAGE",
        "RUNPOD_TEMPLATE_FALLBACK_ALIAS",
        "RUNPOD_TEMPLATE_PREWARMED_IMAGE",
        "DC_SERVE_FRONTEND",
        "DC_MODEL_PROFILE",
    ):
        monkeypatch.delenv(key, raising=False)
    client = TestClient(app)
    response = client.get("/api/runpod/template-policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["image_primary"] == "runpod/comfyui:1.4.1-cuda12.8"
    assert payload["compatibility_alias"] == "runpod/comfyui:cuda12.8"
    assert payload["storage_policy"] == "ephemeral_session_local"
    assert payload["recommended_gpu_server"] == "RTX PRO 6000"
    assert payload["recommended_gpu_vram"] == "96GB"
    assert payload["container_disk_gb"] == 80
    assert payload["volume_disk_default_gb"] == 400
    assert payload["volume_disk_full_frontier_qwen_gb"] == 500
    assert payload["network_volume_policy"] == "disabled_by_default"
    assert payload["persistent_model_cache_policy"] == "disabled"
    assert payload["long_term_outputs_policy"] == "external_or_local_only"
    assert payload["prewarmed_image_candidate"] is None
    assert payload["prewarmed_build_artifacts"]["dockerfile"] == "runpod/prewarm/Dockerfile.runtime"
    assert any("no HF_TOKEN" in item for item in payload["prewarmed_content_scope"])
    assert payload["ports"]["studio"] == "8000/http"
    assert payload["required_env"]["DC_MODEL_PROFILE"] == "frontier"
    assert payload["required_env"]["DC_SERVE_FRONTEND"] == "1"
    assert "DC_ENABLE_LABS" not in payload["required_env"]


def test_runpod_template_policy_records_private_prewarmed_image_candidate(monkeypatch):
    monkeypatch.setenv("RUNPOD_TEMPLATE_PREWARMED_IMAGE", "registry.example/dreamcatcher:runtime-v1")
    client = TestClient(app)
    response = client.get("/api/runpod/template-policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["image_primary"] == "runpod/comfyui:1.4.1-cuda12.8"
    assert payload["prewarmed_image_candidate"] == "registry.example/dreamcatcher:runtime-v1"
    assert "DreamCatcher.zip remains the source of truth" in payload["prewarmed_image_policy"]


def test_runpod_bootstrap_session_endpoint_requires_output_recovery_before_termination(monkeypatch):
    monkeypatch.delenv("DC_MODEL_PROFILE", raising=False)
    client = TestClient(app)
    response = client.get("/api/runpod/bootstrap-session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "ephemeral_zip_pod"
    assert payload["default_profile"] == "frontier"
    assert "Full Frontier" in payload["frontier_bootstrap_scope"]
    assert any("RTX PRO 6000" in item for item in payload["startup_policy"])
    assert any("volume disk to 400GB" in item for item in payload["startup_policy"])
    assert any("Network Volume disabled" in item for item in payload["startup_policy"])
    assert any("/workspace/DreamCatcher/outputs" in item for item in payload["end_of_session_policy"])
    assert any("Stop and terminate" in item for item in payload["end_of_session_policy"])
