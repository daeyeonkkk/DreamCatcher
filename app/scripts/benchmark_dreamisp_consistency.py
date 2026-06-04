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

from app.core.rawprep_benchmark_dreamisp_consistency import (  # noqa: E402
    RawPrepDreamISPConsistencyRequest,
    write_rawprep_dreamisp_consistency,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the canonical DreamISP consistency smoke artifact.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--local-e2e-smoke-path", default=None)
    args = parser.parse_args()

    artifact = write_rawprep_dreamisp_consistency(
        RawPrepDreamISPConsistencyRequest(
            output_dir=args.output_dir,
            output_root=args.output_root,
            local_e2e_smoke_path=args.local_e2e_smoke_path,
        )
    )
    print(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2))
    return 0 if artifact.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
