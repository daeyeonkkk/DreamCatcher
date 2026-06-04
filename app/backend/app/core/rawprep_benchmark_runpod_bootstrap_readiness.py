from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_paths import repo_root, resolve_output_root


PROFILE_SCOPED_MODEL_SCOPES = {
    "lazy_on_demand",
    "requested_only",
    "profile:frontier",
    "profile_plus_requested",
    "download_all",
}


class RawPrepRunPodBootstrapReadinessRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    bootstrap_summary_path: str | None = None
    model_bootstrap_contract_path: str | None = None
    custom_node_contract_path: str | None = None


class RawPrepRunPodBootstrapReadinessChecks(BaseModel):
    bootstrap_summary_present: bool = False
    bootstrap_completed: bool = False
    health_ready: bool = False
    model_contract_present: bool = False
    model_selection_recorded: bool = False
    requested_only_model_scope: bool = False
    custom_node_contract_present: bool = False
    custom_node_runtime_valid: bool = False


class RawPrepRunPodBootstrapReadinessArtifact(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_evidence"
    summary: str
    artifact_path: str | None = None
    bootstrap_summary_path: str | None = None
    model_bootstrap_contract_path: str | None = None
    custom_node_contract_path: str | None = None
    runpod_console_label: str | None = None
    model_download_scope_status: str | None = None
    selected_model_sets: list[str] = Field(default_factory=list)
    custom_node_count: int = 0
    checks: RawPrepRunPodBootstrapReadinessChecks
    blockers: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("RunPod bootstrap readiness output_dir must stay inside the configured output root.") from exc
    return resolved


def _artifact_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_runpod_bootstrap_readiness.json"


def _resolve_repo_path(relative_path: str) -> Path:
    return (repo_root() / relative_path).resolve()


def _resolve_optional_path(value: str | None, *, default_relative: str) -> Path:
    if value:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else _resolve_repo_path(value)
    return _resolve_repo_path(default_relative)


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _extract_model_contract(
    bootstrap_summary: dict[str, Any] | None,
    explicit_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    if explicit_contract:
        return explicit_contract
    if isinstance(bootstrap_summary, dict):
        candidate = bootstrap_summary.get("model_bootstrap_contract")
        if isinstance(candidate, dict):
            return candidate
    return {}


def _extract_custom_node_contract(
    bootstrap_summary: dict[str, Any] | None,
    explicit_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    if explicit_contract:
        return explicit_contract
    if isinstance(bootstrap_summary, dict):
        candidate = bootstrap_summary.get("custom_node_contract")
        if isinstance(candidate, dict):
            return candidate
    return {}


def build_rawprep_runpod_bootstrap_readiness(
    request: RawPrepRunPodBootstrapReadinessRequest,
) -> RawPrepRunPodBootstrapReadinessArtifact:
    bootstrap_summary_path = _resolve_optional_path(
        request.bootstrap_summary_path,
        default_relative="app/runtime/bootstrap_summary.json",
    )
    model_bootstrap_contract_path = _resolve_optional_path(
        request.model_bootstrap_contract_path,
        default_relative="app/runtime/runpod_model_bootstrap_contract.json",
    )
    custom_node_contract_path = _resolve_optional_path(
        request.custom_node_contract_path,
        default_relative="app/runtime/runpod_custom_node_contract.json",
    )

    bootstrap_summary = _load_json_dict(bootstrap_summary_path)
    explicit_model_contract = _load_json_dict(model_bootstrap_contract_path)
    explicit_custom_node_contract = _load_json_dict(custom_node_contract_path)
    model_contract = _extract_model_contract(bootstrap_summary, explicit_model_contract)
    custom_node_contract = _extract_custom_node_contract(bootstrap_summary, explicit_custom_node_contract)

    blockers: list[str] = []
    recommended_actions: list[str] = []

    if bootstrap_summary is None:
        blockers.append("bootstrap_summary.json이 없어 RunPod bootstrap evidence를 판단할 수 없습니다.")
        recommended_actions.append("RunPod에서 /workspace/DreamCatcher/app/runtime/bootstrap_summary.json을 다시 회수해 주세요.")

    checks_payload = bootstrap_summary.get("checks", {}) if isinstance(bootstrap_summary, dict) else {}
    checks = RawPrepRunPodBootstrapReadinessChecks(
        bootstrap_summary_present=bootstrap_summary is not None,
        bootstrap_completed=bool(checks_payload.get("comfy_ready")) and bool(checks_payload.get("backend_ready")),
        health_ready=bool(checks_payload.get("rawprep_healthcheck_present")) and bool(checks_payload.get("single_raw_healthcheck_present")),
        model_contract_present=bool(model_contract),
        model_selection_recorded=bool(model_contract.get("ok")) or bool(checks_payload.get("model_selection_recorded")),
        requested_only_model_scope=str(model_contract.get("download_scope_status") or "") in PROFILE_SCOPED_MODEL_SCOPES,
        custom_node_contract_present=bool(custom_node_contract),
        custom_node_runtime_valid=bool(custom_node_contract.get("ok")) or bool(checks_payload.get("custom_node_runtime_valid")),
    )

    if not checks.bootstrap_summary_present:
        status = "missing_evidence"
        summary = "RunPod bootstrap readiness를 판단할 summary evidence가 아직 없습니다."
    else:
        if not checks.bootstrap_completed:
            blockers.append("RunPod bootstrap이 comfy/backend 준비 상태까지 완주했다는 근거가 부족합니다.")
        if not checks.health_ready:
            blockers.append("RunPod bootstrap health evidence가 아직 완전하지 않습니다.")
        if not checks.model_contract_present:
            blockers.append("runpod_model_bootstrap_contract.json evidence가 아직 없습니다.")
            recommended_actions.append("다음 RunPod 회수 때 /workspace/DreamCatcher/app/runtime/runpod_model_bootstrap_contract.json도 같이 가져와 주세요.")
        if checks.model_contract_present and not checks.model_selection_recorded:
            blockers.append("모델 선택 정책이 canonical contract로 기록되지 않았습니다.")
        if checks.model_contract_present and not checks.requested_only_model_scope:
            blockers.append("모델 준비 범위가 lazy_on_demand/requested_only로 확인되지 않습니다.")
        if not checks.custom_node_contract_present:
            blockers.append("runpod_custom_node_contract.json evidence가 아직 없습니다.")
            recommended_actions.append("다음 RunPod 회수 때 /workspace/DreamCatcher/app/runtime/runpod_custom_node_contract.json도 같이 가져와 주세요.")
        if checks.custom_node_contract_present and not checks.custom_node_runtime_valid:
            blockers.append("커스텀 노드 runtime validation이 성공 상태가 아닙니다.")

        if blockers:
            status = "evidence_partial"
            summary = "RunPod bootstrap은 통과했지만 8.1의 남은 운영 증빙을 닫기엔 contract evidence가 아직 부분적입니다."
        else:
            status = "ready_for_bootstrap_review"
            summary = "RunPod bootstrap, health, 모델 선택 범위, 커스텀 노드 runtime validation evidence가 모두 준비됐습니다."

    template_policy = bootstrap_summary.get("runpod_template_policy", {}) if isinstance(bootstrap_summary, dict) else {}
    selected_model_sets = [str(value) for value in (model_contract.get("selected_model_sets", []) or []) if value]
    custom_nodes = custom_node_contract.get("custom_nodes", []) if isinstance(custom_node_contract.get("custom_nodes"), list) else []

    return RawPrepRunPodBootstrapReadinessArtifact(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
        bootstrap_summary_path=str(bootstrap_summary_path),
        model_bootstrap_contract_path=str(model_bootstrap_contract_path),
        custom_node_contract_path=str(custom_node_contract_path),
        runpod_console_label=str(template_policy.get("console_label") or "") or None,
        model_download_scope_status=str(model_contract.get("download_scope_status") or "") or None,
        selected_model_sets=selected_model_sets,
        custom_node_count=len(custom_nodes),
        checks=checks,
        blockers=blockers,
        recommended_actions=recommended_actions,
        ok=not blockers,
    )


def write_rawprep_runpod_bootstrap_readiness(
    request: RawPrepRunPodBootstrapReadinessRequest,
) -> RawPrepRunPodBootstrapReadinessArtifact:
    artifact = build_rawprep_runpod_bootstrap_readiness(request)
    path = _artifact_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def load_rawprep_runpod_bootstrap_readiness(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepRunPodBootstrapReadinessArtifact:
    path = _artifact_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"RunPod bootstrap readiness artifact was not found: {path}")
    return RawPrepRunPodBootstrapReadinessArtifact(**json.loads(path.read_text(encoding="utf-8")))
