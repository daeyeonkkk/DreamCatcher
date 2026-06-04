from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


FRONTIER_DATASET_MANIFEST_NAME = "frontier_dataset_manifest.yaml"


@dataclass(frozen=True)
class FrontierDatasetCard:
    dataset_id: str
    label: str
    tasks: list[str]
    kind: str
    readiness: str
    integration_status: str
    availability: str
    download_mode: str
    runpod_default_download: bool
    local_dir: str
    license_note: str
    use_in_dreamcatcher: str
    references: list[str]


@dataclass(frozen=True)
class FrontierDownloadPlanItem:
    dataset_id: str
    label: str
    download_mode: str
    local_dir: str
    status: str
    command: str | None = None
    manual_url: str | None = None
    license_note: str = ""


@dataclass(frozen=True)
class FrontierDatasetPlan:
    ok: bool
    seed_root: str
    manifest_path: str
    local_cache_root: str
    tasks: list[str]
    selected_dataset_count: int
    selected_datasets: list[FrontierDatasetCard]
    task_coverage: dict[str, list[str]]
    missing_tasks: list[str] = field(default_factory=list)
    unknown_dataset_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    download_plan: list[FrontierDownloadPlanItem] = field(default_factory=list)
    eval_tracks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def frontier_dataset_manifest_path(seed_root: Path) -> Path:
    return seed_root / FRONTIER_DATASET_MANIFEST_NAME


@lru_cache(maxsize=8)
def load_frontier_dataset_manifest(manifest_path: str) -> dict[str, Any]:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def clear_frontier_dataset_manifest_cache() -> None:
    load_frontier_dataset_manifest.cache_clear()


def _normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    normalized: list[str] = []
    for item in payload:
        value = str(item).strip()
        if value:
            normalized.append(value)
    return normalized


