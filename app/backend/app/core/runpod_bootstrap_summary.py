from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runpod_model_bootstrap_contract import build_runpod_bootstrap_session_policy
from .runpod_model_bootstrap_contract import build_runpod_template_policy


def _load_json_dict(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_shape"}
    return payload


def build_runpod_bootstrap_summary(
    *,
    summary_path: str | Path,
    workflow_dir: str | Path,
    rawprep_healthcheck_path: str | Path,
    single_raw_healthcheck_path: str | Path,
    backend_url: str,
    comfy_root: str | Path,
    comfy_python: str,
    console_label: str,
    primary_image: str,
    fallback_pinned_image: str,
    fallback_alias_image: str,
    storage_contract_path: str | Path,
    model_bootstrap_contract_path: str | Path,
    custom_node_contract_path: str | Path,
) -> dict[str, Any]:
    resolved_summary_path = Path(summary_path).resolve()
    resolved_workflow_dir = Path(workflow_dir).resolve()
    resolved_rawprep_healthcheck_path = Path(rawprep_healthcheck_path).resolve()
    resolved_single_raw_healthcheck_path = Path(single_raw_healthcheck_path).resolve()
    resolved_comfy_root = Path(comfy_root).resolve()
    resolved_storage_contract_path = Path(storage_contract_path).resolve()
    resolved_model_bootstrap_contract_path = Path(model_bootstrap_contract_path).resolve()
    resolved_custom_node_contract_path = Path(custom_node_contract_path).resolve()

    rawprep_healthcheck = _load_json_dict(resolved_rawprep_healthcheck_path)
    single_raw_healthcheck = _load_json_dict(resolved_single_raw_healthcheck_path)
    storage_contract = _load_json_dict(resolved_storage_contract_path)
    model_bootstrap_contract = _load_json_dict(resolved_model_bootstrap_contract_path)
    custom_node_contract = _load_json_dict(resolved_custom_node_contract_path)
    template_policy = model_bootstrap_contract.get("template_policy") or build_runpod_template_policy().model_dump()
    session_policy = model_bootstrap_contract.get("bootstrap_session_policy") or build_runpod_bootstrap_session_policy().model_dump()

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "app_root": str(resolved_summary_path.parents[2]),
        "backend_url": backend_url,
        "comfy_root": str(resolved_comfy_root),
        "comfy_python": comfy_python,
        "runpod_template_policy": {
            "console_label": console_label,
            "primary_image": primary_image,
            "fallback_pinned_image": fallback_pinned_image,
            "fallback_alias_image": fallback_alias_image,
            "canonical_policy": template_policy,
        },
        "runpod_bootstrap_session_policy": session_policy,
        "workflow_dir": str(resolved_workflow_dir),
        "workflow_files": sorted(path.name for path in resolved_workflow_dir.glob("*") if path.is_file()),
        "rawprep_healthcheck_path": str(resolved_rawprep_healthcheck_path),
        "rawprep_healthcheck": rawprep_healthcheck,
        "single_raw_healthcheck_path": str(resolved_single_raw_healthcheck_path),
        "single_raw_healthcheck": single_raw_healthcheck,
        "storage_contract_path": str(resolved_storage_contract_path),
        "storage_contract": storage_contract,
        "model_bootstrap_contract_path": str(resolved_model_bootstrap_contract_path),
        "model_bootstrap_contract": model_bootstrap_contract,
        "custom_node_contract_path": str(resolved_custom_node_contract_path),
        "custom_node_contract": custom_node_contract,
        "frontend_served_by_backend": True,
        "frontend_entry_port": "8000/http",
        "checks": {
            "comfy_ready": True,
            "backend_ready": True,
            "runtime_workflows_present": resolved_workflow_dir.exists() and any(path.is_file() for path in resolved_workflow_dir.glob("*")),
            "rawprep_healthcheck_present": resolved_rawprep_healthcheck_path.exists(),
            "single_raw_runtime_ready": bool(single_raw_healthcheck.get("ok")),
            "single_raw_healthcheck_present": resolved_single_raw_healthcheck_path.exists(),
            "storage_contract_present": resolved_storage_contract_path.exists(),
            "storage_layout_ok": bool(storage_contract.get("ok")),
            "model_bootstrap_contract_present": resolved_model_bootstrap_contract_path.exists(),
            "model_selection_recorded": bool(model_bootstrap_contract.get("ok")),
            "ephemeral_session_policy_recorded": session_policy.get("mode") == "ephemeral_zip_pod",
            "custom_node_contract_present": resolved_custom_node_contract_path.exists(),
            "custom_node_runtime_valid": bool(custom_node_contract.get("ok")),
        },
    }


def write_runpod_bootstrap_summary(
    *,
    summary_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = build_runpod_bootstrap_summary(summary_path=summary_path, **kwargs)
    resolved_summary_path = Path(summary_path).resolve()
    resolved_summary_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
