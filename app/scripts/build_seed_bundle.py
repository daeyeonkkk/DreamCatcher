#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tarfile
from pathlib import Path


ALLOWED_TOP_LEVEL = [
    "api_workflows",
    "comfy.settings.json",
    "config.ini",
    "extra_model_paths.yaml",
    "pinned_refs.lock.yaml",
    "public_dataset_manifest.yaml",
    "reference_runtime",
    "resolved_nodes.json",
    "runtime_priors",
    "runtime_config",
    "workflow_manifest.yaml",
    "presets",
    "styles",
]


def add_path(tf: tarfile.TarFile, path: Path, arcname: str) -> None:
    if path.is_dir():
        for child in sorted(path.iterdir()):
            add_path(tf, child, f"{arcname}/{child.name}")
    elif path.exists():
        tf.add(path, arcname=arcname)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a small DreamCatcher local seed bundle.")
    parser.add_argument("--seed-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    seed_root = Path(args.seed_root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(out, "w:gz") as tf:
        for name in ALLOWED_TOP_LEVEL:
            path = seed_root / name
            if path.exists():
                add_path(tf, path, name)

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"built {out} ({size_mb:.2f} MB)")
    if size_mb > 3072:
        raise SystemExit("Seed bundle exceeded 3GB limit")


if __name__ == "__main__":
    main()
