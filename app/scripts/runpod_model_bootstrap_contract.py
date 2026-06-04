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

from app.core.runpod_model_bootstrap_contract import (  # noqa: E402
    build_runpod_model_bootstrap_contract,
    write_runpod_model_bootstrap_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical RunPod model bootstrap contract for DreamCatcher.")
    parser.add_argument("--workspace-root", default="/workspace")
    parser.add_argument("--app-root", default=None)
    parser.add_argument("--comfy-root", default="/workspace/runpod-slim/ComfyUI")
    parser.add_argument("--profile", choices=("frontier", "core", "pro", "labs"), default=None)
    parser.add_argument("--download-birefnet", action="store_true")
    parser.add_argument("--download-qwen", action="store_true")
    parser.add_argument("--download-qwen-2512", action="store_true")
    parser.add_argument("--download-qwen-judge", action="store_true")
    parser.add_argument("--download-flux2-dev", action="store_true")
    parser.add_argument("--download-klein", action="store_true")
    parser.add_argument("--download-fill", action="store_true")
    parser.add_argument("--download-qwen-layered", action="store_true")
    parser.add_argument("--download-z-image", action="store_true")
    parser.add_argument("--download-omnigen2", action="store_true")
    parser.add_argument("--download-all", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    build_kwargs = {
        "workspace_root": args.workspace_root,
        "app_root": args.app_root,
        "comfy_root": args.comfy_root,
        "model_profile": args.profile,
        "download_birefnet": args.download_birefnet,
        "download_qwen": args.download_qwen,
        "download_qwen_2512": args.download_qwen_2512,
        "download_qwen_judge": args.download_qwen_judge,
        "download_flux2_dev": args.download_flux2_dev,
        "download_klein": args.download_klein,
        "download_fill": args.download_fill,
        "download_qwen_layered": args.download_qwen_layered,
        "download_z_image": args.download_z_image,
        "download_omnigen2": args.download_omnigen2,
        "download_all": args.download_all,
    }

    contract = (
        write_runpod_model_bootstrap_contract(artifact_path=args.out, **build_kwargs)
        if args.out
        else build_runpod_model_bootstrap_contract(**build_kwargs)
    )
    print(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
