from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml


@dataclass
class NativeTemplate:
    name: str
    tool: str
    official_doc: str
    ui_workflow_url: str
    capture_as: str
    notes: str


def load_registry(path: str | Path) -> List[NativeTemplate]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = data.get("native_templates", [])
    return [NativeTemplate(**item) for item in items]


def by_tool(path: str | Path) -> Dict[str, NativeTemplate]:
    return {item.tool: item for item in load_registry(path)}
