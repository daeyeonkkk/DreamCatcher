from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_paths import resolve_output_root


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


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def paths_are_separate(first: Path, second: Path) -> bool:
    return not (
        first == second
        or _is_relative_to(first, second)
        or _is_relative_to(second, first)
    )


class RunPodStorageChecks(BaseModel):
    model_cache_location_clear: bool = False
    workflow_cache_location_clear: bool = False
    session_output_location_clear: bool = False
    outputs_vs_model_cache: bool = False
    outputs_vs_comfy_models: bool = False
    outputs_vs_bootstrap_cache: bool = False
    outputs_vs_workflow_runtime: bool = False
    outputs_vs_workflow_staging: bool = False
    outputs_vs_rawprep_root: bool = False
    outputs_vs_rawprep_tmp: bool = False
    outputs_not_mixed_with_cache: bool = False


class RunPodStorageContract(BaseModel):
    created_at: str
    workspace_root: str
    app_root: str
    comfy_root: str
    runtime_root: str
    output_root: str
    model_cache_root: str
    comfy_models_root: str
    bootstrap_cache_root: str
    workflow_runtime_root: str
    workflow_staging_root: str
    rawprep_root: str
    rawprep_tmp_root: str
    artifact_path: str
    checks: RunPodStorageChecks
    issues: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


def default_storage_contract_path(app_root: str | Path) -> Path:
    return _resolve_path(Path(app_root) / "app" / "runtime" / "runpod_storage_contract.json")


