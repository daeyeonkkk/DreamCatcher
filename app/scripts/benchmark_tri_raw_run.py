from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_tri_raw_run import (
    RawPrepBenchmarkTriRawRunRequest,
    run_rawprep_benchmark_tri_raw_samples,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize official TriRaw benchmark samples, then optionally write measured benchmark evidence."
    )
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--manifest-path", help="Optional TriRaw manifest override.")
    parser.add_argument(
        "--run-root",
        default="_benchmark_runs/tri_raw",
        help="Output-root-relative directory used for per-sample TriRaw materialization runs.",
    )
    parser.add_argument(
        "--benchmark-output-dir",
        help="Optional benchmark output directory used to refresh rawprep_benchmark.json/report after the run.",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        default=[],
        help="Optional sample_id filter. Pass multiple times to run a subset of the official TriRaw manifest.",
    )
    parser.add_argument(
        "--requested-reference-policy",
        choices=["auto", "first", "middle", "last"],
        default="auto",
        help="Reference-frame preference used by the TriRaw preview runtime.",
    )
    parser.add_argument(
        "--skip-measurements",
        action="store_true",
        help="Only materialize TriRaw benchmark sample reports without writing official benchmark_result_path JSON files.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the run summary.")
    args = parser.parse_args()

    record = run_rawprep_benchmark_tri_raw_samples(
        RawPrepBenchmarkTriRawRunRequest(
            output_root=args.output_root,
            manifest_path=args.manifest_path,
            run_root=args.run_root,
            benchmark_output_dir=args.benchmark_output_dir,
            sample_ids=args.sample_id,
            requested_reference_policy=args.requested_reference_policy,
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
