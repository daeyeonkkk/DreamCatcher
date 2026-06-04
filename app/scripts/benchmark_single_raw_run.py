from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_single_raw_run import (
    RawPrepBenchmarkSingleRawRunRequest,
    run_rawprep_benchmark_single_raw_samples,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize official SingleRaw benchmark samples, then optionally bridge each report.json into measured benchmark evidence."
    )
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--manifest-path", help="Optional SingleRaw manifest override.")
    parser.add_argument(
        "--run-root",
        default="_benchmark_runs/single_raw",
        help="Output-root-relative directory used for per-sample SingleRaw materialization runs.",
    )
    parser.add_argument(
        "--benchmark-output-dir",
        help="Optional benchmark output directory used to refresh rawprep_benchmark.json/report after the run.",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        default=[],
        help="Optional sample_id filter. Pass multiple times to run a subset of the official SingleRaw manifest.",
    )
    parser.add_argument(
        "--quality-preset",
        choices=["balanced", "safe"],
        default="balanced",
        help="SingleRaw quality preset used when materializing the benchmark samples.",
    )
    parser.add_argument(
        "--mode-preference",
        choices=["auto", "fast", "hq", "safe"],
        default="fast",
        help="SingleRaw mode preference used when materializing the benchmark samples.",
    )
    parser.add_argument(
        "--skip-measurements",
        action="store_true",
        help="Only materialize SingleRaw benchmark sample reports without writing official benchmark_result_path JSON files.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the run summary.")
    args = parser.parse_args()

    record = run_rawprep_benchmark_single_raw_samples(
        RawPrepBenchmarkSingleRawRunRequest(
            output_root=args.output_root,
            manifest_path=args.manifest_path,
            run_root=args.run_root,
            benchmark_output_dir=args.benchmark_output_dir,
            sample_ids=args.sample_id,
            quality_preset=args.quality_preset,
            mode_preference=args.mode_preference,
            write_measurements=not args.skip_measurements,
        )
    )
    payload = json.dumps(record.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)


if __name__ == "__main__":
    main()
