from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_local_e2e_smoke import (
    RawPrepBenchmarkLocalE2ESmokeRequest,
    write_rawprep_benchmark_local_e2e_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local end-to-end smoke on curated SingleRaw and TriRaw benchmark samples and write a canonical smoke artifact."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that will hold the local E2E smoke artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--run-root", default="_benchmark_runs/local_e2e", help="Run root used for local smoke session outputs.")
    parser.add_argument("--single-raw-sample-id", help="Optional SingleRaw sample_id override.")
    parser.add_argument("--tri-raw-sample-id", help="Optional TriRaw sample_id override.")
    parser.add_argument(
        "--single-raw-quality-preset",
        choices=("balanced", "safe"),
        default="balanced",
        help="Quality preset used for the SingleRaw smoke run.",
    )
    parser.add_argument(
        "--single-raw-mode-preference",
        choices=("auto", "fast", "hq", "safe"),
        default="fast",
        help="Mode preference used for the SingleRaw smoke run.",
    )
    parser.add_argument(
        "--tri-raw-reference-policy",
        choices=("auto", "first", "middle", "last"),
        default="auto",
        help="Reference policy used for the TriRaw smoke run.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the smoke summary.")
    parser.add_argument("--require-passed", action="store_true", help="Exit successfully only when the local E2E smoke passes.")
    args = parser.parse_args()

    smoke = write_rawprep_benchmark_local_e2e_smoke(
        RawPrepBenchmarkLocalE2ESmokeRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
            run_root=args.run_root,
            single_raw_sample_id=args.single_raw_sample_id,
            tri_raw_sample_id=args.tri_raw_sample_id,
            single_raw_quality_preset=args.single_raw_quality_preset,
            single_raw_mode_preference=args.single_raw_mode_preference,
            tri_raw_reference_policy=args.tri_raw_reference_policy,
        )
    )
    payload = json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)
    if args.require_passed and not smoke.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
