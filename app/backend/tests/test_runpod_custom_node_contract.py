import json
from pathlib import Path

import yaml

from app.core.runpod_custom_node_contract import (
    build_runpod_custom_node_contract,
    load_runpod_custom_node_contract,
    write_runpod_custom_node_contract,
)


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "custom_nodes": [
                    {
                        "name": "Test Node Pack",
                        "repo": "https://github.com/example/ComfyUI-Test-Pack.git",
                        "required_for": ["테스트"],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_runtime_workflow(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "TestNode",
                    "inputs": {},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_object_info(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "TestNode": {
                    "input": {
                        "required": {},
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_runpod_custom_node_contract_reports_valid_runtime(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    comfy_root = workspace_root / "runpod-slim" / "ComfyUI"
    manifest_path = app_root / "app" / "custom_nodes" / "custom_node_manifest.yaml"
    object_info_path = app_root / "app" / "runtime" / "object_info.json"
    workflow_root = app_root / "app" / "workflows" / "runtime"
    custom_node_dir = comfy_root / "custom_nodes" / "ComfyUI-Test-Pack"
    custom_node_dir.mkdir(parents=True, exist_ok=True)

    _write_manifest(manifest_path)
    _write_object_info(object_info_path)
    _write_runtime_workflow(workflow_root / "test.json")

    contract = build_runpod_custom_node_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=comfy_root,
        manifest_path=manifest_path,
        object_info_path=object_info_path,
        workflow_root=workflow_root,
        artifact_path=app_root / "app" / "runtime" / "runpod_custom_node_contract.json",
    )

    assert contract.ok is True
    assert contract.checks.required_node_dirs_present is True
    assert contract.checks.runtime_workflows_valid is True
    assert contract.workflow_validations[0].ok is True


def test_write_runpod_custom_node_contract_round_trip(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    comfy_root = workspace_root / "runpod-slim" / "ComfyUI"
    manifest_path = app_root / "app" / "custom_nodes" / "custom_node_manifest.yaml"
    object_info_path = app_root / "app" / "runtime" / "object_info.json"
    workflow_root = app_root / "app" / "workflows" / "runtime"
    artifact_path = app_root / "app" / "runtime" / "runpod_custom_node_contract.json"
    (comfy_root / "custom_nodes" / "ComfyUI-Test-Pack").mkdir(parents=True, exist_ok=True)

    _write_manifest(manifest_path)
    _write_object_info(object_info_path)
    _write_runtime_workflow(workflow_root / "test.json")

    written = write_runpod_custom_node_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=comfy_root,
        manifest_path=manifest_path,
        object_info_path=object_info_path,
        workflow_root=workflow_root,
        artifact_path=artifact_path,
    )
    loaded = load_runpod_custom_node_contract(artifact_path)

    assert artifact_path.exists()
    assert written.ok is True
    assert loaded.custom_nodes[0].name == "Test Node Pack"


def test_build_runpod_custom_node_contract_reports_missing_node_dir(tmp_path):
    workspace_root = tmp_path / "workspace"
    app_root = workspace_root / "DreamCatcher"
    comfy_root = workspace_root / "runpod-slim" / "ComfyUI"
    manifest_path = app_root / "app" / "custom_nodes" / "custom_node_manifest.yaml"
    object_info_path = app_root / "app" / "runtime" / "object_info.json"
    workflow_root = app_root / "app" / "workflows" / "runtime"

    _write_manifest(manifest_path)
    _write_object_info(object_info_path)
    _write_runtime_workflow(workflow_root / "test.json")

    contract = build_runpod_custom_node_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=comfy_root,
        manifest_path=manifest_path,
        object_info_path=object_info_path,
        workflow_root=workflow_root,
        artifact_path=app_root / "app" / "runtime" / "runpod_custom_node_contract.json",
    )

    assert contract.ok is False
    assert contract.checks.required_node_dirs_present is False
    assert any("커스텀 노드 디렉터리" in issue for issue in contract.issues)
