from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml

from .preflight_validator import validate_workflow


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _default_workspace_root() -> Path:
    return _resolve_path("/workspace")


def _default_app_root(workspace_root: Path) -> Path:
    return _resolve_path(workspace_root / "DreamCatcher")


def _default_comfy_root() -> Path:
    return _resolve_path("/workspace/runpod-slim/ComfyUI")


def _repo_dir_from_url(repo: str) -> str:
    name = repo.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


class RunPodCustomNodeEntry(BaseModel):
    name: str
    repo: str
    ref: str | None = None
    target_dir: str
    required_for: list[str] = Field(default_factory=list)
    target_exists: bool = False
    notes: str | None = None


class RunPodWorkflowValidation(BaseModel):
    workflow_path: str
    ok: bool = False
    errors: list[str] = Field(default_factory=list)


class RunPodCustomNodeChecks(BaseModel):
    manifest_present: bool = False
    object_info_present: bool = False
    workflow_files_present: bool = False
    required_node_dirs_present: bool = False
    runtime_workflows_valid: bool = False


class RunPodCustomNodeContract(BaseModel):
    created_at: str
    workspace_root: str
    app_root: str
    comfy_root: str
    custom_nodes_root: str
    manifest_path: str
    object_info_path: str
    workflow_root: str
    artifact_path: str
    custom_nodes: list[RunPodCustomNodeEntry] = Field(default_factory=list)
    workflow_validations: list[RunPodWorkflowValidation] = Field(default_factory=list)
    checks: RunPodCustomNodeChecks
    issues: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


def default_custom_node_contract_path(app_root: str | Path) -> Path:
    return _resolve_path(Path(app_root) / "app" / "runtime" / "runpod_custom_node_contract.json")


