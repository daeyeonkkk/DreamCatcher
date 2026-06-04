from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .frontier_dataset_catalog import (
    FrontierDatasetCard,
    build_frontier_dataset_plan,
    frontier_dataset_manifest_path,
)


TOOL_FRONTIER_TASKS: dict[str, list[str]] = {
    "removeBg": ["background_removal_matting"],
    "replaceBg": ["background_generation_replace", "background_removal_matting", "inpaint_outpaint"],
    "relight": ["background_generation_replace", "photo_correction_retouch"],
    "replaceObject": ["inpaint_outpaint", "background_generation_replace", "background_removal_matting"],
    "expandCanvas": ["inpaint_outpaint", "background_generation_replace"],
    "retouch": ["photo_correction_retouch"],
    "enhance": ["photo_correction_retouch"],
    "finish": ["photo_correction_retouch"],
    "compare": ["photo_correction_retouch", "background_generation_replace", "inpaint_outpaint"],
    "rawprep": ["raw_merge_denoise"],
    "triRaw": ["raw_merge_denoise"],
    "rawMergeDenoise": ["raw_merge_denoise"],
}

ACTIVE_STAGES = {"runtime_prior_active", "adapter_hook_active", "model_contract_active", "eval_guardrail_ready"}


def frontier_tasks_for_tool(tool: str) -> list[str]:
    return TOOL_FRONTIER_TASKS.get(tool, [])


def _runtime_prior_dataset_ids(runtime_prior_artifacts: list[dict[str, Any]]) -> set[str]:
    dataset_ids: set[str] = set()
    for artifact in runtime_prior_artifacts:
        source_datasets = artifact.get("source_datasets")
        if not isinstance(source_datasets, list):
            continue
        for dataset_id in source_datasets:
            value = str(dataset_id).strip()
            if value:
                dataset_ids.add(value)
    return dataset_ids


def _repo_root_for_seed_root(seed_root: Path) -> Path:
    if seed_root.name == "seed_bundle":
        return seed_root.parent
    return seed_root.parent


def _local_cache_path(card: FrontierDatasetCard, *, seed_root: Path) -> Path:
    path = Path(card.local_dir)
    if path.is_absolute():
        return path
    return (_repo_root_for_seed_root(seed_root) / path).resolve()


def _rawfusion_adapter_ready() -> bool:
    if os.getenv("DC_TRIRAW_LEARNED_ADAPTER", "").strip().lower() != "rawfusion":
        return False
    repo = os.getenv("DC_RAWFUSION_REPO", "").strip()
    checkpoint = os.getenv("DC_RAWFUSION_CKPT", "").strip()
    return bool(repo and checkpoint and Path(repo).exists() and Path(checkpoint).exists())


def _activation_stage(
    card: FrontierDatasetCard,
    *,
    runtime_prior_dataset_ids: set[str],
    rawfusion_adapter_ready: bool,
) -> str:
    if card.dataset_id in runtime_prior_dataset_ids:
        return "runtime_prior_active"
    if card.dataset_id == "rawfusion_burst_hdr" and rawfusion_adapter_ready:
        return "adapter_hook_active"
    if card.kind == "cutout_model_weights" and card.integration_status == "ready":
        return "model_contract_active"
    if card.integration_status == "ready" and card.readiness in {
        "benchmark",
        "executable_model",
        "foundational",
        "frontier_eval_default",
        "model_reference",
    }:
        return "eval_guardrail_ready"
    if card.integration_status == "license_review":
        return "license_review"
    if card.integration_status == "weights_pending":
        return "weights_pending"
    if card.integration_status == "workflow_needed":
        return "workflow_pending"
    if card.integration_status == "dataset_only":
        return "dataset_only"
    return "catalog_tracked"


