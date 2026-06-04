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

PROJECT_ROOT = project_root()

from runpod.release_bundle_lib import PROJECT_ROOT as RELEASE_PROJECT_ROOT, build_release_bundle_preflight_report, load_manifest

from app.core.rawprep_benchmark_runpod_smoke_handoff import (
    RawPrepBenchmarkRunPodSmokeHandoffRequest,
    build_rawprep_benchmark_runpod_smoke_handoff,
    write_rawprep_benchmark_runpod_smoke_handoff,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the canonical local-to-RunPod smoke handoff by verifying DreamCatcher.zip, staging the smoke sample bundle, and embedding it into the app bundle."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that should receive the handoff artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--manifest-path", help="Optional SingleRaw manifest path override.")
    parser.add_argument("--sample-id", help="Optional SingleRaw sample_id override.")
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
    parser.add_argument(
        "--release-bundle-path",
        help="Optional DreamCatcher.zip path override. Defaults to the official artifact path from release_bundle_manifest.json.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip rebuilding/verifying DreamCatcher.zip and only assemble the handoff artifact from existing files.",
    )
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--write-canonical",
        action="store_true",
        help="Write rawprep_runpod_smoke_handoff.json plus the canonical smoke stage artifacts.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    release_bundle_path = (
        Path(args.release_bundle_path).expanduser().resolve()
        if args.release_bundle_path
        else (RELEASE_PROJECT_ROOT / manifest.official_artifact_name).resolve()
    )

    if not args.skip_preflight:
        report = build_release_bundle_preflight_report(RELEASE_PROJECT_ROOT, manifest, release_bundle_path)
        if not bool(report.get("ok")):
            print(json.dumps(report, indent=2, ensure_ascii=False))
            raise SystemExit(1)

    request = RawPrepBenchmarkRunPodSmokeHandoffRequest(
        output_dir=args.output_dir,
        output_root=args.output_root,
        manifest_path=args.manifest_path,
        sample_id=args.sample_id,
        sample_working_root=args.sample_working_root,
        runtime_output_path=args.runtime_output_path,
        release_bundle_path=str(release_bundle_path),
    )
    handoff = (
        write_rawprep_benchmark_runpod_smoke_handoff(request)
        if args.write_canonical
        else build_rawprep_benchmark_runpod_smoke_handoff(request)
    )
    payload = json.dumps(handoff.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
