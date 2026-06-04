from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_backend_import_paths() -> None:
    app_root = project_root() / "app"
    backend_root = app_root / "backend"
    for candidate in (backend_root, app_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


ensure_backend_import_paths()

from app.raw_engine_v2.single_raw.runtime import build_single_raw_runtime_health


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate DreamCatcher SingleRaw sensor decode runtime readiness.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--sample-raw",
        help="Optional RAW file path for a real sensor decode smoke check.",
    )
    parser.add_argument(
        "--sample-working-root",
        help="Optional output root used when --sample-raw is provided.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit successfully even if the sensor decode backend or sample decode is unavailable.",
    )
    args = parser.parse_args()

    report = build_single_raw_runtime_health(
        sample_raw_path=args.sample_raw,
        sample_working_root=args.sample_working_root,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if not report["ok"] and not args.allow_missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
