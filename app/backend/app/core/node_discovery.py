from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional
import json
import requests
import yaml


@dataclass
class ComfyEndpoint:
    base_url: str = "http://127.0.0.1:8188"
    timeout: int = 30

    def get_json(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


class NodeDiscoveryError(RuntimeError):
    """Raised when node discovery or alias resolution fails."""


class NodeDiscovery:
    def __init__(self, endpoint: ComfyEndpoint):
        self.endpoint = endpoint

    def fetch_object_info(self) -> Dict[str, Any]:
        return self.endpoint.get_json("/object_info")

    @staticmethod
    def load_aliases(path: str) -> Dict[str, List[str]]:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        if "aliases" in raw:
            aliases = raw.get("aliases", {})
            if not isinstance(aliases, dict):
                raise NodeDiscoveryError("Invalid alias config: 'aliases' must be a mapping.")
            return {str(k): [str(x) for x in v] for k, v in aliases.items()}

        logical_nodes = raw.get("logical_nodes", {})
        if not isinstance(logical_nodes, dict):
            raise NodeDiscoveryError("Invalid alias config: 'logical_nodes' must be a mapping.")

        converted: Dict[str, List[str]] = {}
        for alias, spec in logical_nodes.items():
            if not isinstance(spec, dict):
                raise NodeDiscoveryError(f"Invalid alias config for {alias}: expected mapping.")
            candidates = spec.get("candidates", [])
            if not isinstance(candidates, list):
                raise NodeDiscoveryError(f"Invalid alias config for {alias}: candidates must be a list.")
            converted[str(alias)] = [str(x) for x in candidates]
        return converted

    @staticmethod
    def resolve_aliases(
        object_info: Mapping[str, Any],
        alias_map: Mapping[str, Iterable[str]],
    ) -> Dict[str, str]:
        available = set(object_info.keys())
        resolved: Dict[str, str] = {}
        missing: Dict[str, List[str]] = {}

        for alias, candidates in alias_map.items():
            chosen: Optional[str] = None
            tried: List[str] = []
            for candidate in candidates:
                tried.append(candidate)
                if candidate in available:
                    chosen = candidate
                    break
            if chosen is None:
                missing[alias] = tried
            else:
                resolved[alias] = chosen

        if missing:
            raise NodeDiscoveryError(
                "Missing required node aliases: "
                + json.dumps(missing, ensure_ascii=False, indent=2)
            )
        return resolved

    @staticmethod
    def save_resolved_nodes(path: str, resolved: Mapping[str, str]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dict(resolved), f, ensure_ascii=False, indent=2)
