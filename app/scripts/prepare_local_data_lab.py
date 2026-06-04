#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare DreamCatcher local data lab directories and summarize planned tracks.")
    parser.add_argument("--lab-root", default=str(repo_root() / "local_data_lab"), help="Path to the local data lab root.")
    args = parser.parse_args()

    lab_root = Path(args.lab_root)
    dataset_registry = read_yaml(lab_root / "dataset_registry.yaml")
    training_tracks = read_yaml(lab_root / "training_tracks.yaml")

    cache_root = ensure_directory(lab_root / "cache")
    runs_root = ensure_directory(lab_root / "runs")
    exports_root = ensure_directory(lab_root / "exports")
    logs_root = ensure_directory(lab_root / "logs")

    payload = {
        "lab_root": str(lab_root),
        "cache_root": str(cache_root),
        "runs_root": str(runs_root),
        "exports_root": str(exports_root),
        "logs_root": str(logs_root),
        "dataset_count": len(dataset_registry.get("datasets", []) or []),
        "track_count": len(training_tracks.get("tracks", []) or []),
        "datasets": [
            {
                "dataset_id": str(item.get("dataset_id") or ""),
                "cache_dir": str(lab_root / "cache" / str(item.get("local_cache_subdir") or item.get("dataset_id") or "dataset")),
                "download_priority": str(item.get("download_priority") or ""),
            }
            for item in dataset_registry.get("datasets", []) or []
            if isinstance(item, dict)
        ],
        "tracks": [
            {
                "track_id": str(item.get("track_id") or ""),
                "status": str(item.get("status") or ""),
                "local_output": str(item.get("local_output") or ""),
                "runtime_destination": str(item.get("runtime_destination") or ""),
            }
            for item in training_tracks.get("tracks", []) or []
            if isinstance(item, dict)
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
