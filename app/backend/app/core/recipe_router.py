from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .frontier_dataset_activation import frontier_dataset_activation_for_tool
from .public_dataset_priors import public_priors_for_tool
from .runtime_prior_bundle import runtime_priors_for_tool


@dataclass
class RecipeDecision:
    recipe_id: str
    tool: str
    selection_profile: str
    execution_engine: str
    workflow_source: str
    workflow_path: str
    model_family: str | None
    maturity: str | None
    license: str | None
    warm_models: list[str]
    cold_models: list[str]
    notes: str
    watch_models: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    public_priors: list[dict[str, Any]] = field(default_factory=list)
    bootstrap_rules: list[str] = field(default_factory=list)
    community_takeaways: list[str] = field(default_factory=list)
    runtime_prior_bundle: dict[str, Any] | None = None
    runtime_prior_artifacts: list[dict[str, Any]] = field(default_factory=list)
    frontier_dataset_activation: dict[str, Any] | None = None
    frontier_dataset_items: list[dict[str, Any]] = field(default_factory=list)


AI_CAPABLE_TOOLS = {"removeBg", "replaceBg", "relight", "replaceObject", "expandCanvas", "retouch", "enhance"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def app_root() -> Path:
    return repo_root() / "app"


def runtime_root() -> Path:
    return app_root() / "workflows" / "runtime"


def reference_runtime_root() -> Path:
    return repo_root() / "seed_bundle" / "reference_runtime" / "workflows" / "runtime"


def workflow_manifest_path(seed_root: Path) -> Path:
    return seed_root / "workflow_manifest.yaml"


def workflow_selection_profile() -> str | None:
    raw_value = os.getenv("DREAMCATCHER_WORKFLOW_PROFILE")
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    return normalized or None


@lru_cache(maxsize=8)
def load_workflow_manifest(manifest_path: str) -> dict[str, Any]:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data if isinstance(data, dict) else {}


def clear_workflow_manifest_cache() -> None:
    load_workflow_manifest.cache_clear()


def resolve_runtime_workflow(filename: str) -> tuple[str, str]:
    materialized_path = runtime_root() / filename
    if materialized_path.exists():
        return "runtime-template", str(materialized_path)

    reference_path = reference_runtime_root() / filename
    if reference_path.exists():
        return "reference-runtime", str(reference_path)

    return "runtime-template", str(materialized_path)


def normalize_tool_key(tool: str) -> str:
    normalized = tool.strip()
    aliases = {
        "removebg": "removeBg",
        "backgroundremove": "removeBg",
        "replacebg": "replaceBg",
        "backgroundreplace": "replaceBg",
        "relight": "relight",
        "replaceobject": "replaceObject",
        "objectreplace": "replaceObject",
        "expandcanvas": "expandCanvas",
        "canvasexpand": "expandCanvas",
        "outpaint": "expandCanvas",
        "retouch": "retouch",
        "enhance": "enhance",
        "finish": "finish",
        "compare": "compare",
    }
    key = "".join(ch for ch in normalized if ch.isalnum())
    return aliases.get(key.lower(), normalized)


def is_ai_capable_tool(tool: str) -> bool:
    return normalize_tool_key(tool) in AI_CAPABLE_TOOLS


def _resolve_seed_root(seed_root: str | Path) -> Path:
    seed_root_path = Path(seed_root)
    if not seed_root_path.is_absolute():
        seed_root_path = (repo_root() / seed_root_path).resolve()
    return seed_root_path


def _manifest_profile_name(manifest: dict[str, Any], explicit_profile: str | None) -> str:
    selected_profile = explicit_profile or workflow_selection_profile() or str(manifest.get("active_profile") or "").strip()
    if not selected_profile:
        raise ValueError("workflow_manifest.yaml is missing active_profile.")
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict) or selected_profile not in profiles:
        raise ValueError(f"Workflow selection profile is not defined: {selected_profile}")
    return selected_profile


