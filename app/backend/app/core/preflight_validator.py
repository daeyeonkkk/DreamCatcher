from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def _extract_allowed_inputs(node_def: Dict[str, Any]) -> Set[str]:
    allowed: Set[str] = set()
    # /object_info is not guaranteed to be stable across versions, so parse defensively.
    input_block = node_def.get("input") or node_def.get("inputs") or {}
    if isinstance(input_block, dict):
        for group_name in ("required", "optional", "hidden"):
            group = input_block.get(group_name, {})
            if isinstance(group, dict):
                allowed.update(group.keys())
    return allowed


def validate_workflow(workflow: Dict[str, Any], object_info: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for node_id, node in workflow.items():
        class_type = node.get("class_type")
        if class_type not in object_info:
            errors.append(f"[{node_id}] Missing node class_type: {class_type}")
            continue

        allowed_inputs = _extract_allowed_inputs(object_info[class_type])
        node_inputs = node.get("inputs", {})
        if not isinstance(node_inputs, dict):
            errors.append(f"[{node_id}] inputs must be a dict")
            continue

        unknown_inputs = sorted(set(node_inputs.keys()) - allowed_inputs) if allowed_inputs else []
        if unknown_inputs:
            errors.append(
                f"[{node_id}] Node '{class_type}' has unknown inputs: {unknown_inputs}. "
                f"Allowed={sorted(allowed_inputs)}"
            )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a materialized workflow against ComfyUI /object_info.")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--object-info", required=True)
    args = parser.parse_args()

    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    object_info = json.loads(Path(args.object_info).read_text(encoding="utf-8"))
    errors = validate_workflow(workflow=workflow, object_info=object_info)

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print("OK: workflow validated successfully")


if __name__ == "__main__":
    main()