def _blocking_reason(card: FrontierDatasetCard, *, stage: str, local_cache_present: bool) -> str | None:
    if stage in ACTIVE_STAGES:
        return None
    if card.integration_status == "license_review":
        return "license_review_required"
    if card.integration_status == "weights_pending":
        return "weights_or_release_pending"
    if card.integration_status == "workflow_needed":
        return "workflow_or_adapter_needed"
    if card.download_mode == "challenge_registration":
        return "challenge_registration_required"
    if card.download_mode == "manual":
        return "manual_collection_required"
    if card.download_mode in {"git_clone", "hf_dataset", "hf_model"} and not local_cache_present:
        return "local_cache_missing_for_training_or_eval"
    return None


def _studio_use(card: FrontierDatasetCard, *, stage: str) -> list[str]:
    uses: list[str] = []
    if stage == "runtime_prior_active":
        uses.append("runtime_prior")
    if stage == "adapter_hook_active":
        uses.append("optional_learned_adapter")
    if "raw_merge_denoise" in card.tasks:
        uses.extend(["tri_raw_frontier_eval", "alignment_ghost_denoise_evidence"])
    if "photo_correction_retouch" in card.tasks:
        uses.extend(["compare_guardrail", "retouch_reference_prior"])
    if "background_removal_matting" in card.tasks:
        uses.extend(["mask_boundary_eval", "cutout_model_evidence"])
    if "background_generation_replace" in card.tasks:
        uses.extend(["composition_guardrail", "subject_preservation_eval"])
    if "inpaint_outpaint" in card.tasks:
        uses.extend(["mask_distribution_regression", "large_hole_fill_eval"])
    return list(dict.fromkeys(uses))


def frontier_dataset_activation_for_tool(
    tool: str,
    *,
    seed_root: Path,
    runtime_prior_artifacts: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not frontier_dataset_manifest_path(seed_root).exists():
        return None, []

    tasks = frontier_tasks_for_tool(tool)
    if not tasks:
        return None, []

    runtime_dataset_ids = _runtime_prior_dataset_ids(runtime_prior_artifacts or [])
    rawfusion_ready = _rawfusion_adapter_ready()
    plan = build_frontier_dataset_plan(seed_root=seed_root, tasks=tasks)

    items: list[dict[str, Any]] = []
    for card in plan.selected_datasets:
        cache_path = _local_cache_path(card, seed_root=seed_root)
        cache_present = cache_path.exists()
        stage = _activation_stage(
            card,
            runtime_prior_dataset_ids=runtime_dataset_ids,
            rawfusion_adapter_ready=rawfusion_ready,
        )
        items.append(
            {
                "dataset_id": card.dataset_id,
                "label": card.label,
                "tasks": card.tasks,
                "kind": card.kind,
                "readiness": card.readiness,
                "integration_status": card.integration_status,
                "availability": card.availability,
                "download_mode": card.download_mode,
                "runpod_default_download": card.runpod_default_download,
                "local_dir": card.local_dir,
                "local_cache_present": cache_present,
                "activation_stage": stage,
                "studio_use": _studio_use(card, stage=stage),
                "blocking_reason": _blocking_reason(card, stage=stage, local_cache_present=cache_present),
                "license_note": card.license_note,
                "use_in_dreamcatcher": card.use_in_dreamcatcher,
                "references": card.references,
            }
        )

    summary = {
        "label": "Frontier Dataset Activation",
        "tool": tool,
        "task_ids": tasks,
        "dataset_count": len(items),
        "active_count": sum(1 for item in items if item["activation_stage"] in ACTIVE_STAGES),
        "local_cache_ready_count": sum(1 for item in items if item["local_cache_present"]),
        "runtime_prior_dataset_ids": sorted(runtime_dataset_ids),
        "runpod_default_downloads_datasets": False,
        "policy": "manifest_driven_runtime_priors_no_default_corpora",
        "warnings": plan.warnings,
        "notes": [
            "Frontier dataset corpora are not downloaded during normal ephemeral RunPod bootstrap.",
            "Runtime priors, model contracts, evaluation guardrails, and optional adapters can use the catalog automatically.",
        ],
    }
    return summary, items
