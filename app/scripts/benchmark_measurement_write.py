from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementWriteRequest,
    write_rawprep_benchmark_measurement,
)


def _parse_metric_entries(entries: list[str]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for entry in entries:
        key, separator, value = entry.partition("=")
        metric_key = key.strip()
        if separator != "=" or not metric_key:
            raise ValueError(f"Invalid metric entry '{entry}'. Use key=value.")
        metrics[metric_key] = float(value)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write measured benchmark result JSON for an official benchmark sample entry."
    )
    parser.add_argument("--sample-id", required=True, help="Official benchmark sample_id to update.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument(
        "--status",
        default="measured",
        choices=["pending_measurement", "measured"],
        help="Measurement status to write.",
    )
    parser.add_argument("--timing-ms", type=float, help="Measured processing time in milliseconds.")
    parser.add_argument("--metric", action="append", default=[], help="Metric entry formatted as key=value.")
    parser.add_argument("--fallback-mode", help="Optional fallback mode used for this sample.")
    parser.add_argument("--note", action="append", default=[], help="Optional note to store in the result JSON.")
    parser.add_argument("--out", help="Optional JSON output path for the write summary.")
    args = parser.parse_args()

    record = write_rawprep_benchmark_measurement(
        RawPrepBenchmarkMeasurementWriteRequest(
            sample_id=args.sample_id,
            output_root=args.output_root,
            status=args.status,
            timing_ms=args.timing_ms,
            metrics=_parse_metric_entries(args.metric),
            fallback_mode=args.fallback_mode,
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
