from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def dataset_manifest_path(seed_root: Path) -> Path:
    return seed_root / "public_dataset_manifest.yaml"


@lru_cache(maxsize=8)
def load_public_dataset_manifest(manifest_path: str) -> dict[str, Any]:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def clear_public_dataset_manifest_cache() -> None:
    load_public_dataset_manifest.cache_clear()


def _normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    normalized: list[str] = []
    for item in payload:
        if isinstance(item, str):
            value = item.strip()
            if value:
                normalized.append(value)
            continue
        if isinstance(item, dict):
            for key, value in item.items():
                key_text = str(key).strip()
                value_text = str(value).strip()
                if key_text and value_text:
                    normalized.append(f"{key_text}: {value_text}")
            continue
        value = str(item).strip()
        if value:
            normalized.append(value)
    return normalized


def _reference_urls(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    urls: list[str] = []
    for item in payload:
        if isinstance(item, dict):
            url = item.get("url")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
        elif isinstance(item, str) and item.strip():
            urls.append(item.strip())
    return urls


def public_priors_for_tool(
    tool: str,
    *,
    seed_root: Path,
    profile: str | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    manifest = load_public_dataset_manifest(str(dataset_manifest_path(seed_root)))
    if not manifest:
        return [], [], []

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        return [], [], []

    profile_name = str(profile or manifest.get("active_profile") or "").strip()
    if not profile_name:
        return [], [], []

    profile_payload = profiles.get(profile_name)
    if not isinstance(profile_payload, dict):
        return [], [], []

    defaults = profile_payload.get("defaults")
    if not isinstance(defaults, dict):
        return [], [], []

    dataset_ids = _normalize_string_list(defaults.get(tool))
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        datasets = {}

    priors: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        dataset_payload = datasets.get(dataset_id)
        if not isinstance(dataset_payload, dict):
            continue
        priors.append(
            {
                "dataset_id": dataset_id,
                "label": str(dataset_payload.get("label") or dataset_id),
                "kind": str(dataset_payload.get("kind") or "dataset"),
                "readiness": str(dataset_payload.get("readiness") or ""),
                "availability": str(dataset_payload.get("availability") or ""),
                "scale": str(dataset_payload.get("scale") or ""),
                "license": str(dataset_payload.get("license") or ""),
                "bootstraps": _normalize_string_list(dataset_payload.get("bootstraps")),
                "notes": str(dataset_payload.get("notes") or ""),
                "references": _reference_urls(dataset_payload.get("references")),
            }
        )

    return (
        priors,
        _normalize_string_list(profile_payload.get("bootstrap_rules")),
        _normalize_string_list((profile_payload.get("community_takeaways") or {}).get(tool)),
    )
