from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .comfy_client import ComfyClient


def fetch_and_save(base_url: str, output_path: str) -> Dict[str, Any]:
    client = ComfyClient(base_url=base_url)
    inventory = client.object_info()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch ComfyUI /object_info and save it.")
    parser.add_argument("--base-url", required=True, help="ComfyUI base url, e.g. http://127.0.0.1:8188")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()
    fetch_and_save(base_url=args.base_url, output_path=args.out)


if __name__ == "__main__":
    main()
