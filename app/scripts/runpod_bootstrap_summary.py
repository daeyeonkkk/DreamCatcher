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

from app.core.runpod_bootstrap_summary import write_runpod_bootstrap_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Write DreamCatcher RunPod bootstrap_summary.json from current runtime evidence.")
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--workflow-dir", required=True)
    parser.add_argument("--rawprep-healthcheck-path", required=True)
    parser.add_argument("--single-raw-healthcheck-path", required=True)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--comfy-python", required=True)
    parser.add_argument("--console-label", required=True)
    parser.add_argument("--primary-image", required=True)
    parser.add_argument("--fallback-pinned-image", required=True)
    parser.add_argument("--fallback-alias-image", required=True)
    parser.add_argument("--storage-contract-path", required=True)
    parser.add_argument("--model-bootstrap-contract-path", required=True)
    parser.add_argument("--custom-node-contract-path", required=True)
    args = parser.parse_args()

    payload = write_runpod_bootstrap_summary(
        summary_path=args.summary_out,
        workflow_dir=args.workflow_dir,
        rawprep_healthcheck_path=args.rawprep_healthcheck_path,
        single_raw_healthcheck_path=args.single_raw_healthcheck_path,
        backend_url=args.backend_url,
        comfy_root=args.comfy_root,
        comfy_python=args.comfy_python,
        console_label=args.console_label,
        primary_image=args.primary_image,
        fallback_pinned_image=args.fallback_pinned_image,
        fallback_alias_image=args.fallback_alias_image,
        storage_contract_path=args.storage_contract_path,
        model_bootstrap_contract_path=args.model_bootstrap_contract_path,
        custom_node_contract_path=args.custom_node_contract_path,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

