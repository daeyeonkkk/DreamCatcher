import json
from pathlib import Path

from app.core.rawprep_benchmark_runpod_bootstrap_readiness import (
    RawPrepRunPodBootstrapReadinessRequest,
    build_rawprep_runpod_bootstrap_readiness,
    load_rawprep_runpod_bootstrap_readiness,
    write_rawprep_runpod_bootstrap_readiness,
)


def _write_bootstrap_summary(path: Path, *, embed_contracts: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runpod_template_policy": {
            "console_label": "ComfyUI - CUDA 13",
        },
        "checks": {
            "comfy_ready": True,
            "backend_ready": True,
            "rawprep_healthcheck_present": True,
            "single_raw_healthcheck_present": True,
            "model_selection_recorded": embed_contracts,
            "custom_node_runtime_valid": embed_contracts,
        },
    }
    if embed_contracts:
        payload["model_bootstrap_contract"] = {
            "ok": True,
            "download_scope_status": "requested_only",
            "selected_model_sets": ["qwen"],
        }
        payload["custom_node_contract"] = {
            "ok": True,
            "custom_nodes": [{"name": "node-a"}],
        }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_model_contract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "download_scope_status": "lazy_on_demand",
                "selected_model_sets": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_custom_node_contract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "custom_nodes": [{"name": "node-a"}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_runpod_bootstrap_readiness_reports_partial_when_contracts_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_bootstrap_readiness.repo_root", lambda: tmp_path)
    bootstrap_path = tmp_path / "app" / "runtime" / "bootstrap_summary.json"
    _write_bootstrap_summary(bootstrap_path, embed_contracts=False)

    artifact = build_rawprep_runpod_bootstrap_readiness(
        RawPrepRunPodBootstrapReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is False
    assert artifact.status == "evidence_partial"
    assert artifact.checks.bootstrap_completed is True
    assert artifact.checks.model_contract_present is False


def test_build_runpod_bootstrap_readiness_reports_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_bootstrap_readiness.repo_root", lambda: tmp_path)
    bootstrap_path = tmp_path / "app" / "runtime" / "bootstrap_summary.json"
    model_contract_path = tmp_path / "app" / "runtime" / "runpod_model_bootstrap_contract.json"
    custom_contract_path = tmp_path / "app" / "runtime" / "runpod_custom_node_contract.json"
    _write_bootstrap_summary(bootstrap_path, embed_contracts=False)
    _write_model_contract(model_contract_path)
    _write_custom_node_contract(custom_contract_path)

    artifact = build_rawprep_runpod_bootstrap_readiness(
        RawPrepRunPodBootstrapReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is True
    assert artifact.status == "ready_for_bootstrap_review"
    assert artifact.checks.model_selection_recorded is True
    assert artifact.checks.custom_node_runtime_valid is True


def test_write_runpod_bootstrap_readiness_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_bootstrap_readiness.repo_root", lambda: tmp_path)
    bootstrap_path = tmp_path / "app" / "runtime" / "bootstrap_summary.json"
    model_contract_path = tmp_path / "app" / "runtime" / "runpod_model_bootstrap_contract.json"
    custom_contract_path = tmp_path / "app" / "runtime" / "runpod_custom_node_contract.json"
    _write_bootstrap_summary(bootstrap_path, embed_contracts=False)
    _write_model_contract(model_contract_path)
    _write_custom_node_contract(custom_contract_path)

    artifact = write_rawprep_runpod_bootstrap_readiness(
        RawPrepRunPodBootstrapReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )
    loaded = load_rawprep_runpod_bootstrap_readiness("benchmarks/measured", output_root="outputs")

    assert Path(artifact.artifact_path).exists()
    assert loaded.status == "ready_for_bootstrap_review"
    assert loaded.model_download_scope_status == "lazy_on_demand"
