from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_script_import_paths() -> None:
    repo_root = project_root()
    backend_root = repo_root / "app" / "backend"
    for candidate in (backend_root, repo_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


ensure_script_import_paths()

from app.core.rawprep_benchmark_runpod_smoke import (
    build_rawprep_benchmark_runpod_smoke,
    write_rawprep_benchmark_runpod_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture RunPod bootstrap and healthcheck evidence into a canonical benchmark smoke artifact."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that should receive the smoke artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write the canonical rawprep_runpod_smoke.json artifact to the benchmark output directory.",
    )
    parser.add_argument(
        "--require-passed",
        action="store_true",
        help="Exit successfully only when the RunPod smoke evidence passes the current bootstrap checks.",
    )
    args = parser.parse_args()

    smoke = (
        write_rawprep_benchmark_runpod_smoke(args.output_dir, output_root=args.output_root)
        if args.write_canonical
        else build_rawprep_benchmark_runpod_smoke(args.output_dir, output_root=args.output_root)
    )
    payload = json.dumps(smoke.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if args.require_passed and not smoke.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
