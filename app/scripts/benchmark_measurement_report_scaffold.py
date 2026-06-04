from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement_report_scaffold import (
    RawPrepBenchmarkMeasurementReportScaffoldRequest,
    build_rawprep_benchmark_measurement_report_scaffold,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover SingleRaw report.json timing artifacts for official benchmark samples and scaffold batch bridge input."
    )
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--manifest-path", help="Optional SingleRaw benchmark manifest path.")
    parser.add_argument("--search-root", help="Optional directory to search for SingleRaw report.json artifacts.")
    parser.add_argument("--batch-input-path", help="Optional JSONL output path for the generated batch bridge input.")
    parser.add_argument("--write-batch-input", action="store_true", help="Write the generated batch bridge input JSONL.")
    parser.add_argument(
        "--include-existing-measurements",
        action="store_true",
        help="Include samples that already have measured benchmark_result_path JSON.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the scaffold summary.")
    args = parser.parse_args()

    scaffold = build_rawprep_benchmark_measurement_report_scaffold(
        RawPrepBenchmarkMeasurementReportScaffoldRequest(
            output_root=args.output_root,
            manifest_path=args.manifest_path,
            search_root=args.search_root,
            batch_input_path=args.batch_input_path,
            write_batch_input=args.write_batch_input,
            skip_existing_measurements=not args.include_existing_measurements,
        )
    )
    payload = json.dumps(scaffold.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)


if __name__ == "__main__":
    main()
