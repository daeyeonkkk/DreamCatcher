from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_review import (
    build_rawprep_benchmark_release_review,
    write_rawprep_benchmark_release_review,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a release-review snapshot that combines measured benchmark, release gate, and RunPod smoke evidence."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that contains benchmark artifacts.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write the canonical rawprep_release_review.json artifact to the benchmark output directory.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit successfully only when the review snapshot is ready for human default-engine review.",
    )
    args = parser.parse_args()

    review = (
        write_rawprep_benchmark_release_review(args.output_dir, output_root=args.output_root)
        if args.write_canonical
        else build_rawprep_benchmark_release_review(args.output_dir, output_root=args.output_root)
    )
    payload = json.dumps(review.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if args.require_ready and not review.ready_for_human_review:
        sys.exit(1)


if __name__ == "__main__":
    main()
