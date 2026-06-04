from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Mapping


PLACEHOLDER_PATTERN = re.compile(r"\$\{node\.([a-zA-Z0-9_]+)\}")


class WorkflowPatchError(RuntimeError):
    pass


def patch_workflow_text(template_text: str, resolved_nodes: Mapping[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        alias = match.group(1)
        if alias not in resolved_nodes:
            raise WorkflowPatchError(f"Missing resolved alias: {alias}")
        return resolved_nodes[alias]

    return PLACEHOLDER_PATTERN.sub(replacer, template_text)


def patch_workflow_file(template_path: str, output_path: str, resolved_nodes: Mapping[str, str]) -> None:
    text = Path(template_path).read_text(encoding="utf-8")
    patched = patch_workflow_text(text, resolved_nodes)
    # ensure JSON is valid after replacement
    parsed = json.loads(patched)
    Path(output_path).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_all_in_directory(template_dir: str, output_dir: str, resolved_nodes: Mapping[str, str]) -> Dict[str, str]:
    template_root = Path(template_dir)
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    result = {}
    for path in template_root.glob("*.template.json"):
        output_name = path.name.replace(".template.json", ".resolved.json")
        output_path = out_root / output_name
        patch_workflow_file(str(path), str(output_path), resolved_nodes)
        result[str(path)] = str(output_path)
    return result
