from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_script_import_paths() -> None:
    repo_root = project_root()
    backend_root = repo_root / "app" / "backend"
    for candidate in (backend_root, repo_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


ensure_script_import_paths()

from app.core.rawprep_benchmark_runpod_smoke_plan import (
    RawPrepBenchmarkRunPodSmokePlanRequest,
    build_rawprep_benchmark_runpod_smoke_plan,
    write_rawprep_benchmark_runpod_smoke_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a canonical RunPod smoke sample plan from the SingleRaw benchmark manifest."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that should receive the smoke plan artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--manifest-path", help="Optional SingleRaw manifest path override.")
    parser.add_argument("--sample-id", help="Optional sample_id override from the SingleRaw manifest.")
    parser.add_argument(
        "--sample-working-root",
        default="outputs/_single_raw_healthcheck",
        help="RunPod working root used when single_raw_healthcheck.py performs the sample decode.",
    )
    parser.add_argument(
        "--runtime-output-path",
        default="app/runtime/single_raw_healthcheck.json",
        help="RunPod output path that should receive single_raw_healthcheck.json.",
    )
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write the canonical rawprep_runpod_smoke_plan.json artifact to the benchmark output directory.",
    )
    args = parser.parse_args()

    request = RawPrepBenchmarkRunPodSmokePlanRequest(
        output_dir=args.output_dir,
        output_root=args.output_root,
        manifest_path=args.manifest_path,
        sample_id=args.sample_id,
        sample_working_root=args.sample_working_root,
        runtime_output_path=args.runtime_output_path,
    )
    plan = (
        write_rawprep_benchmark_runpod_smoke_plan(request)
        if args.write_canonical
        else build_rawprep_benchmark_runpod_smoke_plan(request)
    )
    payload = json.dumps(plan.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
