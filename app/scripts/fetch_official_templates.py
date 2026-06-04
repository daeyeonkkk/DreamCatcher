#!/usr/bin/env python3
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = PROJECT_ROOT / "seed_bundle" / "runtime_config" / "native_templates.yaml"
DEFAULT_OUT_DIR = PROJECT_ROOT / "seed_bundle" / "staging_templates"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official ComfyUI UI workflow templates into the local seed bundle staging area.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    data = yaml.safe_load(Path(args.registry).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for item in data.get("native_templates", []):
        name = item["name"].lower().replace(" ", "_").replace(".", "").replace("-", "_")
        url = item["ui_workflow_url"]
        target = out_dir / f"{name}.ui.json"
        print(f"downloading {item['name']} -> {target.name}")
        with urllib.request.urlopen(url) as resp:
            target.write_bytes(resp.read())


if __name__ == "__main__":
    main()
