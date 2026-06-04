from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any

import yaml


def git_head(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo), text=True).strip()


def git_remote(repo: Path) -> str:
    try:
        return subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=str(repo), text=True).strip()
    except Exception:
        return ""


def freeze_refs(comfy_root: str, out_path: str) -> Dict[str, Any]:
    comfy = Path(comfy_root)
    custom_nodes = comfy / "custom_nodes"

    data: Dict[str, Any] = {
        "comfy_core": {
            "repo": git_remote(comfy),
            "ref": git_head(comfy),
        },
        "custom_nodes": [],
    }

    if custom_nodes.exists():
        for node_dir in sorted(custom_nodes.iterdir()):
            if not node_dir.is_dir():
                continue
            git_dir = node_dir / ".git"
            if not git_dir.exists():
                continue
            data["custom_nodes"].append(
                {
                    "name": node_dir.name,
                    "repo": git_remote(node_dir),
                    "ref": git_head(node_dir),
                }
            )

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze current ComfyUI/core and custom-node refs into a lock file.")
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    freeze_refs(args.comfy_root, args.out)


if __name__ == "__main__":
    main()
