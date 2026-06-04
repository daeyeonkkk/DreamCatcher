from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rawprep_benchmark_sample_library import (
    RawPrepBenchmarkSampleLibrarySyncRequest,
    sync_rawprep_benchmark_sample_library,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy curated benchmark samples from a read-only photo source into benchmark/samples and refresh official manifests/result stubs."
    )
    parser.add_argument("--source-root", required=True, help="Read-only source directory that contains the original photo tree.")
    parser.add_argument(
        "--plan-path",
        default="benchmark/BENCHMARK_SAMPLE_LIBRARY.json",
        help="JSON plan that declares which source files to copy into the benchmark sample library.",
    )
    parser.add_argument(
        "--benchmark-sample-root",
        default="benchmark/samples",
        help="Repository-local destination root for curated benchmark samples.",
    )
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark result stubs.")
    parser.add_argument(
        "--manifest-merge-mode",
        choices=["replace", "merge_preserve_existing"],
        default="replace",
        help="How to apply discovered samples when refreshing the official manifests.",
    )
    parser.add_argument("--skip-manifest", action="store_true", help="Do not write refreshed manifests.")
    parser.add_argument("--skip-result-stubs", action="store_true", help="Do not write pending benchmark result stubs.")
    parser.add_argument("--out", help="Optional JSON output path for the sync summary.")
    args = parser.parse_args()

    sync = sync_rawprep_benchmark_sample_library(
        RawPrepBenchmarkSampleLibrarySyncRequest(
            source_root=args.source_root,
            plan_path=args.plan_path,
            benchmark_sample_root=args.benchmark_sample_root,
            output_root=args.output_root,
            manifest_merge_mode=args.manifest_merge_mode,
            write_manifest=not args.skip_manifest,
            write_result_stubs=not args.skip_result_stubs,
        )
    )
    payload = json.dumps(sync.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)


if __name__ == "__main__":
    main()
