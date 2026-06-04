import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.runpod_storage_contract import (
    build_runpod_storage_contract,
    load_runpod_storage_contract,
    write_runpod_storage_contract,
)


def test_build_runpod_storage_contract_reports_separated_roots(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    contract = build_runpod_storage_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=workspace_root / "runpod-slim" / "ComfyUI",
        hf_home=workspace_root / ".cache" / "huggingface",
        bootstrap_cache_root=workspace_root / ".dreamcatcher_cache",
        workflow_runtime_root=app_root / "app" / "workflows" / "runtime",
        workflow_staging_root=app_root / "seed_bundle" / "staging_templates",
        rawprep_root=workspace_root / "rawprep",
        rawprep_tmp_root=workspace_root / ".rawprep_tmp",
        output_root=app_root / "outputs",
        artifact_path=app_root / "app" / "runtime" / "runpod_storage_contract.json",
    )

    assert contract.ok is True
    assert contract.checks.model_cache_location_clear is True
    assert contract.checks.workflow_cache_location_clear is True
    assert contract.checks.session_output_location_clear is True
    assert contract.checks.outputs_not_mixed_with_cache is True
    assert contract.checks.outputs_vs_model_cache is True
    assert contract.checks.outputs_vs_workflow_runtime is True


def test_write_and_load_runpod_storage_contract_round_trip(tmp_path):
    artifact_path = tmp_path / "runpod_storage_contract.json"

    written = write_runpod_storage_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        output_root=tmp_path / "workspace" / "DreamCatcher" / "outputs",
        artifact_path=artifact_path,
    )
    loaded = load_runpod_storage_contract(artifact_path)

    assert artifact_path.exists()
    assert loaded.ok is True
    assert loaded.artifact_path == str(artifact_path.resolve())
    assert loaded.output_root == written.output_root


def test_storage_contract_route_reports_current_layout(tmp_path, monkeypatch):
    client = TestClient(app)
    workspace_root = tmp_path / "workspace"
    output_root = workspace_root / "DreamCatcher" / "outputs"
    monkeypatch.setenv("HF_HOME", str(workspace_root / ".cache" / "huggingface"))
    monkeypatch.setenv("RAWPREP_ROOT", str(workspace_root / "rawprep"))
    monkeypatch.setenv("RAWPREP_TMP", str(workspace_root / ".rawprep_tmp"))

    response = client.get(
        "/api/studio/ops/storage-contract",
        params={"output_root": str(output_root)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["outputs_not_mixed_with_cache"] is True
    assert payload["output_root"] == str(output_root.resolve())


def test_bootstrap_summary_can_embed_storage_contract_snapshot(tmp_path):
    artifact_path = tmp_path / "runpod_storage_contract.json"
    contract = write_runpod_storage_contract(
        workspace_root=tmp_path / "workspace",
        app_root=tmp_path / "workspace" / "DreamCatcher",
        output_root=tmp_path / "workspace" / "DreamCatcher" / "outputs",
        artifact_path=artifact_path,
    )

    payload = json.loads(Path(contract.artifact_path).read_text(encoding="utf-8"))

    assert payload["ok"] is True
    assert payload["checks"]["outputs_not_mixed_with_cache"] is True
