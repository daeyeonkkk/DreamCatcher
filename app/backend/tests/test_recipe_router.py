from pathlib import Path

from app.core import recipe_router


def _write_manifest(seed_root: Path) -> None:
    seed_root.mkdir(parents=True, exist_ok=True)
    (seed_root / "workflow_manifest.yaml").write_text(
        """
version: "2026-03-26"
active_profile: test_profile
profiles:
  test_profile:
    label: Test Profile
    defaults:
      removeBg: removebg_birefnet
recipes:
  removebg_birefnet:
    tool: removeBg
    execution_engine: comfy-workflow
    workflow_mode: runtime-fallback
    workflow_file: cutout_birefnet.json
    model_family: BiRefNet
    maturity: stable
    license: open-source
    warm_models:
      - BiRefNet-DIS5K
    cold_models: []
    watch_models:
      - BiRefNet_dynamic
    rationale: Test manifest entry
    references:
      - label: BiRefNet
        url: https://github.com/ZhengPeng7/BiRefNet
""".strip(),
        encoding="utf-8",
    )
    (seed_root / "public_dataset_manifest.yaml").write_text(
        """
version: "2026-03-26"
active_profile: test_profile
profiles:
  test_profile:
    bootstrap_rules:
      - Start from public priors before local memory exists.
    defaults:
      removeBg:
        - dis5k
    community_takeaways:
      removeBg:
        - Captured on 2026-03-26 from the community: mask quality still matters more than speed.
datasets:
  dis5k:
    label: DIS5K
    kind: segmentation_dataset
    readiness: stable
    availability: public
    scale: test scale
    license: open-source
    bootstraps:
      - edge fidelity
    notes: Test dataset prior
    references:
      - https://example.com/dis5k
""".strip(),
        encoding="utf-8",
    )
    (seed_root / "frontier_dataset_manifest.yaml").write_text(
        """
version: "2026-05-08"
strategy: frontier
policy:
  local_cache_root: local_data_lab/cache/frontier_datasets
  runpod_default_downloads_datasets: false
tasks:
  background_removal_matting:
    label: Background removal, matting, subject masks
task_defaults:
  background_removal_matting:
    - dis5k
datasets:
  dis5k:
    label: DIS5K
    tasks:
      - background_removal_matting
    kind: dichotomous_segmentation_dataset
    readiness: frontier_eval_default
    integration_status: ready
    availability: public_repo
    download_mode: git_clone
    runpod_default_download: false
    local_cache_subdir: matting/dis5k
    license_note: Test license gate.
    use_in_dreamcatcher: Test mask boundary evidence.
    references:
      - https://example.com/dis5k
""".strip(),
        encoding="utf-8",
    )
    runtime_priors = seed_root / "runtime_priors"
    runtime_priors.mkdir(parents=True, exist_ok=True)
    (runtime_priors / "manifest.yaml").write_text(
        """
version: "2026-03-26"
bundle_label: Test Runtime Prior Bundle
source_profile: test_lab
generated_at: "2026-03-26T00:00:00+00:00"
artifacts:
  - artifact_id: evaluator_rules
    label: Evaluator Rules
    kind: evaluator_rules
    bundle_path: seed_bundle/runtime_priors/evaluator/edit_evaluator_rules.default.json
    tool_scopes:
      - removeBg
    source_datasets:
      - dis5k
    training_tracks:
      - edit_evaluator_bootstrap
    notes: Test runtime prior
    generated_at: "2026-03-26T00:00:00+00:00"
    sha256: abc123
""".strip(),
        encoding="utf-8",
    )