def build_runpod_storage_contract(
    *,
    workspace_root: str | Path = "/workspace",
    app_root: str | Path | None = None,
    comfy_root: str | Path = "/workspace/runpod-slim/ComfyUI",
    hf_home: str | Path | None = None,
    bootstrap_cache_root: str | Path | None = None,
    workflow_runtime_root: str | Path | None = None,
    workflow_staging_root: str | Path | None = None,
    rawprep_root: str | Path | None = None,
    rawprep_tmp_root: str | Path | None = None,
    output_root: str | Path = "outputs",
    artifact_path: str | Path | None = None,
) -> RunPodStorageContract:
    resolved_workspace_root = _resolve_path(workspace_root)
    resolved_app_root = _resolve_path(app_root or _default_app_root(resolved_workspace_root))
    resolved_comfy_root = _resolve_path(comfy_root or _default_comfy_root())
    resolved_model_cache_root = _resolve_path(hf_home or os.getenv("HF_HOME") or (resolved_workspace_root / ".cache" / "huggingface"))
    resolved_bootstrap_cache_root = _resolve_path(bootstrap_cache_root or (resolved_workspace_root / ".dreamcatcher_cache"))
    resolved_workflow_runtime_root = _resolve_path(workflow_runtime_root or (resolved_app_root / "app" / "workflows" / "runtime"))
    resolved_workflow_staging_root = _resolve_path(workflow_staging_root or (resolved_app_root / "seed_bundle" / "staging_templates"))
    resolved_rawprep_root = _resolve_path(rawprep_root or os.getenv("RAWPREP_ROOT") or (resolved_workspace_root / "rawprep"))
    resolved_rawprep_tmp_root = _resolve_path(rawprep_tmp_root or os.getenv("RAWPREP_TMP") or (resolved_workspace_root / ".rawprep_tmp"))
    resolved_output_root = (
        _resolve_path(output_root)
        if Path(output_root).expanduser().is_absolute()
        else resolve_output_root(output_root)
    )
    resolved_comfy_models_root = _resolve_path(resolved_comfy_root / "models")
    resolved_artifact_path = _resolve_path(artifact_path or default_storage_contract_path(resolved_app_root))

    checks = RunPodStorageChecks(
        model_cache_location_clear=bool(resolved_model_cache_root and resolved_comfy_models_root),
        workflow_cache_location_clear=bool(resolved_bootstrap_cache_root and resolved_workflow_runtime_root and resolved_workflow_staging_root),
        session_output_location_clear=bool(resolved_output_root),
        outputs_vs_model_cache=paths_are_separate(resolved_output_root, resolved_model_cache_root),
        outputs_vs_comfy_models=paths_are_separate(resolved_output_root, resolved_comfy_models_root),
        outputs_vs_bootstrap_cache=paths_are_separate(resolved_output_root, resolved_bootstrap_cache_root),
        outputs_vs_workflow_runtime=paths_are_separate(resolved_output_root, resolved_workflow_runtime_root),
        outputs_vs_workflow_staging=paths_are_separate(resolved_output_root, resolved_workflow_staging_root),
        outputs_vs_rawprep_root=paths_are_separate(resolved_output_root, resolved_rawprep_root),
        outputs_vs_rawprep_tmp=paths_are_separate(resolved_output_root, resolved_rawprep_tmp_root),
    )
    checks.outputs_not_mixed_with_cache = all(
        (
            checks.outputs_vs_model_cache,
            checks.outputs_vs_comfy_models,
            checks.outputs_vs_bootstrap_cache,
            checks.outputs_vs_workflow_runtime,
            checks.outputs_vs_workflow_staging,
            checks.outputs_vs_rawprep_root,
            checks.outputs_vs_rawprep_tmp,
        )
    )

    issues: list[str] = []
    recommended_actions: list[str] = []
    if not checks.model_cache_location_clear:
        issues.append("모델 캐시 루트가 완전히 정의되지 않았습니다.")
        recommended_actions.append("HF_HOME을 설정하고 ComfyUI 모델은 전용 models 루트 아래에 두세요.")
    if not checks.workflow_cache_location_clear:
        issues.append("워크플로 캐시 루트가 완전히 정의되지 않았습니다.")
        recommended_actions.append("워크플로 bootstrap marker와 staging template은 output과 분리된 전용 루트에 두세요.")
    if not checks.session_output_location_clear:
        issues.append("세션 output 루트가 정의되지 않았습니다.")
        recommended_actions.append("RAWPREP_OUT 또는 백엔드 output_root를 전용 세션 output 경로에 두세요.")
    if not checks.outputs_not_mixed_with_cache:
        issues.append("세션 output이 하나 이상의 캐시·모델·워크플로 루트와 겹칩니다.")
        recommended_actions.append("output은 HF cache, ComfyUI models, bootstrap cache, workflow roots, RAWPREP_ROOT, RAWPREP_TMP와 분리하세요.")

    ok = (
        checks.model_cache_location_clear
        and checks.workflow_cache_location_clear
        and checks.session_output_location_clear
        and checks.outputs_not_mixed_with_cache
    )
    return RunPodStorageContract(
        created_at=utc_now_iso(),
        workspace_root=str(resolved_workspace_root),
        app_root=str(resolved_app_root),
        comfy_root=str(resolved_comfy_root),
        runtime_root=str(_resolve_path(resolved_app_root / "app" / "runtime")),
        output_root=str(resolved_output_root),
        model_cache_root=str(resolved_model_cache_root),
        comfy_models_root=str(resolved_comfy_models_root),
        bootstrap_cache_root=str(resolved_bootstrap_cache_root),
        workflow_runtime_root=str(resolved_workflow_runtime_root),
        workflow_staging_root=str(resolved_workflow_staging_root),
        rawprep_root=str(resolved_rawprep_root),
        rawprep_tmp_root=str(resolved_rawprep_tmp_root),
        artifact_path=str(resolved_artifact_path),
        checks=checks,
        issues=issues,
        recommended_actions=recommended_actions,
        ok=ok,
    )


def write_runpod_storage_contract(
    *,
    artifact_path: str | Path | None = None,
    **kwargs: Any,
) -> RunPodStorageContract:
    contract = build_runpod_storage_contract(artifact_path=artifact_path, **kwargs)
    path = Path(contract.artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return contract


def load_runpod_storage_contract(path: str | Path) -> RunPodStorageContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunPodStorageContract(**payload)
