from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

from .node_alias_resolver import NodeAliasResolver


NODE_PREFIX = "@node:"


def materialize_workflow(template: Dict[str, Any], resolver: NodeAliasResolver) -> Tuple[Dict[str, Any], Dict[str, str]]:
    workflow = deepcopy(template)
    resolved_map: Dict[str, str] = {}

    for node_id, node in workflow.items():
        class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type.startswith(NODE_PREFIX):
            logical_name = class_type[len(NODE_PREFIX):]
            resolved = resolver.resolve(logical_name)
            node["class_type"] = resolved.concrete_name
            node.setdefault("_dc_meta", {})
            node["_dc_meta"]["logical_name"] = logical_name
            node["_dc_meta"]["resolution_strategy"] = resolved.strategy
            resolved_map[logical_name] = resolved.concrete_name

    return workflow, resolved_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize a logical-node workflow template into a runtime workflow.")
    parser.add_argument("--template", required=True)
    parser.add_argument("--alias-config", required=True)
    parser.add_argument("--object-info", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    resolver = NodeAliasResolver.from_files(args.alias_config, args.object_info)
    workflow, _ = materialize_workflow(template, resolver)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
