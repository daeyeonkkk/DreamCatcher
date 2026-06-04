from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@dataclass
class ResolvedNode:
    logical_name: str
    concrete_name: str
    strategy: str


class NodeAliasResolver:
    def __init__(self, alias_config: Dict[str, Any], object_info: Dict[str, Any]):
        self.alias_config = alias_config.get("logical_nodes", {})
        self.object_info = object_info
        self.available_names = list(object_info.keys())
        self.normalized_lookup = {normalize_name(name): name for name in self.available_names}

    @classmethod
    def from_files(cls, alias_path: str | Path, object_info_path: str | Path) -> "NodeAliasResolver":
        alias_config = yaml.safe_load(Path(alias_path).read_text(encoding="utf-8"))
        import json
        object_info = json.loads(Path(object_info_path).read_text(encoding="utf-8"))
        return cls(alias_config=alias_config, object_info=object_info)

    def resolve(self, logical_name: str) -> ResolvedNode:
        entry = self.alias_config.get(logical_name)
        if entry is None:
            raise KeyError(f"Unknown logical node alias: {logical_name}")

        candidates = entry.get("candidates", [])
        for candidate in candidates:
            if candidate in self.object_info:
                return ResolvedNode(logical_name=logical_name, concrete_name=candidate, strategy="exact")
        lower_map = {name.lower(): name for name in self.available_names}
        for candidate in candidates:
            hit = lower_map.get(candidate.lower())
            if hit:
                return ResolvedNode(logical_name=logical_name, concrete_name=hit, strategy="casefold")
        for candidate in candidates:
            hit = self.normalized_lookup.get(normalize_name(candidate))
            if hit:
                return ResolvedNode(logical_name=logical_name, concrete_name=hit, strategy="normalized")
        raise KeyError(
            f"Could not resolve logical node '{logical_name}'. Candidates={candidates}, "
            f"available_count={len(self.available_names)}"
        )
