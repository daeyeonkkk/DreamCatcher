from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_service import build_rawprep_benchmark_foundation_health


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate DreamCatcher benchmark foundation manifests and measured result references."
    )
    parser.add_argument("--output-root", default="outputs", help="Output root used to resolve benchmark_result_path values.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="Exit successfully only when the foundation is measured-ready.",
    )
    args = parser.parse_args()

    report = build_rawprep_benchmark_foundation_health(output_root=args.output_root)
    payload = json.dumps(report.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if not report.ok:
        sys.exit(1)
    if args.require_measured and report.status != "measured_ready":
        sys.exit(1)


if __name__ == "__main__":
    main()
