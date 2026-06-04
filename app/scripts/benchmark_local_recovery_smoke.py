from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.rawprep_benchmark_local_recovery_smoke import (
    RawPrepBenchmarkLocalRecoverySmokeRequest,
    write_rawprep_benchmark_local_recovery_smoke,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local recovery smoke that verifies result retrieval artifacts and provider-pause readiness."
    )
    parser.add_argument("--output-dir", required=True, help="Benchmark output directory that will hold the local recovery smoke artifact.")
    parser.add_argument("--output-root", default="outputs", help="Output root used for benchmark artifacts.")
    parser.add_argument("--run-root", default="_benchmark_runs/local_recovery", help="Run root used for local recovery smoke session outputs.")
    parser.add_argument("--session-id", default="local_recovery_demo", help="Session id used for the local recovery smoke fixture.")
    parser.add_argument("--preset", default="master_archive", help="Delivery preset used to build the recovery package.")
    parser.add_argument("--out", help="Optional JSON output path for the smoke summary.")
    parser.add_argument("--require-passed", action="store_true", help="Exit successfully only when the local recovery smoke passes.")
    args = parser.parse_args()

    smoke = write_rawprep_benchmark_local_recovery_smoke(
        RawPrepBenchmarkLocalRecoverySmokeRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
            run_root=args.run_root,
            session_id=args.session_id,
            preset=args.preset,
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
