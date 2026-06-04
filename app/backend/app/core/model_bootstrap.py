from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


def load_manifest(path: str) -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def planned_downloads(path: str, tier: str = "warm") -> List[Dict[str, Any]]:
    manifest = load_manifest(path)
    return list(manifest.get(tier, []))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print DreamCatcher model bootstrap plan.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--tier", default="warm", choices=["warm", "cold"])
    args = parser.parse_args()

    for item in planned_downloads(args.manifest, args.tier):
        print(f"- {item['name']} -> {item.get('target_subdir','models')} ({item['kind']})")


if __name__ == "__main__":
    main()
