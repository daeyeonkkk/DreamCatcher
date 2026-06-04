from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement_batch import (
    RawPrepBenchmarkMeasurementBatchRequest,
    load_rawprep_benchmark_measurement_batch_entries,
    write_rawprep_benchmark_measurement_batch,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write measured benchmark result JSON for multiple official benchmark samples from a JSON or JSONL batch file."
    )
    parser.add_argument("--input", required=True, help="Path to a JSON/JSONL file containing batch measurement entries.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--out", help="Optional JSON output path for the batch write summary.")
    args = parser.parse_args()

    batch = write_rawprep_benchmark_measurement_batch(
        RawPrepBenchmarkMeasurementBatchRequest(
            output_root=args.output_root,
            entries=load_rawprep_benchmark_measurement_batch_entries(args.input),
        )
    )
    payload = json.dumps(batch.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)


if __name__ == "__main__":
    main()
