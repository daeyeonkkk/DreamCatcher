#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.seed_bundle import inspect_seed_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify required DreamCatcher local seed bundle files.")
    parser.add_argument("--seed-root", required=True)
    args = parser.parse_args()

    status = inspect_seed_bundle(args.seed_root)
    print(f"seed root: {status.root}")
    print(f"found api workflows: {', '.join(status.found_api_workflows) if status.found_api_workflows else '(none)'}")
    has_errors = False
    if status.placeholder_api_workflows:
        print(f"placeholder api workflows: {', '.join(status.placeholder_api_workflows)}")
        print("ERROR: replace placeholder API workflows with real ComfyUI Save (API Format) exports.")
        has_errors = True
    if status.missing_files:
        print("missing files:")
        for item in status.missing_files:
            print(f" - {item}")
        has_errors = True
    if has_errors:
        raise SystemExit(1)
    print("seed bundle is complete")


if __name__ == "__main__":
    main()
