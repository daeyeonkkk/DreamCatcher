from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Mapping, List
import yaml

from .node_discovery import ComfyEndpoint, NodeDiscovery, NodeDiscoveryError
from .workflow_patch import patch_all_in_directory


class PreflightError(RuntimeError):
    """Raised when startup validation fails."""


def load_workflow_requirements(path: str) -> Dict[str, List[str]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    workflows = data.get("workflows", {})
    result: Dict[str, List[str]] = {}
    for workflow_name, spec in workflows.items():
        aliases = list(spec.get("required_aliases", []))
        result[workflow_name] = aliases
    return result


def validate_requirements(resolved: Mapping[str, str], requirements: Mapping[str, List[str]]) -> Dict[str, Any]:
    missing_by_workflow: Dict[str, List[str]] = {}
    for workflow_name, aliases in requirements.items():
        missing = [alias for alias in aliases if alias not in resolved]
        if missing:
            missing_by_workflow[workflow_name] = missing
    return {
        "ok": not missing_by_workflow,
        "missing_by_workflow": missing_by_workflow,
    }


def run_preflight(
    base_url: str,
    alias_config_path: str,
    workflow_requirements_path: str,
    workflow_template_dir: str,
    resolved_output_path: str,
    patched_output_dir: str,
) -> Dict[str, Any]:
    discovery = NodeDiscovery(ComfyEndpoint(base_url=base_url))
    object_info = discovery.fetch_object_info()
    alias_map = discovery.load_aliases(alias_config_path)
    resolved = discovery.resolve_aliases(object_info, alias_map)
    discovery.save_resolved_nodes(resolved_output_path, resolved)

    requirements = load_workflow_requirements(workflow_requirements_path)
    validation = validate_requirements(resolved, requirements)
    if not validation["ok"]:
        raise PreflightError(json.dumps(validation, ensure_ascii=False, indent=2))

    patched = patch_all_in_directory(
        template_dir=workflow_template_dir,
        output_dir=patched_output_dir,
        resolved_nodes=resolved,
    )

    return {
        "resolved_nodes": resolved,
        "patched_workflows": patched,
        "workflow_validation": validation,
        "detected_node_count": len(object_info),
    }
