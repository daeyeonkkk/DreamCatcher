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

from app.core.runpod_custom_node_contract import (  # noqa: E402
    build_runpod_custom_node_contract,
    write_runpod_custom_node_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical RunPod custom-node contract for DreamCatcher.")
    parser.add_argument("--workspace-root", default="/workspace")
    parser.add_argument("--app-root", default=None)
    parser.add_argument("--comfy-root", default="/workspace/runpod-slim/ComfyUI")
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--object-info-path", default=None)
    parser.add_argument("--workflow-root", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--require-ok", action="store_true")
    args = parser.parse_args()

    build_kwargs = {
        "workspace_root": args.workspace_root,
        "app_root": args.app_root,
        "comfy_root": args.comfy_root,
        "manifest_path": args.manifest_path,
        "object_info_path": args.object_info_path,
        "workflow_root": args.workflow_root,
    }

    contract = (
        write_runpod_custom_node_contract(artifact_path=args.out, **build_kwargs)
        if args.out
        else build_runpod_custom_node_contract(**build_kwargs)
    )
    print(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2))
    if args.require_ok and not contract.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