def test_choose_recipe_prefers_materialized_runtime_workflow(tmp_path, monkeypatch):
    app_root = tmp_path / "app"
    reference_root = tmp_path / "reference_runtime"
    seed_root = tmp_path / "seed_bundle"
    materialized = app_root / "workflows" / "runtime" / "cutout_birefnet.json"
    reference = reference_root / "cutout_birefnet.json"

    _write_manifest(seed_root)
    materialized.parent.mkdir(parents=True, exist_ok=True)
    reference.parent.mkdir(parents=True, exist_ok=True)
    materialized.write_text("{}", encoding="utf-8")
    reference.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(recipe_router, "app_root", lambda: app_root)
    monkeypatch.setattr(recipe_router, "reference_runtime_root", lambda: reference_root)
    recipe_router.clear_workflow_manifest_cache()

    recipe = recipe_router.choose_recipe("removeBg", seed_root=seed_root)

    assert recipe.workflow_source == "runtime-template"
    assert Path(recipe.workflow_path) == materialized
    assert recipe.recipe_id == "removebg_birefnet"
    assert recipe.model_family == "BiRefNet"
    assert recipe.selection_profile == "test_profile"
    assert recipe.watch_models == ["BiRefNet_dynamic"]
    assert recipe.public_priors == [
        {
            "dataset_id": "dis5k",
            "label": "DIS5K",
            "kind": "segmentation_dataset",
            "readiness": "stable",
            "availability": "public",
            "scale": "test scale",
            "license": "open-source",
            "bootstraps": ["edge fidelity"],
            "notes": "Test dataset prior",
            "references": ["https://example.com/dis5k"],
        }
    ]
    assert recipe.bootstrap_rules == ["Start from public priors before local memory exists."]
    assert recipe.community_takeaways == [
        "Captured on 2026-03-26 from the community: mask quality still matters more than speed."
    ]
    assert recipe.runtime_prior_bundle == {
        "label": "Test Runtime Prior Bundle",
        "profile": "test_lab",
        "generated_at": "2026-03-26T00:00:00+00:00",
        "artifact_count": 1,
    }
    assert recipe.runtime_prior_artifacts == [
        {
            "artifact_id": "evaluator_rules",
            "label": "Evaluator Rules",
            "kind": "evaluator_rules",
            "bundle_path": "seed_bundle/runtime_priors/evaluator/edit_evaluator_rules.default.json",
            "tool_scopes": ["removeBg"],
            "source_datasets": ["dis5k"],
            "training_tracks": ["edit_evaluator_bootstrap"],
            "notes": "Test runtime prior",
            "generated_at": "2026-03-26T00:00:00+00:00",
            "sha256": "abc123",
        }
    ]
    assert recipe.frontier_dataset_activation == {
        "label": "Frontier Dataset Activation",
        "tool": "removeBg",
        "task_ids": ["background_removal_matting"],
        "dataset_count": 1,
        "active_count": 1,
        "local_cache_ready_count": 0,
        "runtime_prior_dataset_ids": ["dis5k"],
        "runpod_default_downloads_datasets": False,
        "policy": "manifest_driven_runtime_priors_no_default_corpora",
        "warnings": [],
        "notes": [
            "Frontier dataset corpora are not downloaded during normal ephemeral RunPod bootstrap.",
            "Runtime priors, model contracts, evaluation guardrails, and optional adapters can use the catalog automatically.",
        ],
    }
    assert len(recipe.frontier_dataset_items) == 1
    frontier_item = dict(recipe.frontier_dataset_items[0])
    local_dir = frontier_item.pop("local_dir")
    assert frontier_item == {
        "dataset_id": "dis5k",
        "label": "DIS5K",
        "tasks": ["background_removal_matting"],
        "kind": "dichotomous_segmentation_dataset",
        "readiness": "frontier_eval_default",
        "integration_status": "ready",
        "availability": "public_repo",
        "download_mode": "git_clone",
        "runpod_default_download": False,
        "local_cache_present": False,
        "activation_stage": "runtime_prior_active",
        "studio_use": ["runtime_prior", "mask_boundary_eval", "cutout_model_evidence"],
        "blocking_reason": None,
        "license_note": "Test license gate.",
        "use_in_dreamcatcher": "Test mask boundary evidence.",
        "references": ["https://example.com/dis5k"],
    }
    assert Path(local_dir) == Path("local_data_lab/cache/frontier_datasets/matting/dis5k")


def test_choose_recipe_falls_back_to_reference_runtime_workflow(tmp_path, monkeypatch):
    app_root = tmp_path / "app"
    reference_root = tmp_path / "reference_runtime"
    seed_root = tmp_path / "seed_bundle"
    reference = reference_root / "cutout_birefnet.json"

    _write_manifest(seed_root)
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(recipe_router, "app_root", lambda: app_root)
    monkeypatch.setattr(recipe_router, "reference_runtime_root", lambda: reference_root)
    recipe_router.clear_workflow_manifest_cache()

    recipe = recipe_router.choose_recipe("removeBg", seed_root=seed_root)

    assert recipe.workflow_source == "reference-runtime"
    assert Path(recipe.workflow_path) == reference
