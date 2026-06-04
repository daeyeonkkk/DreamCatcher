from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


REQUIRED_API_WORKFLOWS = {
    "qwen_precision_edit.api.json",
    "flux2_dev_compose.api.json",
    "flux2_klein_preview.api.json",
    "flux_fill_replace.api.json",
}

REQUIRED_EXTRA_FILES = (
    "comfy.settings.json",
    "frontier_dataset_manifest.yaml",
    "pinned_refs.lock.yaml",
    "public_dataset_manifest.yaml",
    "resolved_nodes.json",
    "runtime_priors/manifest.yaml",
    "runtime_priors/evaluator/golden_calibration_v1.schema.json",
    "runtime_priors/evaluator/golden_quality_calibration.seed.json",
    "runtime_priors/evaluator/judge_evidence_packet_v1.schema.json",
    "runtime_priors/evaluator/qwen_judge_signal_v2.schema.json",
)


@dataclass
class SeedBundleStatus:
    root: Path
    missing_files: List[str]
    found_api_workflows: List[str]
    placeholder_api_workflows: List[str]

    @property
    def ok(self) -> bool:
        return not self.missing_files and not self.placeholder_api_workflows


def _is_placeholder_json(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(data.get("_placeholder")) if isinstance(data, dict) else False


def inspect_seed_bundle(root: str | Path) -> SeedBundleStatus:
    root = Path(root)
    missing: List[str] = []
    api_dir = root / "api_workflows"
    found: List[str] = []
    placeholders: List[str] = []

    for name in sorted(REQUIRED_API_WORKFLOWS):
        path = api_dir / name
        if path.exists():
            found.append(name)
            if _is_placeholder_json(path):
                placeholders.append(name)
        else:
            missing.append(str(path.relative_to(root)))

    for relpath in REQUIRED_EXTRA_FILES:
        path = root / relpath
        if not path.exists():
            missing.append(str(path.relative_to(root)))

    return SeedBundleStatus(
        root=root,
        missing_files=missing,
        found_api_workflows=found,
        placeholder_api_workflows=placeholders,
    )