def _recipe_manifest_entry(
    tool: str,
    *,
    seed_root_path: Path,
    profile: str | None,
) -> tuple[str, dict[str, Any], str]:
    manifest = load_workflow_manifest(str(workflow_manifest_path(seed_root_path)))
    profile_name = _manifest_profile_name(manifest, profile)
    profiles = manifest.get("profiles") or {}
    profile_payload = profiles[profile_name]
    defaults = profile_payload.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError(f"Workflow selection profile is missing defaults: {profile_name}")
    recipe_id = defaults.get(tool)
    if not isinstance(recipe_id, str) or not recipe_id.strip():
        raise ValueError(f"Workflow selection profile has no default recipe for tool: {tool}")
    recipes = manifest.get("recipes")
    if not isinstance(recipes, dict):
        raise ValueError("workflow_manifest.yaml is missing recipes.")
    recipe_payload = recipes.get(recipe_id)
    if not isinstance(recipe_payload, dict):
        raise ValueError(f"workflow_manifest.yaml is missing recipe definition: {recipe_id}")
    return recipe_id, recipe_payload, profile_name


def _resolve_manifest_workflow(
    recipe_payload: dict[str, Any],
    *,
    seed_root_path: Path,
) -> tuple[str, str]:
    workflow_mode = str(recipe_payload.get("workflow_mode") or "").strip()
    workflow_file = recipe_payload.get("workflow_file")
    if workflow_mode == "runtime-fallback":
        if not isinstance(workflow_file, str) or not workflow_file.strip():
            raise ValueError("runtime-fallback recipe is missing workflow_file.")
        return resolve_runtime_workflow(workflow_file)
    if workflow_mode == "api-export":
        if not isinstance(workflow_file, str) or not workflow_file.strip():
            raise ValueError("api-export recipe is missing workflow_file.")
        return "api-export", str(seed_root_path / "api_workflows" / workflow_file)
    if workflow_mode == "studio-export":
        if not isinstance(workflow_file, str) or not workflow_file.strip():
            raise ValueError("studio-export recipe is missing workflow_file.")
        return "studio-export", str(runtime_root() / workflow_file)
    if workflow_mode == "studio-compare":
        if not isinstance(workflow_file, str) or not workflow_file.strip():
            raise ValueError("studio-compare recipe is missing workflow_file.")
        return "studio-compare", str(runtime_root() / workflow_file)
    raise ValueError(f"Unsupported workflow_mode: {workflow_mode}")


def choose_recipe(tool: str, seed_root: str = "seed_bundle", profile: str | None = None) -> RecipeDecision:
    normalized_tool = normalize_tool_key(tool)
    seed_root_path = _resolve_seed_root(seed_root)
    recipe_id, recipe_payload, profile_name = _recipe_manifest_entry(
        normalized_tool,
        seed_root_path=seed_root_path,
        profile=profile,
    )
    workflow_source, workflow_path = _resolve_manifest_workflow(recipe_payload, seed_root_path=seed_root_path)
    references = recipe_payload.get("references")
    reference_urls = []
    if isinstance(references, list):
        for item in references:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    reference_urls.append(url.strip())
            elif isinstance(item, str) and item.strip():
                reference_urls.append(item.strip())
    public_priors, bootstrap_rules, community_takeaways = public_priors_for_tool(
        normalized_tool,
        seed_root=seed_root_path,
        profile=profile_name,
    )
    runtime_prior_bundle, runtime_prior_artifacts = runtime_priors_for_tool(
        normalized_tool,
        seed_root=seed_root_path,
    )
    frontier_dataset_activation, frontier_dataset_items = frontier_dataset_activation_for_tool(
        normalized_tool,
        seed_root=seed_root_path,
        runtime_prior_artifacts=runtime_prior_artifacts,
    )
    return RecipeDecision(
        recipe_id=recipe_id,
        tool=normalized_tool,
        selection_profile=profile_name,
        execution_engine=str(recipe_payload.get("execution_engine") or "comfy-workflow"),
        workflow_source=workflow_source,
        workflow_path=workflow_path,
        model_family=recipe_payload.get("model_family"),
        maturity=recipe_payload.get("maturity"),
        license=recipe_payload.get("license"),
        warm_models=[str(item) for item in recipe_payload.get("warm_models", []) if str(item).strip()],
        cold_models=[str(item) for item in recipe_payload.get("cold_models", []) if str(item).strip()],
        watch_models=[str(item) for item in recipe_payload.get("watch_models", []) if str(item).strip()],
        references=reference_urls,
        public_priors=public_priors,
        bootstrap_rules=bootstrap_rules,
        community_takeaways=community_takeaways,
        runtime_prior_bundle=runtime_prior_bundle,
        runtime_prior_artifacts=runtime_prior_artifacts,
        frontier_dataset_activation=frontier_dataset_activation,
        frontier_dataset_items=frontier_dataset_items,
        notes=str(recipe_payload.get("rationale") or recipe_payload.get("notes") or ""),
    )
