import json
from pathlib import Path

from app.core.rawprep_benchmark_default_decision import (
    RawPrepBenchmarkDefaultDecisionRequest,
    load_rawprep_benchmark_default_decision,
    write_rawprep_benchmark_default_decision,
)
from app.core.rawprep_benchmark_local_ui_language_smoke import _UI_LANGUAGE_SURFACE_FILES


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-09",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "partially_populated",
                        "sample_count": 1,
                        "evaluation_axes": ["noise_reduction", "detail_preservation", "processing_time"],
                    }
                },
                "tri_raw": {
                    "bucket_definitions": [
                        {
                            "bucket_id": "static_hdr",
                            "label": "Static HDR",
                            "status": "partially_populated",
                            "sample_count": 1,
                            "hard_case": False,
                            "traits": ["static_scene"],
                            "required_report_sections": ["hdr_gain"],
                        }
                    ],
                    "hard_case_bucket": {
                        "defined": True,
                        "member_bucket_ids": [],
                    },
                },
                "report_template": {
                    "defined": True,
                    "sections": ["dataset_overview", "bucket_findings", "open_risks"],
                },
                "product_metrics": {
                    "compare_decision_logging": {
                        "defined": True,
                        "storage": [
                            "04_compare/decisions/compare_decision_*.json",
                            "_compare_learning/compare_decisions.jsonl",
                        ],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "single_decision",
                        "raw_path": "samples/single_decision/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_decision.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "tri_decision",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_decision/frame_01.dng",
                            "samples/tri_decision/frame_02.dng",
                            "samples/tri_decision/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_decision.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_measured_results(repo_root: Path) -> None:
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "single_decision.json").write_text(
        json.dumps(
            {
                "sample_id": "single_decision",
                "status": "measured",
                "timing_ms": 812.0,
                "metrics": {"noise_reduction": 0.92, "detail_preservation": 0.66},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "tri_decision.json").write_text(
        json.dumps(
            {
                "sample_id": "tri_decision",
                "status": "measured",
                "timing_ms": 1412.0,
                "metrics": {"hdr_gain": 0.84, "alignment_pressure_score": 0.91},
                "fallback_mode": "reference_frame_holdout",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_runpod_smoke_evidence(repo_root: Path) -> None:
    runtime_root = repo_root / "app" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    rawprep_payload = {"ok": True, "message": "ready"}
    single_raw_payload = {"ok": True, "preferred_backend": "rawpy"}
    single_raw_payload.update(
        {
            "sample_raw_path": "/workspace/sample_raw/input.CR3",
            "sample_decode_ok": True,
            "sample_result": {
                "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
                "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
            },
        }
    )
    bootstrap_payload = {
        "checks": {
            "comfy_ready": True,
            "backend_ready": True,
            "runtime_workflows_present": True,
            "rawprep_healthcheck_present": True,
            "single_raw_runtime_ready": True,
            "single_raw_healthcheck_present": True,
        },
        "rawprep_healthcheck": rawprep_payload,
        "single_raw_healthcheck": single_raw_payload,
    }
    (runtime_root / "rawprep_healthcheck.json").write_text(json.dumps(rawprep_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "single_raw_healthcheck.json").write_text(json.dumps(single_raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "bootstrap_summary.json").write_text(json.dumps(bootstrap_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_local_e2e_smoke_evidence(repo_root: Path, *, output_dir: str) -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_e2e_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-13T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "run_root": "outputs/_benchmark_runs/local_e2e",
                "status": "passed",
                "ok": True,
                "single_raw": {"status": "passed", "ready_for_edit_ui": True},
                "tri_raw": {"status": "passed", "ready_for_edit_ui": True},
                "recommended_actions": [],
                "summary": "Local e2e smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_local_recovery_smoke_evidence(repo_root: Path, *, output_dir: str) -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_recovery_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-13T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "run_root": "outputs/_benchmark_runs/local_recovery",
                "session_id": "local_recovery_demo",
                "status": "passed",
                "ok": True,
                "blocked_without_package": {
                    "status": "passed",
                    "ready_for_provider_pause": False,
                    "summary": "Recovery pause remains blocked until the package exists.",
                },
                "ready_with_package": {
                    "status": "passed",
                    "ready_for_provider_pause": True,
                    "ready_for_result_retrieval": True,
                    "ready_for_metadata_retrieval": True,
                    "summary": "Recovery package and metadata are ready for provider pause.",
                },
                "recommended_actions": [],
                "summary": "Local recovery smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_local_ui_language_smoke_evidence(repo_root: Path, *, output_dir: str) -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_ui_language_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-13T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "status": "passed",
                "ok": True,
                "scanned_files": list(_UI_LANGUAGE_SURFACE_FILES),
                "scanned_file_count": len(_UI_LANGUAGE_SURFACE_FILES),
                "scanned_literal_count": 42,
                "allowed_token_hints": ["DreamCatcher", "DreamISP", "SingleRaw", "TriRaw", "RunPod", "RAW", "HDR"],
                "missing_files": [],
                "findings": [],
                "recommended_actions": [],
                "summary": "Local UI language smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_default_decision_holds_when_runpod_smoke_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_results(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/default_hold")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/default_hold")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/default_hold")

    decision = write_rawprep_benchmark_default_decision(
        RawPrepBenchmarkDefaultDecisionRequest(
            output_dir="benchmarks/default_hold",
            output_root="outputs",
            label="default_hold",
        )
    )

    assert decision.benchmark_evidence_ready is True
    assert decision.release_promotion_ready is False
    assert decision.status == "hold_runpod_smoke_pending"
    assert decision.promotion_recommendation == "hold_default_promotion"
    assert decision.local_ui_language_smoke_status == "passed"
    assert decision.compare_decision_count == 0
    assert any("RunPod smoke" in line for line in decision.rationale)


def test_default_decision_is_ready_when_runpod_smoke_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_results(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/default_ready")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/default_ready")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/default_ready")

    decision = write_rawprep_benchmark_default_decision(
        RawPrepBenchmarkDefaultDecisionRequest(
            output_dir="benchmarks/default_ready",
            output_root="outputs",
            label="default_ready",
        )
    )

    assert decision.benchmark_evidence_ready is True
    assert decision.release_promotion_ready is True
    assert decision.status == "ready_for_default_review"
    assert decision.promotion_recommendation == "ready_for_human_default_review"
    assert decision.decision_path is not None and Path(decision.decision_path).exists()

    loaded = load_rawprep_benchmark_default_decision("benchmarks/default_ready", output_root="outputs")
    assert loaded.status == "ready_for_default_review"
    assert loaded.local_ui_language_smoke_status == "passed"
