from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_local_ui_language_smoke import (
    RawPrepBenchmarkLocalUiLanguageSmokeRequest,
    write_rawprep_benchmark_local_ui_language_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit curated DreamCatcher studio UI surfaces and write a canonical Korean UI smoke artifact."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that will hold the local UI language smoke artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--out", help="Optional JSON output path for the smoke summary.")
    parser.add_argument("--require-passed", action="store_true", help="Exit successfully only when the local UI language smoke passes.")
    args = parser.parse_args()

    smoke = write_rawprep_benchmark_local_ui_language_smoke(
        RawPrepBenchmarkLocalUiLanguageSmokeRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
        )
    )
    payload = json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)
    if args.require_passed and not smoke.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
