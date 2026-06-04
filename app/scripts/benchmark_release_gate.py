from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_gate import build_rawprep_benchmark_gate, write_rawprep_benchmark_gate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate whether measured benchmark evidence and RunPod smoke evidence are ready for v2 default-engine review."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that contains rawprep_benchmark.json/report.json.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write the gate artifact to the benchmark output directory as rawprep_release_gate.json.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit successfully only when the release gate is ready for default review.",
    )
    args = parser.parse_args()

    gate = (
        write_rawprep_benchmark_gate(args.output_dir, output_root=args.output_root)
        if args.write_canonical
        else build_rawprep_benchmark_gate(args.output_dir, output_root=args.output_root)
    )
    payload = json.dumps(gate.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if args.require_ready and not gate.ready_for_default_review:
        sys.exit(1)


if __name__ == "__main__":
    main()
