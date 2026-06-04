import json
from pathlib import Path

from app.core.runpod_bootstrap_summary import build_runpod_bootstrap_summary, write_runpod_bootstrap_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_runpod_bootstrap_summary_embeds_contract_checks(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    runtime_root = app_root / "app" / "runtime"
    workflow_dir = app_root / "app" / "workflows" / "runtime"
    summary_path = runtime_root / "bootstrap_summary.json"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "flow.json").write_text("{}", encoding="utf-8")

    _write_json(runtime_root / "rawprep_healthcheck.json", {"ok": True})
    _write_json(runtime_root / "single_raw_healthcheck.json", {"ok": True})
    _write_json(runtime_root / "runpod_storage_contract.json", {"ok": True})
    _write_json(runtime_root / "runpod_model_bootstrap_contract.json", {"ok": True, "selected_model_sets": ["qwen"]})
    _write_json(runtime_root / "runpod_custom_node_contract.json", {"ok": True, "custom_nodes": [{"name": "node-a"}]})

    summary = build_runpod_bootstrap_summary(
        summary_path=summary_path,
        workflow_dir=workflow_dir,
        rawprep_healthcheck_path=runtime_root / "rawprep_healthcheck.json",
        single_raw_healthcheck_path=runtime_root / "single_raw_healthcheck.json",
        backend_url="http://127.0.0.1:8000/health",
        comfy_root=workspace_root / "runpod-slim" / "ComfyUI",
        comfy_python="python",
        console_label="ComfyUI - CUDA 13",
        primary_image="runpod/comfyui:cuda13.0",
        fallback_pinned_image="runpod/comfyui:1.3.0-cuda12.8",
        fallback_alias_image="runpod/comfyui:latest",
        storage_contract_path=runtime_root / "runpod_storage_contract.json",
        model_bootstrap_contract_path=runtime_root / "runpod_model_bootstrap_contract.json",
        custom_node_contract_path=runtime_root / "runpod_custom_node_contract.json",
    )

    assert summary["checks"]["storage_layout_ok"] is True
    assert summary["checks"]["model_selection_recorded"] is True
    assert summary["checks"]["custom_node_runtime_valid"] is True
    assert summary["workflow_files"] == ["flow.json"]


def test_write_runpod_bootstrap_summary_round_trip(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    runtime_root = app_root / "app" / "runtime"
    workflow_dir = app_root / "app" / "workflows" / "runtime"
    summary_path = runtime_root / "bootstrap_summary.json"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "flow.json").write_text("{}", encoding="utf-8")

    _write_json(runtime_root / "rawprep_healthcheck.json", {"ok": True})
    _write_json(runtime_root / "single_raw_healthcheck.json", {"ok": True})
    _write_json(runtime_root / "runpod_storage_contract.json", {"ok": True})
    _write_json(runtime_root / "runpod_model_bootstrap_contract.json", {"ok": False})
    _write_json(runtime_root / "runpod_custom_node_contract.json", {"ok": False})

    payload = write_runpod_bootstrap_summary(
        summary_path=summary_path,
        workflow_dir=workflow_dir,
        rawprep_healthcheck_path=runtime_root / "rawprep_healthcheck.json",
        single_raw_healthcheck_path=runtime_root / "single_raw_healthcheck.json",
        backend_url="http://127.0.0.1:8000/health",
        comfy_root=workspace_root / "runpod-slim" / "ComfyUI",
        comfy_python="python",
        console_label="ComfyUI - CUDA 13",
        primary_image="runpod/comfyui:cuda13.0",
        fallback_pinned_image="runpod/comfyui:1.3.0-cuda12.8",
        fallback_alias_image="runpod/comfyui:latest",
        storage_contract_path=runtime_root / "runpod_storage_contract.json",
        model_bootstrap_contract_path=runtime_root / "runpod_model_bootstrap_contract.json",
        custom_node_contract_path=runtime_root / "runpod_custom_node_contract.json",
    )

    loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["checks"]["model_selection_recorded"] is False
    assert loaded["checks"]["custom_node_runtime_valid"] is False
    assert loaded["app_root"] == str(app_root.resolve())
