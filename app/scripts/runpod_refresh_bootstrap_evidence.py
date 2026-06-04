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

from app.core.runpod_custom_node_contract import write_runpod_custom_node_contract  # noqa: E402
from app.core.runpod_model_bootstrap_contract import write_runpod_model_bootstrap_contract  # noqa: E402
from app.core.runpod_bootstrap_summary import write_runpod_bootstrap_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh DreamCatcher RunPod bootstrap evidence after bootstrap without rerunning the full bootstrap flow."
    )
    parser.add_argument("--workspace-root", default="/workspace")
    parser.add_argument("--app-root", default=None)
    parser.add_argument("--comfy-root", default="/workspace/runpod-slim/ComfyUI")
    parser.add_argument("--workflow-dir", default=None)
    parser.add_argument("--rawprep-healthcheck-path", default=None)
    parser.add_argument("--single-raw-healthcheck-path", default=None)
    parser.add_argument("--storage-contract-path", default=None)
    parser.add_argument("--summary-out", default=None)
    parser.add_argument("--model-contract-out", default=None)
    parser.add_argument("--custom-node-contract-out", default=None)
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--object-info-path", default=None)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--comfy-python", default="python")
    parser.add_argument("--console-label", default="ComfyUI - CUDA 12.8")
    parser.add_argument("--primary-image", default="runpod/comfyui:1.4.1-cuda12.8")
    parser.add_argument("--fallback-pinned-image", default="runpod/comfyui:1.3.0-cuda12.8")
    parser.add_argument("--fallback-alias-image", default="runpod/comfyui:cuda12.8")
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
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    app_root = Path(args.app_root).resolve() if args.app_root else (workspace_root / "DreamCatcher").resolve()
    runtime_root = app_root / "app" / "runtime"

    workflow_dir = Path(args.workflow_dir).resolve() if args.workflow_dir else (app_root / "app" / "workflows" / "runtime").resolve()
    rawprep_healthcheck_path = (
        Path(args.rawprep_healthcheck_path).resolve() if args.rawprep_healthcheck_path else (runtime_root / "rawprep_healthcheck.json").resolve()
    )
    single_raw_healthcheck_path = (
        Path(args.single_raw_healthcheck_path).resolve() if args.single_raw_healthcheck_path else (runtime_root / "single_raw_healthcheck.json").resolve()
    )
    storage_contract_path = (
        Path(args.storage_contract_path).resolve() if args.storage_contract_path else (runtime_root / "runpod_storage_contract.json").resolve()
    )
    summary_out = Path(args.summary_out).resolve() if args.summary_out else (runtime_root / "bootstrap_summary.json").resolve()
    model_contract_out = (
        Path(args.model_contract_out).resolve() if args.model_contract_out else (runtime_root / "runpod_model_bootstrap_contract.json").resolve()
    )
    custom_node_contract_out = (
        Path(args.custom_node_contract_out).resolve() if args.custom_node_contract_out else (runtime_root / "runpod_custom_node_contract.json").resolve()
    )
    manifest_path = (
        Path(args.manifest_path).resolve() if args.manifest_path else (app_root / "app" / "custom_nodes" / "custom_node_manifest.yaml").resolve()
    )
    object_info_path = (
        Path(args.object_info_path).resolve() if args.object_info_path else (runtime_root / "object_info.json").resolve()
    )

    model_contract = write_runpod_model_bootstrap_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=args.comfy_root,
        model_profile=args.profile,
        download_birefnet=args.download_birefnet,
        download_qwen=args.download_qwen,
        download_qwen_2512=args.download_qwen_2512,
        download_qwen_judge=args.download_qwen_judge,
        download_flux2_dev=args.download_flux2_dev,
        download_klein=args.download_klein,
        download_fill=args.download_fill,
        download_qwen_layered=args.download_qwen_layered,
        download_z_image=args.download_z_image,
        download_omnigen2=args.download_omnigen2,
        download_all=args.download_all,
        artifact_path=model_contract_out,
    )
    custom_node_contract = write_runpod_custom_node_contract(
        workspace_root=workspace_root,
        app_root=app_root,
        comfy_root=args.comfy_root,
        manifest_path=manifest_path,
        object_info_path=object_info_path,
        workflow_root=workflow_dir,
        artifact_path=custom_node_contract_out,
    )
    summary = write_runpod_bootstrap_summary(
        summary_path=summary_out,
        workflow_dir=workflow_dir,
        rawprep_healthcheck_path=rawprep_healthcheck_path,
        single_raw_healthcheck_path=single_raw_healthcheck_path,
        backend_url=args.backend_url,
        comfy_root=args.comfy_root,
        comfy_python=args.comfy_python,
        console_label=args.console_label,
        primary_image=args.primary_image,
        fallback_pinned_image=args.fallback_pinned_image,
        fallback_alias_image=args.fallback_alias_image,
        storage_contract_path=storage_contract_path,
        model_bootstrap_contract_path=model_contract_out,
        custom_node_contract_path=custom_node_contract_out,
    )

    payload = {
        "ok": bool(model_contract.ok) and bool(custom_node_contract.ok),
        "summary_path": str(summary_out),
        "model_contract_path": str(model_contract_out),
        "custom_node_contract_path": str(custom_node_contract_out),
        "model_bootstrap_contract": model_contract.model_dump(),
        "custom_node_contract": custom_node_contract.model_dump(),
        "bootstrap_summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