def _string_dict(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _manifest_datasets(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        return {}
    return {str(key): value for key, value in datasets.items() if isinstance(value, dict)}


def _manifest_task_names(manifest: dict[str, Any]) -> list[str]:
    tasks = manifest.get("tasks")
    if isinstance(tasks, dict):
        return [str(key) for key in tasks.keys()]
    return []


def _references(payload: dict[str, Any]) -> list[str]:
    return _normalize_string_list(payload.get("references"))


def _policy_local_cache_root(manifest: dict[str, Any]) -> str:
    policy = _string_dict(manifest.get("policy"))
    value = str(policy.get("local_cache_root") or "local_data_lab/cache/frontier_datasets").strip()
    return value or "local_data_lab/cache/frontier_datasets"


def _local_dir(local_cache_root: Path, dataset_id: str, dataset_payload: dict[str, Any]) -> str:
    subdir = str(dataset_payload.get("local_cache_subdir") or dataset_id).strip() or dataset_id
    return str(local_cache_root / Path(subdir))


def _dataset_card(
    dataset_id: str,
    payload: dict[str, Any],
    *,
    local_cache_root: Path,
) -> FrontierDatasetCard:
    return FrontierDatasetCard(
        dataset_id=dataset_id,
        label=str(payload.get("label") or dataset_id),
        tasks=_normalize_string_list(payload.get("tasks")),
        kind=str(payload.get("kind") or "dataset"),
        readiness=str(payload.get("readiness") or ""),
        integration_status=str(payload.get("integration_status") or ""),
        availability=str(payload.get("availability") or ""),
        download_mode=str(payload.get("download_mode") or "metadata_only"),
        runpod_default_download=bool(payload.get("runpod_default_download")),
        local_dir=_local_dir(local_cache_root, dataset_id, payload),
        license_note=str(payload.get("license_note") or ""),
        use_in_dreamcatcher=str(payload.get("use_in_dreamcatcher") or ""),
        references=_references(payload),
    )


def list_frontier_dataset_cards(
    *,
    seed_root: Path,
    tasks: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    local_cache_root: Path | None = None,
) -> list[FrontierDatasetCard]:
    manifest_path = frontier_dataset_manifest_path(seed_root)
    manifest = load_frontier_dataset_manifest(str(manifest_path))
    datasets = _manifest_datasets(manifest)
    cache_root = local_cache_root or Path(_policy_local_cache_root(manifest))

    requested_tasks = set(tasks or [])
    requested_ids = set(dataset_ids or [])
    cards: list[FrontierDatasetCard] = []
    for dataset_id, payload in datasets.items():
        if requested_ids and dataset_id not in requested_ids:
            continue
        dataset_tasks = set(_normalize_string_list(payload.get("tasks")))
        if requested_tasks and dataset_tasks.isdisjoint(requested_tasks):
            continue
        cards.append(_dataset_card(dataset_id, payload, local_cache_root=cache_root))
    return cards


def _select_dataset_ids(
    manifest: dict[str, Any],
    *,
    tasks: list[str],
    dataset_ids: list[str],
) -> tuple[list[str], list[str]]:
    if dataset_ids:
        return dataset_ids, []

    datasets = _manifest_datasets(manifest)
    if not tasks:
        return list(datasets.keys()), []

    defaults = _string_dict(manifest.get("task_defaults"))
    selected: list[str] = []
    unknown_defaults: list[str] = []
    for task in tasks:
        for dataset_id in _normalize_string_list(defaults.get(task)):
            if dataset_id not in datasets:
                unknown_defaults.append(dataset_id)
                continue
            if dataset_id not in selected:
                selected.append(dataset_id)
    return selected, unknown_defaults


def _download_plan_item(
    card: FrontierDatasetCard,
    payload: dict[str, Any],
) -> FrontierDownloadPlanItem:
    download = _string_dict(payload.get("download"))
    mode = card.download_mode
    command: str | None = None
    status = "manual_gate"
    manual_url = card.references[0] if card.references else None

    if mode == "hf_dataset":
        hf_dataset_id = str(download.get("hf_dataset_id") or "").strip()
        if hf_dataset_id:
            command = f"huggingface-cli download --repo-type dataset {hf_dataset_id} --local-dir {card.local_dir}"
            status = "command_ready_license_gate"
    elif mode == "hf_model":
        hf_model_id = str(download.get("hf_model_id") or "").strip()
        if hf_model_id:
            command = f"huggingface-cli download {hf_model_id} --local-dir {card.local_dir}"
            status = "command_ready_license_gate"
    elif mode == "git_clone":
        git_url = str(download.get("git_url") or "").strip()
        if git_url:
            command = f"git clone {git_url} {card.local_dir}"
            status = "command_ready_license_gate"
    elif mode == "metadata_only":
        status = "metadata_only"
    elif mode == "challenge_registration":
        status = "challenge_registration_required"

    return FrontierDownloadPlanItem(
        dataset_id=card.dataset_id,
        label=card.label,
        download_mode=mode,
        local_dir=card.local_dir,
        status=status,
        command=command,
        manual_url=manual_url,
        license_note=card.license_note,
    )


def build_frontier_dataset_plan(
    *,
    seed_root: Path,
    tasks: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    local_cache_root: Path | None = None,
) -> FrontierDatasetPlan:
    manifest_path = frontier_dataset_manifest_path(seed_root)
    manifest = load_frontier_dataset_manifest(str(manifest_path))
    cache_root = local_cache_root or Path(_policy_local_cache_root(manifest))
    all_datasets = _manifest_datasets(manifest)
    requested_tasks = list(dict.fromkeys(tasks or []))
    requested_dataset_ids = list(dict.fromkeys(dataset_ids or []))

    selected_ids, unknown_defaults = _select_dataset_ids(
        manifest,
        tasks=requested_tasks,
        dataset_ids=requested_dataset_ids,
    )
    unknown_dataset_ids = [dataset_id for dataset_id in selected_ids if dataset_id not in all_datasets]
    unknown_dataset_ids.extend(dataset_id for dataset_id in unknown_defaults if dataset_id not in unknown_dataset_ids)

    selected_cards: list[FrontierDatasetCard] = []
    selected_payloads: dict[str, dict[str, Any]] = {}
    for dataset_id in selected_ids:
        payload = all_datasets.get(dataset_id)
        if not isinstance(payload, dict):
            continue
        card = _dataset_card(dataset_id, payload, local_cache_root=cache_root)
        if requested_tasks and set(card.tasks).isdisjoint(requested_tasks):
            continue
        selected_cards.append(card)
        selected_payloads[dataset_id] = payload

    coverage_tasks = requested_tasks or _manifest_task_names(manifest)
    task_coverage: dict[str, list[str]] = {task: [] for task in coverage_tasks}
    for card in selected_cards:
        for task in coverage_tasks:
            if task in card.tasks:
                task_coverage.setdefault(task, []).append(card.dataset_id)

    missing_tasks = [task for task, covered_ids in task_coverage.items() if not covered_ids]
    warnings: list[str] = []
    for card in selected_cards:
        if card.runpod_default_download:
            warnings.append(f"{card.dataset_id}: runpod_default_download should remain false for dataset corpora.")
        if card.integration_status in {"license_review", "weights_pending", "workflow_needed"}:
            warnings.append(f"{card.dataset_id}: integration_status={card.integration_status}")
        if card.download_mode in {"manual", "challenge_registration"}:
            warnings.append(f"{card.dataset_id}: {card.download_mode} requires explicit operator action.")

    download_plan = [
        _download_plan_item(card, selected_payloads[card.dataset_id])
        for card in selected_cards
    ]

    eval_tracks = _string_dict(manifest.get("eval_tracks"))
    return FrontierDatasetPlan(
        ok=not unknown_dataset_ids and not missing_tasks,
        seed_root=str(seed_root),
        manifest_path=str(manifest_path),
        local_cache_root=str(cache_root),
        tasks=coverage_tasks,
        selected_dataset_count=len(selected_cards),
        selected_datasets=selected_cards,
        task_coverage=task_coverage,
        missing_tasks=missing_tasks,
        unknown_dataset_ids=unknown_dataset_ids,
        warnings=warnings,
        download_plan=download_plan,
        eval_tracks=eval_tracks,
    )
