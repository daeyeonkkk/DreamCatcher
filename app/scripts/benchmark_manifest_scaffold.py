from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_scaffold import (
    RawPrepBenchmarkScaffoldRequest,
    build_rawprep_benchmark_scaffold,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build manifest-ready benchmark sample scaffolds from a local SingleRaw or TriRaw source tree."
    )
    parser.add_argument("--mode", choices=["single_raw", "tri_raw"], required=True)
    parser.add_argument("--source-root", required=True, help="Root directory that contains benchmark sample files.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for default result stub locations.")
    parser.add_argument("--manifest-path", help="Optional manifest output path. Defaults to the official benchmark manifest.")
    parser.add_argument("--result-root", help="Optional directory used for benchmark_result_path stubs.")
    parser.add_argument(
        "--manifest-merge-mode",
        choices=["replace", "merge_preserve_existing"],
        default="replace",
        help="How to apply discovered samples when writing the manifest.",
    )
    parser.add_argument("--write-manifest", action="store_true", help="Write the generated manifest payload to disk.")
    parser.add_argument(
        "--write-result-stubs",
        action="store_true",
        help="Create pending-measurement result JSON stubs for every discovered sample.",
    )
    parser.add_argument("--out", help="Optional JSON output path for the scaffold summary itself.")
    args = parser.parse_args()

    scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode=args.mode,
            source_root=args.source_root,
            output_root=args.output_root,
            manifest_path=args.manifest_path,
            result_root=args.result_root,
            manifest_merge_mode=args.manifest_merge_mode,
            write_manifest=args.write_manifest,
            write_result_stubs=args.write_result_stubs,
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
