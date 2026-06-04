from app.core.runpod_model_bootstrap_contract import (
    build_runpod_model_bootstrap_contract,
    load_runpod_model_bootstrap_contract,
    write_runpod_model_bootstrap_contract,
)


def test_build_runpod_model_bootstrap_contract_defaults_to_lazy_on_demand(tmp_path):
    contract = build_runpod_model_bootstrap_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        comfy_root=tmp_path / "workspace" / "runpod-slim" / "ComfyUI",
        artifact_path=tmp_path / "runpod_model_bootstrap_contract.json",
    )

    assert contract.ok is True
    assert contract.download_scope_status == "lazy_on_demand"
    assert contract.selected_model_sets == []
    assert contract.checks.ephemeral_session_policy_recorded is True


def test_write_runpod_model_bootstrap_contract_records_requested_sets(tmp_path):
    comfy_root = tmp_path / "workspace" / "runpod-slim" / "ComfyUI"
    (comfy_root / "models").mkdir(parents=True, exist_ok=True)
    artifact_path = tmp_path / "runpod_model_bootstrap_contract.json"

    contract = write_runpod_model_bootstrap_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        comfy_root=comfy_root,
        download_qwen=True,
        download_fill=True,
        artifact_path=artifact_path,
    )
    loaded = load_runpod_model_bootstrap_contract(artifact_path)

    assert artifact_path.exists()
    assert contract.download_scope_status == "requested_only"
    assert contract.selected_model_sets == ["qwen", "fill"]
    assert loaded.selected_download_flags == ["--download-qwen", "--download-fill"]


def test_build_runpod_model_bootstrap_contract_records_frontier_profile(tmp_path):
    contract = build_runpod_model_bootstrap_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        comfy_root=tmp_path / "workspace" / "runpod-slim" / "ComfyUI",
        model_profile="frontier",
        artifact_path=tmp_path / "runpod_model_bootstrap_contract.json",
    )

    assert contract.ok is True
    assert contract.download_scope_status == "profile:frontier"
    assert contract.model_profile == "frontier"
    assert "birefnet_dis5k" in contract.selected_model_sets
    assert "qwen_image_2512" in contract.selected_model_sets
    assert "qwen_judge" in contract.selected_model_sets
    assert "qwen_layered" in contract.selected_model_sets
    assert "longcat_image_edit_turbo" not in contract.selected_model_sets
    assert "longcat_image_edit_turbo" in contract.frontier_research_model_sets
    assert contract.profile_metadata is not None
    assert contract.profile_metadata.min_vram_class == "48GB"
    assert contract.template_policy.image_primary == "runpod/comfyui:1.4.1-cuda12.8"
    assert contract.template_policy.recommended_gpu_server == "RTX PRO 6000"
    assert contract.template_policy.container_disk_gb == 80
    assert contract.template_policy.volume_disk_default_gb == 400
    assert contract.template_policy.volume_disk_full_frontier_qwen_gb == 500
    assert contract.template_policy.network_volume_policy == "disabled_by_default"
    assert contract.template_policy.prewarmed_image_candidate is None
    assert contract.template_policy.prewarmed_build_artifacts["dockerfile"] == "runpod/prewarm/Dockerfile.runtime"
    assert any("no HF_TOKEN" in item for item in contract.template_policy.prewarmed_content_scope)
    assert "DC_ENABLE_LABS" not in contract.template_policy.required_env
    assert any("runtime-prewarmed" in item for item in contract.recommended_actions)


def test_build_runpod_model_bootstrap_contract_maps_legacy_profiles_to_frontier(tmp_path):
    contract = build_runpod_model_bootstrap_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        comfy_root=tmp_path / "workspace" / "runpod-slim" / "ComfyUI",
        model_profile="labs",
        artifact_path=tmp_path / "runpod_model_bootstrap_contract.json",
    )

    assert contract.ok is True
    assert contract.model_profile == "frontier"
    assert contract.legacy_profile_alias == "labs"
    assert contract.download_scope_status == "profile:frontier"
    assert any("mapped to the single Frontier" in item for item in contract.recommended_actions)


def test_build_runpod_model_bootstrap_contract_marks_download_all_scope(tmp_path):
    contract = build_runpod_model_bootstrap_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        comfy_root=tmp_path / "workspace" / "runpod-slim" / "ComfyUI",
        download_all=True,
        artifact_path=tmp_path / "runpod_model_bootstrap_contract.json",
    )

    assert contract.download_scope_status == "download_all"
    assert contract.checks.download_all_requested is True
    assert contract.selected_model_sets == [
        "birefnet_dis5k",
        "qwen",
        "qwen_image_2512",
        "qwen_judge",
        "flux2_dev",
        "klein",
        "fill",
        "qwen_layered",
        "z_image_turbo",
        "omnigen2",
    ]
    assert any("download_all selected" in item for item in contract.recommended_actions)
