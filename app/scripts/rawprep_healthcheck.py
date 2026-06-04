from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_backend_import_paths() -> None:
    app_root = project_root() / "app"
    backend_root = app_root / "backend"
    for candidate in (backend_root, app_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


ensure_backend_import_paths()

from backend.app.core.rawprep_catalog import required_tools_for_engine
from backend.app.core.rawprep_runner import detect_rawprep_tools, missing_required_tools


def dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate DreamCatcher TriRaw(rawprep) CLI prerequisites.")
    parser.add_argument(
        "--require",
        nargs="*",
        default=None,
        help="Explicit tool names to require. Overrides --engine-stack when provided.",
    )
    parser.add_argument(
        "--engine-stack",
        default="dreamraw_tri_v2",
        help="Engine stack to validate. Defaults to dreamraw_tri_v2.",
    )
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit successfully even if one or more required tools are missing.",
    )
    args = parser.parse_args()

    required_tools = args.require or required_tools_for_engine(args.engine_stack)
    tool_status = detect_rawprep_tools(required_tools)
    missing = missing_required_tools(tool_status, required_tools)
    report = {
        "ok": not missing,
        "engine_stack": args.engine_stack,
        "required_tools": required_tools,
        "missing_tools": missing,
        "tool_status": {name: dump_model(status) for name, status in tool_status.items()},
    }

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    if missing and not args.allow_missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