def build_runpod_custom_node_contract(
    *,
    workspace_root: str | Path = "/workspace",
    app_root: str | Path | None = None,
    comfy_root: str | Path = "/workspace/runpod-slim/ComfyUI",
    manifest_path: str | Path | None = None,
    object_info_path: str | Path | None = None,
    workflow_root: str | Path | None = None,
    artifact_path: str | Path | None = None,
) -> RunPodCustomNodeContract:
    resolved_workspace_root = _resolve_path(workspace_root)
    resolved_app_root = _resolve_path(app_root or _default_app_root(resolved_workspace_root))
    resolved_comfy_root = _resolve_path(comfy_root or _default_comfy_root())
    resolved_manifest_path = _resolve_path(manifest_path or (resolved_app_root / "app" / "custom_nodes" / "custom_node_manifest.yaml"))
    resolved_object_info_path = _resolve_path(object_info_path or (resolved_app_root / "app" / "runtime" / "object_info.json"))
    resolved_workflow_root = _resolve_path(workflow_root or (resolved_app_root / "app" / "workflows" / "runtime"))
    resolved_artifact_path = _resolve_path(artifact_path or default_custom_node_contract_path(resolved_app_root))
    custom_nodes_root = _resolve_path(resolved_comfy_root / "custom_nodes")

    checks = RunPodCustomNodeChecks(
        manifest_present=resolved_manifest_path.exists(),
        object_info_present=resolved_object_info_path.exists(),
        workflow_files_present=resolved_workflow_root.exists() and any(resolved_workflow_root.glob("*.json")),
    )
    issues: list[str] = []
    recommended_actions: list[str] = []

    manifest_payload = {"custom_nodes": []}
    if checks.manifest_present:
        manifest_payload = yaml.safe_load(resolved_manifest_path.read_text(encoding="utf-8")) or {"custom_nodes": []}
        if not isinstance(manifest_payload, dict):
            manifest_payload = {"custom_nodes": []}
    else:
        issues.append("커스텀 노드 manifest를 찾지 못했습니다.")
        recommended_actions.append("app/custom_nodes/custom_node_manifest.yaml 경로를 확인하세요.")

    object_info: dict[str, Any] = {}
    if checks.object_info_present:
        payload = json.loads(resolved_object_info_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            object_info = payload
        else:
            issues.append("object_info.json 형식이 올바르지 않습니다.")
            recommended_actions.append("setup.sh가 다시 node inventory를 수집하도록 실행하세요.")
    else:
        issues.append("object_info.json이 없어 커스텀 노드 inventory를 검증할 수 없습니다.")
        recommended_actions.append("RunPod bootstrap 이후 app/runtime/object_info.json 생성 여부를 확인하세요.")

    custom_nodes: list[RunPodCustomNodeEntry] = []
    missing_dirs: list[str] = []
    for item in manifest_payload.get("custom_nodes", []) or []:
        if not isinstance(item, dict):
            continue
        repo = str(item.get("repo") or "").strip()
        target_dir = custom_nodes_root / _repo_dir_from_url(repo)
        target_exists = target_dir.exists()
        if not target_exists:
            missing_dirs.append(str(target_dir))
        custom_nodes.append(
            RunPodCustomNodeEntry(
                name=str(item.get("name") or target_dir.name),
                repo=repo,
                ref=str(item.get("ref") or "").strip() or None,
                target_dir=str(target_dir),
                required_for=[str(value) for value in item.get("required_for", []) if value],
                target_exists=target_exists,
                notes=str(item.get("notes") or "").strip() or None,
            )
        )
    checks.required_node_dirs_present = not missing_dirs
    if missing_dirs:
        issues.append("manifest에 선언된 커스텀 노드 디렉터리 일부가 설치되지 않았습니다.")
        recommended_actions.append("setup.sh 또는 custom_node_installer.py로 커스텀 노드 설치를 다시 맞추세요.")

    workflow_validations: list[RunPodWorkflowValidation] = []
    if checks.workflow_files_present and object_info:
        for workflow_path in sorted(resolved_workflow_root.glob("*.json")):
            workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
            errors = validate_workflow(workflow=workflow_payload, object_info=object_info)
            workflow_validations.append(
                RunPodWorkflowValidation(
                    workflow_path=str(workflow_path),
                    ok=not errors,
                    errors=errors,
                )
            )
    elif not checks.workflow_files_present:
        issues.append("runtime workflow JSON이 없어 커스텀 노드 충돌 여부를 검증할 수 없습니다.")
        recommended_actions.append("bootstrap 이후 app/workflows/runtime 아래 materialized workflow가 있는지 확인하세요.")

    checks.runtime_workflows_valid = bool(workflow_validations) and all(item.ok for item in workflow_validations)
    if workflow_validations and not checks.runtime_workflows_valid:
        issues.append("runtime workflow 일부가 현재 object_info와 맞지 않아 커스텀 노드 충돌 가능성이 있습니다.")
        recommended_actions.append("missing node class 또는 unknown input 오류를 기준으로 custom node 버전과 workflow materialization을 다시 맞추세요.")

    ok = all(
        (
            checks.manifest_present,
            checks.object_info_present,
            checks.workflow_files_present,
            checks.required_node_dirs_present,
            checks.runtime_workflows_valid,
        )
    )

    return RunPodCustomNodeContract(
        created_at=utc_now_iso(),
        workspace_root=str(resolved_workspace_root),
        app_root=str(resolved_app_root),
        comfy_root=str(resolved_comfy_root),
        custom_nodes_root=str(custom_nodes_root),
        manifest_path=str(resolved_manifest_path),
        object_info_path=str(resolved_object_info_path),
        workflow_root=str(resolved_workflow_root),
        artifact_path=str(resolved_artifact_path),
        custom_nodes=custom_nodes,
        workflow_validations=workflow_validations,
        checks=checks,
        issues=issues,
        recommended_actions=recommended_actions,
        ok=ok,
    )


def write_runpod_custom_node_contract(
    *,
    artifact_path: str | Path | None = None,
    **kwargs: Any,
) -> RunPodCustomNodeContract:
    contract = build_runpod_custom_node_contract(artifact_path=artifact_path, **kwargs)
    path = Path(contract.artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return contract


def load_runpod_custom_node_contract(path: str | Path) -> RunPodCustomNodeContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunPodCustomNodeContract(**payload)
