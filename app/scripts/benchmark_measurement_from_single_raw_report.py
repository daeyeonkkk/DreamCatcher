from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
    write_rawprep_benchmark_measurement_from_single_raw_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive an official benchmark measurement JSON from a SingleRaw report timing artifact."
    )
    parser.add_argument("--sample-id", required=True, help="Official benchmark sample_id to update.")
    parser.add_argument("--report-path", required=True, help="Path to the SingleRaw report.json artifact to read.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument(
        "--status",
        default="measured",
        choices=["pending_measurement", "measured"],
        help="Measurement status to write.",
    )
    parser.add_argument("--note", action="append", default=[], help="Optional note to store in the result JSON.")
    parser.add_argument("--out", help="Optional JSON output path for the write summary.")
    args = parser.parse_args()

    record = write_rawprep_benchmark_measurement_from_single_raw_report(
        RawPrepBenchmarkMeasurementFromSingleRawReportRequest(
            sample_id=args.sample_id,
            report_path=args.report_path,
            output_root=args.output_root,
            status=args.status,
            notes=args.note,
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
