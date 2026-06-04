import json
from pathlib import Path

from app.core.rawprep_benchmark_gate import (
    build_rawprep_benchmark_gate,
    load_rawprep_benchmark_gate,
    write_rawprep_benchmark_gate,
)
from app.core.rawprep_benchmark_review import (
    build_rawprep_benchmark_release_review,
    load_rawprep_benchmark_release_review,
    write_rawprep_benchmark_release_review,
)
from app.core.rawprep_benchmark_service import RawPrepBenchmarkRequest, run_rawprep_benchmark


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-07",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "spec_only",
                        "sample_count": 0,
                        "evaluation_axes": ["noise_reduction", "detail_preservation"],
                    }
                },
                "tri_raw": {
                    "bucket_definitions": [
                        {
                            "bucket_id": "static_hdr",
                            "label": "Static HDR",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": False,
                            "traits": ["static_scene"],
                            "required_report_sections": ["hdr_gain"],
                        },
                        {
                            "bucket_id": "motion_heavy",
                            "label": "Motion-heavy",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": True,
                            "traits": ["subject_motion"],
                            "required_report_sections": ["deghost"],
                        },
                    ],
                    "hard_case_bucket": {
                        "defined": True,
                        "member_bucket_ids": ["motion_heavy"],
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
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "single_001.json").write_text(
        json.dumps(
            {
                "sample_id": "single_001",
                "status": "measured",
                "timing_ms": 810.0,
                "metrics": {"noise_reduction": 0.91},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "tri_001.json").write_text(
        json.dumps(
            {
                "sample_id": "tri_001",
                "status": "measured",
                "timing_ms": 1220.0,
                "metrics": {"hdr_gain": 0.83},
                "fallback_mode": "guarded_merge",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "tri_002.json").write_text(
        json.dumps(
            {
                "sample_id": "tri_002",
                "status": "measured",
                "timing_ms": 1340.0,
                "metrics": {"deghost_quality": 0.81},
                "fallback_mode": "reference_holdout",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "measured",
                "samples": [
                    {
                        "sample_id": "single_001",
                        "raw_path": "samples/single_001/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_001.json",
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
                "manifest_version": "2026-04-07",
                "status": "measured",
                "samples": [
                    {
                        "sample_id": "tri_001",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_001/frame_01.dng",
                            "samples/tri_001/frame_02.dng",
                            "samples/tri_001/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_001.json",
                    },
                    {
                        "sample_id": "tri_002",
                        "bucket_id": "motion_heavy",
                        "source_paths": [
                            "samples/tri_002/frame_01.dng",
                            "samples/tri_002/frame_02.dng",
                            "samples/tri_002/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_002.json",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_runpod_smoke_evidence(repo_root: Path) -> None:
    runtime_root = repo_root / "app" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    rawprep_payload = {
        "ok": False,
        "message": "dreamcatcher-raw-engine-v2 is still scaffolded.",
        "engine_readiness": {
            "dreamcatcher_raw_engine_v2": {
                "missing_tools": ["dreamcatcher-raw-engine-v2"],
            }
        },
    }
    single_raw_payload = {
        "ok": True,
        "preferred_backend": "rawpy",
        "sample_raw_path": "/workspace/sample_raw/input.CR3",
        "sample_decode_ok": True,
        "sample_result": {
            "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
            "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
        },
    }
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


def test_build_rawprep_benchmark_gate_requires_runpod_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    run_rawprep_benchmark(RawPrepBenchmarkRequest(output_dir="benchmarks/run_measured", output_root="outputs"))

    gate = build_rawprep_benchmark_gate("benchmarks/run_measured", output_root="outputs")

    assert gate.ok is False
    assert gate.ready_for_default_review is False
    assert gate.status == "runpod_smoke_pending"
    assert gate.foundation_status == "measured_ready"
    assert gate.benchmark_record_status == "measured"
    assert gate.benchmark_report_status == "measured"
    assert any(issue.code == "runpod_bootstrap_summary_missing" for issue in gate.blockers)


def test_build_rawprep_benchmark_gate_allows_default_review_with_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    run_rawprep_benchmark(RawPrepBenchmarkRequest(output_dir="benchmarks/run_measured", output_root="outputs"))

    gate = build_rawprep_benchmark_gate("benchmarks/run_measured", output_root="outputs")

    assert gate.ok is True
    assert gate.ready_for_default_review is True
    assert gate.status == "ready_for_default_review"
    assert gate.runpod_smoke_status == "passed"
    assert any(issue.code == "runpod_rawprep_healthcheck_not_ok" for issue in gate.warnings)


def test_write_rawprep_benchmark_gate_persists_canonical_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    run_rawprep_benchmark(RawPrepBenchmarkRequest(output_dir="benchmarks/run_measured", output_root="outputs"))

    gate = write_rawprep_benchmark_gate("benchmarks/run_measured", output_root="outputs")
    loaded = load_rawprep_benchmark_gate("benchmarks/run_measured", output_root="outputs")

    assert gate.gate_path is not None
    assert Path(gate.gate_path).exists()
    assert gate.runpod_smoke_path is not None
    assert Path(gate.runpod_smoke_path).exists()
    assert loaded.status == "ready_for_default_review"
    assert loaded.gate_path == gate.gate_path


def test_build_rawprep_benchmark_release_review_reflects_incomplete_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    run_rawprep_benchmark(RawPrepBenchmarkRequest(output_dir="benchmarks/run_measured", output_root="outputs"))

    review = build_rawprep_benchmark_release_review("benchmarks/run_measured", output_root="outputs")

    assert review.ready_for_human_review is False
    assert review.status == "evidence_incomplete"
    assert review.gate_status == "runpod_smoke_pending"
    assert review.artifact_presence["benchmark_report"] is True
    assert review.artifact_presence["bootstrap_summary"] is False


def test_write_rawprep_benchmark_release_review_persists_canonical_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    run_rawprep_benchmark(RawPrepBenchmarkRequest(output_dir="benchmarks/run_measured", output_root="outputs"))

    review = write_rawprep_benchmark_release_review("benchmarks/run_measured", output_root="outputs")
    loaded = load_rawprep_benchmark_release_review("benchmarks/run_measured", output_root="outputs")

    assert review.review_path is not None
    assert Path(review.review_path).exists()
    assert review.runpod_smoke_path is not None
    assert Path(review.runpod_smoke_path).exists()
    assert review.artifact_presence["runpod_smoke"] is True
    assert review.ready_for_human_review is True
    assert loaded.status == "ready_for_human_review"
    assert loaded.review_path == review.review_path
