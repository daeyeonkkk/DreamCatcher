from pathlib import Path
import json
import os
import subprocess
import sys

from app.core.frontier_dataset_catalog import (
    build_frontier_dataset_plan,
    frontier_dataset_manifest_path,
    list_frontier_dataset_cards,
    load_frontier_dataset_manifest,
)
from app.core.frontier_dataset_activation import frontier_dataset_activation_for_tool


REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_ROOT = REPO_ROOT / "seed_bundle"


def test_frontier_dataset_manifest_covers_required_studio_tasks():
    manifest = load_frontier_dataset_manifest(str(frontier_dataset_manifest_path(SEED_ROOT)))

    assert manifest["strategy"] == "frontier"
    assert manifest["policy"]["runpod_default_downloads_datasets"] is False
    assert set(manifest["tasks"]) >= {
        "raw_merge_denoise",
        "photo_correction_retouch",
        "background_removal_matting",
        "background_generation_replace",
        "inpaint_outpaint",
    }
    assert "ntire_burst_hdr_2025" in manifest["task_defaults"]["raw_merge_denoise"]
    assert "dis5k" in manifest["task_defaults"]["background_removal_matting"]
    assert "imgedit" in manifest["task_defaults"]["background_generation_replace"]


def test_raw_frontier_plan_includes_merge_denoise_research_and_no_runpod_dataset_downloads():
    plan = build_frontier_dataset_plan(seed_root=SEED_ROOT, tasks=["raw_merge_denoise"])
    dataset_ids = {card.dataset_id for card in plan.selected_datasets}

    assert plan.ok is True
    assert {"ntire_burst_hdr_2025", "rawir", "bracketire_ireanet", "sidd"} <= dataset_ids
    assert all(card.runpod_default_download is False for card in plan.selected_datasets)
    assert plan.task_coverage["raw_merge_denoise"]
    assert any(item.dataset_id == "rawir" and item.command for item in plan.download_plan)
    assert any(item.dataset_id == "ntire_burst_hdr_2025" and item.status == "challenge_registration_required" for item in plan.download_plan)


def test_background_dataset_cards_span_removal_generation_and_inpainting():
    cards = list_frontier_dataset_cards(
        seed_root=SEED_ROOT,
        tasks=["background_removal_matting", "background_generation_replace", "inpaint_outpaint"],
    )
    dataset_ids = {card.dataset_id for card in cards}

    assert {"dis5k", "sa1b", "coco_stuff_164k", "ade20k"} <= dataset_ids
    assert {"imgedit", "editbench", "magicbrush", "places2", "lama_places_openimages_masks"} <= dataset_ids


def test_frontier_dataset_activation_marks_runtime_priors_and_eval_guardrails():
    summary, items = frontier_dataset_activation_for_tool(
        "retouch",
        seed_root=SEED_ROOT,
        runtime_prior_artifacts=[
            {
                "artifact_id": "reference_bank_seed",
                "source_datasets": ["fivek", "dear"],
            }
        ],
    )
    stages = {item["dataset_id"]: item["activation_stage"] for item in items}

    assert summary is not None
    assert summary["tool"] == "retouch"
    assert summary["task_ids"] == ["photo_correction_retouch"]
    assert summary["runpod_default_downloads_datasets"] is False
    assert summary["active_count"] >= 2
    assert stages["fivek"] == "runtime_prior_active"
    assert stages["dear"] == "runtime_prior_active"
    assert stages["ppr10k"] == "eval_guardrail_ready"
    assert "compare_guardrail" in next(item for item in items if item["dataset_id"] == "fivek")["studio_use"]
    assert all(item["runpod_default_download"] is False for item in items)


def test_frontier_dataset_plan_script_writes_json_without_pythonpath(tmp_path):
    script = REPO_ROOT / "app" / "scripts" / "frontier_dataset_plan.py"
    out_path = tmp_path / "frontier_raw_plan.json"

    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--seed-root",
            str(SEED_ROOT),
            "--task",
            "raw_merge_denoise",
            "--require-task",
            "raw_merge_denoise",
            "--out",
            str(out_path),
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["task_coverage"]["raw_merge_denoise"]
