#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_repo(path: Path, *, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _format_band(stats: dict[str, Any], *, low_key: str = "p10", high_key: str = "p90", precision: int = 2) -> str | None:
    low = stats.get(low_key)
    high = stats.get(high_key)
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return None
    return f"{low:.{precision}f}..{high:.{precision}f}"


def json_artifact_summary(payload: dict[str, Any], *, record_count: int | None) -> str | None:
    tool_stats = payload.get("tool_stats")
    if isinstance(tool_stats, dict) and tool_stats:
        parts: list[str] = []
        for key, value in list(tool_stats.items())[:3]:
            if not isinstance(value, dict):
                continue
            count = value.get("decision_count")
            if isinstance(count, int):
                parts.append(f"{key} {count}")
        if parts:
            return ", ".join(parts)

    category_counts = payload.get("category_counts")
    if isinstance(category_counts, dict) and category_counts:
        return ", ".join(f"{key} {value}" for key, value in list(category_counts.items())[:4])

    adjustment_stats = payload.get("adjustment_stats")
    if isinstance(adjustment_stats, dict) and adjustment_stats:
        exposure = adjustment_stats.get("Exposure2012")
        highlights = adjustment_stats.get("Highlights2012")
        parts: list[str] = []
        if isinstance(exposure, dict):
            band = _format_band(exposure)
            if band:
                parts.append(f"exp {band}")
        if isinstance(highlights, dict):
            band = _format_band(highlights, precision=0)
            if band:
                parts.append(f"hl {band}")
        if parts:
            return " | ".join(parts)

    rendering_stats = payload.get("rendering_parameter_stats")
    if isinstance(rendering_stats, dict) and rendering_stats:
        exposure = rendering_stats.get("Exposure")
        temperature = rendering_stats.get("Temperature")
        parts = []
        if isinstance(exposure, dict):
            band = _format_band(exposure)
            if band:
                parts.append(f"exp {band}")
        if isinstance(temperature, dict):
            band = _format_band(temperature, precision=0)
            if band:
                parts.append(f"temp {band}")
        if parts:
            return " | ".join(parts)

    if record_count:
        return f"{record_count} records staged"
    return None


def json_artifact_metadata(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".json":
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(payload, dict):
        return {}
    record_count = payload.get("sample_count")
    if record_count is None:
        record_count = payload.get("entry_count")
    if record_count is None:
        record_count = payload.get("decision_count")
    if record_count is None:
        samples = payload.get("samples")
        if isinstance(samples, list):
            record_count = len(samples)
    if record_count is None:
        entries = payload.get("entries")
        if isinstance(entries, list):
            record_count = len(entries)
    metadata: dict[str, Any] = {}
    if isinstance(record_count, int):
        metadata["record_count"] = record_count
    elif isinstance(record_count, float) and record_count.is_integer():
        metadata["record_count"] = int(record_count)
    summary = json_artifact_summary(payload, record_count=metadata.get("record_count"))
    if summary:
        metadata["summary_text"] = summary
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compact DreamCatcher runtime priors from the local data lab into seed_bundle/runtime_priors.")
    parser.add_argument("--plan", default=str(repo_root() / "local_data_lab" / "runtime_export_plan.yaml"), help="Path to the runtime export plan.")
    parser.add_argument("--seed-root", default=str(repo_root() / "seed_bundle"), help="Seed bundle root to receive the exported runtime priors.")
    parser.add_argument("--clean", action="store_true", help="Delete existing runtime_priors contents before exporting.")
    parser.add_argument("--strict", action="store_true", help="Fail if any required source artifact is missing.")
    args = parser.parse_args()

    root = repo_root()
    plan_path = Path(args.plan)
    seed_root = Path(args.seed_root)
    plan = read_yaml(plan_path)
    runtime_root = seed_root / "runtime_priors"
    if args.clean and runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    manifest_artifacts: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for item in plan.get("artifacts", []) or []:
        if not isinstance(item, dict):
            continue
        source_relpath = str(item.get("source_relpath") or "").strip()
        destination_relpath = str(item.get("destination_relpath") or "").strip()
        if not source_relpath or not destination_relpath:
            continue

        source_path = (root / source_relpath).resolve()
        if not source_path.exists():
            if bool(item.get("required")):
                missing_required.append(source_relpath)
            continue

        destination_path = runtime_root / destination_relpath
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

        artifact_metadata = {
            "artifact_id": str(item.get("artifact_id") or destination_path.stem),
            "label": str(item.get("label") or destination_path.stem),
            "kind": str(item.get("kind") or ""),
            "bundle_path": relative_to_repo(destination_path, root=root),
            "source_relpath": source_relpath,
            "tool_scopes": normalize_string_list(item.get("tool_scopes")),
            "source_datasets": normalize_string_list(item.get("source_datasets")),
            "training_tracks": normalize_string_list(item.get("training_tracks")),
            "notes": str(item.get("notes") or ""),
            "generated_at": utc_now_iso(),
            "sha256": sha256_file(destination_path),
            "size_bytes": int(destination_path.stat().st_size),
        }
        artifact_metadata.update(json_artifact_metadata(destination_path))
        manifest_artifacts.append(artifact_metadata)

    if missing_required and args.strict:
        raise SystemExit("Missing required runtime prior sources: " + ", ".join(missing_required))

    manifest = {
        "version": str(plan.get("version") or "2026-03-26"),
        "bundle_label": str(plan.get("bundle_label") or "DreamCatcher Runtime Prior Bundle"),
        "source_profile": str(plan.get("profile") or ""),
        "generated_at": utc_now_iso(),
        "bundle_notes": normalize_string_list(plan.get("bundle_notes")),
        "artifacts": manifest_artifacts,
        "missing_required_sources": missing_required,
    }

    manifest_path = runtime_root / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "artifact_count": len(manifest_artifacts),
                "missing_required_sources": missing_required,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
