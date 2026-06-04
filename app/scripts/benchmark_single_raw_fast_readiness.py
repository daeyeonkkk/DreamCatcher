from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_backend_import_path() -> None:
    repo_root = project_root()
    backend_root = repo_root / "app" / "backend"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


ensure_backend_import_path()

from app.core.rawprep_benchmark_single_raw_fast_readiness import (  # noqa: E402
    RawPrepSingleRawFastReadinessRequest,
    write_rawprep_single_raw_fast_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the canonical SingleRaw fast practical-readiness artifact.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--benchmark-report-path", default=None)
    parser.add_argument("--single-raw-healthcheck-path", default=None)
    parser.add_argument("--local-timing-target-ms", type=float, default=6000.0)
    parser.add_argument("--runpod-timing-target-ms", type=float, default=12000.0)
    args = parser.parse_args()

    artifact = write_rawprep_single_raw_fast_readiness(
        RawPrepSingleRawFastReadinessRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
            benchmark_report_path=args.benchmark_report_path,
            single_raw_healthcheck_path=args.single_raw_healthcheck_path,
            local_timing_target_ms=args.local_timing_target_ms,
            runpod_timing_target_ms=args.runpod_timing_target_ms,
        )
    )
    print(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2))
    return 0 if artifact.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
