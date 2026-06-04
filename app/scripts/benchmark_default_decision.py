from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_default_decision import (
    RawPrepBenchmarkDefaultDecisionRequest,
    build_rawprep_benchmark_default_decision,
    write_rawprep_benchmark_default_decision,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a default-engine decision artifact from measured benchmark, local smoke, and release review evidence."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that contains measured evidence.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--label", help="Optional label to carry into the canonical packet refresh.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write the canonical rawprep_default_engine_decision.json artifact to the benchmark output directory.",
    )
    parser.add_argument(
        "--require-benchmark-ready",
        action="store_true",
        help="Exit successfully only when benchmark evidence is ready for a default-engine decision.",
    )
    args = parser.parse_args()

    decision = (
        write_rawprep_benchmark_default_decision(
            RawPrepBenchmarkDefaultDecisionRequest(
                output_dir=args.output_dir,
                output_root=args.output_root,
                label=args.label,
            )
        )
        if args.write_canonical
        else build_rawprep_benchmark_default_decision(args.output_dir, output_root=args.output_root)
    )
    payload = json.dumps(decision.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if args.require_benchmark_ready and not decision.benchmark_evidence_ready:
        sys.exit(1)


if __name__ == "__main__":
    main()
