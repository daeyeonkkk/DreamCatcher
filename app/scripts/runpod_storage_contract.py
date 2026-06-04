from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_backend_import_path() -> None:
    backend_root = project_root() / "app" / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


ensure_backend_import_path()

from app.core.runpod_storage_contract import (  # noqa: E402
    build_runpod_storage_contract,
    write_runpod_storage_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical RunPod storage contract for DreamCatcher.")
    parser.add_argument("--workspace-root", default="/workspace")
    parser.add_argument("--app-root", default=None)
    parser.add_argument("--comfy-root", default="/workspace/runpod-slim/ComfyUI")
    parser.add_argument("--hf-home", default=None)
    parser.add_argument("--bootstrap-cache-root", default=None)
    parser.add_argument("--workflow-runtime-root", default=None)
    parser.add_argument("--workflow-staging-root", default=None)
    parser.add_argument("--rawprep-root", default=None)
    parser.add_argument("--rawprep-tmp-root", default=None)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--out", default=None, help="Optional JSON path for the canonical storage contract artifact.")
    parser.add_argument("--require-ok", action="store_true", help="Exit nonzero when the computed storage contract is not valid.")
    args = parser.parse_args()

    build_kwargs = {
        "workspace_root": args.workspace_root,
        "app_root": args.app_root,
        "comfy_root": args.comfy_root,
        "hf_home": args.hf_home,
        "bootstrap_cache_root": args.bootstrap_cache_root,
        "workflow_runtime_root": args.workflow_runtime_root,
        "workflow_staging_root": args.workflow_staging_root,
        "rawprep_root": args.rawprep_root,
        "rawprep_tmp_root": args.rawprep_tmp_root,
        "output_root": args.output_root,
    }

    contract = (
        write_runpod_storage_contract(artifact_path=args.out, **build_kwargs)
        if args.out
        else build_runpod_storage_contract(**build_kwargs)
    )
    print(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2))
    if args.require_ok and not contract.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
