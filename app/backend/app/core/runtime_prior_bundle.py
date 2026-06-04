from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def runtime_prior_manifest_path(seed_root: Path) -> Path:
    return seed_root / "runtime_priors" / "manifest.yaml"


@lru_cache(maxsize=8)
def load_runtime_prior_manifest(manifest_path: str) -> dict[str, Any]:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def clear_runtime_prior_manifest_cache() -> None:
    load_runtime_prior_manifest.cache_clear()


def _normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def runtime_priors_for_tool(
    tool: str,
    *,
    seed_root: Path,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    manifest = load_runtime_prior_manifest(str(runtime_prior_manifest_path(seed_root)))
    if not manifest:
        return None, []

    summary = {
        "label": str(manifest.get("bundle_label") or "Runtime Prior Bundle"),
        "profile": str(manifest.get("source_profile") or ""),
        "generated_at": str(manifest.get("generated_at") or ""),
        "artifact_count": int(len(manifest.get("artifacts", []) or [])),
    }

    artifacts: list[dict[str, Any]] = []
    for item in manifest.get("artifacts", []) or []:
        if not isinstance(item, dict):
            continue
        scopes = _normalize_string_list(item.get("tool_scopes"))
        if scopes and tool not in scopes and "*" not in scopes and "all" not in scopes:
            continue
        artifact = {
            "artifact_id": str(item.get("artifact_id") or ""),
            "label": str(item.get("label") or item.get("artifact_id") or "runtime prior"),
            "kind": str(item.get("kind") or ""),
            "bundle_path": str(item.get("bundle_path") or ""),
            "tool_scopes": scopes,
            "source_datasets": _normalize_string_list(item.get("source_datasets")),
            "training_tracks": _normalize_string_list(item.get("training_tracks")),
            "notes": str(item.get("notes") or ""),
            "generated_at": str(item.get("generated_at") or summary["generated_at"]),
            "sha256": str(item.get("sha256") or ""),
        }
        if item.get("size_bytes") is not None:
            artifact["size_bytes"] = int(item.get("size_bytes") or 0)
        if item.get("record_count") is not None:
            artifact["record_count"] = int(item.get("record_count") or 0)
        if item.get("summary_text") is not None:
            artifact["summary_text"] = str(item.get("summary_text") or "")
        artifacts.append(artifact)
    return summary, artifacts
