from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_measurement_batch import (
    load_rawprep_benchmark_measurement_batch_entries,
    load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries,
)
from app.core.rawprep_benchmark_packet import (
    RawPrepBenchmarkPacketRequest,
    write_rawprep_benchmark_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble a measured benchmark release packet by optionally importing batch measurements, rebuilding the benchmark report, and writing smoke/gate/review artifacts."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that will hold the assembled evidence.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--label", help="Optional label recorded in the benchmark packet.")
    parser.add_argument(
        "--measurement-input",
        help="Optional JSON/JSONL file containing batch measurement entries to write before assembling the packet.",
    )
    parser.add_argument(
        "--measurement-report-input",
        help="Optional JSON/JSONL file containing batch entries with sample_id and SingleRaw report_path to bridge into official measurements before assembling the packet.",
    )
    parser.add_argument(
        "--auto-scaffold-single-raw-reports",
        action="store_true",
        help="Auto-discover SingleRaw report.json artifacts from the official manifest before assembling the packet.",
    )
    parser.add_argument(
        "--measurement-report-manifest-path",
        help="Optional manifest override used when auto-scaffolding SingleRaw report bridge entries.",
    )
    parser.add_argument(
        "--measurement-report-search-root",
        help="Optional search root used when auto-scaffolding SingleRaw report bridge entries.",
    )
    parser.add_argument(
        "--measurement-report-batch-input-path",
        help="Optional JSONL output path used when writing the auto-scaffolded SingleRaw report bridge batch input.",
    )
    parser.add_argument(
        "--write-measurement-report-batch-input",
        action="store_true",
        help="Write the auto-scaffolded SingleRaw report bridge entries to a JSONL batch input file before assembling the packet.",
    )
    parser.add_argument(
        "--include-existing-report-measurements",
        action="store_true",
        help="Include SingleRaw samples that already have measured benchmark_result_path JSON when auto-scaffolding report bridge entries.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the packet summary.")
    parser.add_argument("--skip-runpod-smoke", action="store_true", help="Do not materialize the RunPod smoke artifact unless gate/review requires it.")
    parser.add_argument("--skip-release-gate", action="store_true", help="Do not materialize the release gate unless review requires it.")
    parser.add_argument("--skip-release-review", action="store_true", help="Do not materialize the release review snapshot.")
    parser.add_argument("--require-ready", action="store_true", help="Exit successfully only when the packet is ready for human review.")
    args = parser.parse_args()

    write_release_review = not args.skip_release_review
    write_release_gate = write_release_review or not args.skip_release_gate
    write_runpod_smoke = write_release_gate or not args.skip_runpod_smoke
    measurement_entries = (
        load_rawprep_benchmark_measurement_batch_entries(args.measurement_input)
        if args.measurement_input
        else []
    )
    measurement_report_entries = (
        load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries(args.measurement_report_input)
        if args.measurement_report_input
        else []
    )

    packet = write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
            label=args.label,
            measurement_entries=measurement_entries,
            measurement_report_entries=measurement_report_entries,
            measurement_report_scaffold_enabled=args.auto_scaffold_single_raw_reports,
            measurement_report_manifest_path=args.measurement_report_manifest_path,
            measurement_report_search_root=args.measurement_report_search_root,
            measurement_report_batch_input_path=args.measurement_report_batch_input_path,
            write_measurement_report_batch_input=args.write_measurement_report_batch_input,
            include_existing_report_measurements=args.include_existing_report_measurements,
            write_runpod_smoke=write_runpod_smoke,
            write_release_gate=write_release_gate,
            write_release_review=write_release_review,
        )
    )
    payload = json.dumps(packet.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if args.require_ready and not packet.ready_for_human_review:
        sys.exit(1)


if __name__ == "__main__":
    main()
