#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Print DreamCatcher model plan with storage hints.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--tier", choices=["warm", "cold", "all"], default="all")
    args = parser.parse_args()

    data = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    tiers = [args.tier] if args.tier != "all" else ["warm", "cold"]
    for tier in tiers:
        print(f"## {tier}")
        for item in data.get(tier, []):
            print(f"- {item['name']}")
            print(f"  repo: {item.get('repo_id', item.get('repo_url','(manual)'))}")
            print(f"  target: {item.get('target_subdir','models')}")
            files = item.get('files', [])
            if files:
                for f in files:
                    print(f"    - {f}")
            note = item.get('notes') or item.get('manual_note')
            if note:
                print(f"  note: {note}")


if __name__ == "__main__":
    main()
