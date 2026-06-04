import json
from pathlib import Path

from PIL import Image

from app.core.rawprep_benchmark import benchmark_status
from app.core.rawprep_benchmark_service import (
    RawPrepBenchmarkRequest,
    build_rawprep_benchmark_foundation_health,
    load_rawprep_benchmark_record,
    load_rawprep_benchmark_report,
    run_rawprep_benchmark,
)
from app.core.studio_compare_memory import record_compare_decision


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
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "unpopulated",
                "samples": [],
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
                "status": "unpopulated",
                "samples": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_populated_benchmark_manifests(repo_root: Path, *, manifest_status: str = "partially_populated") -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": manifest_status,
                "samples": [
                    {
                        "sample_id": "single_001",
                        "label": "Night portrait high ISO",
                        "raw_path": "samples/single_001/input.dng",
                    },
                    {
                        "sample_id": "single_002",
                        "label": "Daylight texture detail",
                        "raw_path": "samples/single_002/input.dng",
                    },
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
                "status": manifest_status,
                "samples": [
                    {
                        "sample_id": "tri_001",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_001/frame_01.dng",
                            "samples/tri_001/frame_02.dng",
                            "samples/tri_001/frame_03.dng",
                        ],
                    },
                    {
                        "sample_id": "tri_002",
                        "bucket_id": "motion_heavy",
                        "source_paths": [
                            "samples/tri_002/frame_01.dng",
                            "samples/tri_002/frame_02.dng",
                            "samples/tri_002/frame_03.dng",
                        ],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_measured_benchmark_manifests_and_results(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)

    (results_root / "single_001.json").write_text(
        json.dumps(
            {
                "sample_id": "single_001",
                "status": "measured",
                "timing_ms": 810.0,
                "metrics": {
                    "noise_reduction": 0.91,
                    "detail_preservation": 0.87,
                    "color_stability": 0.84,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "single_002.json").write_text(
        json.dumps(
            {
                "sample_id": "single_002",
                "status": "measured",
                "timing_ms": 790.0,
                "metrics": {
                    "noise_reduction": 0.88,
                    "detail_preservation": 0.9,
                    "color_stability": 0.86,
                },
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
                "metrics": {
                    "deghost_quality": 0.79,
                    "hdr_gain": 0.83,
                },
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
                "metrics": {
                    "deghost_quality": 0.81,
                    "hdr_gain": 0.76,
                },
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
                        "label": "Night portrait high ISO",
                        "raw_path": "samples/single_001/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_001.json",
                    },
                    {
                        "sample_id": "single_002",
                        "label": "Daylight texture detail",
                        "raw_path": "samples/single_002/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_002.json",
                    },
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


def _write_pending_benchmark_manifests_and_results(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)

    (results_root / "single_001.json").write_text(
        json.dumps(
            {
                "sample_id": "single_001",
                "status": "pending_measurement",
                "timing_ms": None,
                "metrics": {},
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
                "status": "pending_measurement",
                "timing_ms": None,
                "metrics": {},
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
                "status": "pending_measurement",
                "timing_ms": None,
                "metrics": {},
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
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
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
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_compare_decision_fixture(output_root: Path) -> None:
    session_root = output_root / "session_demo" / "02_manual"
    session_root.mkdir(parents=True, exist_ok=True)
    select_path = session_root / "select.png"
    candidate_path = session_root / "candidate.png"
    Image.new("RGB", (24, 24), (96, 100, 110)).save(select_path)
    Image.new("RGB", (24, 24), (142, 134, 126)).save(candidate_path)
    record_compare_decision(
        session_id="session_demo",
        output_root=str(output_root),
        tool="compare",
        select_path=str(select_path),
        candidate_path=str(candidate_path),
        winner_path=str(candidate_path),
        action="accept_candidate",
    )


def test_run_rawprep_benchmark_writes_foundation_record(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_compare_decision_fixture(tmp_path / "outputs")

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir="benchmarks/run_001",
            output_root="outputs",
            label="foundation_preview",
        )
    )

    assert record.status == "foundation_ready"
    assert record.single_raw_gold_set_defined is True
    assert record.single_raw_manifest_exists is True
    assert record.single_raw_manifest_status == "unpopulated"
    assert record.hard_case_bucket_defined is True
    assert record.tri_raw_manifest_exists is True
    assert record.tri_raw_manifest_status == "unpopulated"
    assert record.report_template_documented is True
    assert [bucket.bucket_id for bucket in record.tri_raw_buckets] == ["static_hdr", "motion_heavy"]
    assert record.report_sections == ["dataset_overview", "bucket_findings", "open_risks"]
    assert record.compare_decision_logging_defined is True
    assert record.compare_decision_count == 1
    assert record.compare_decision_summary["winner_role_counts"] == {"candidate": 1}
    assert record.tri_raw_missing_bucket_ids == ["static_hdr", "motion_heavy"]

    loaded = load_rawprep_benchmark_record("benchmarks/run_001", output_root="outputs")
    assert loaded.label == "foundation_preview"
    assert loaded.catalog_version == "2026-04-07"
    assert loaded.hard_case_member_bucket_ids == ["motion_heavy"]
    assert loaded.compare_decision_count == 1
    assert loaded.report_status == "foundation_ready"

    report = load_rawprep_benchmark_report("benchmarks/run_001", output_root="outputs")
    assert report.status == "foundation_ready"
    assert report.dataset_overview["single_raw_sample_count"] == 0
    assert report.single_raw_summary["manifest_status"] == "unpopulated"
    assert report.tri_raw_summary["missing_bucket_ids"] == ["static_hdr", "motion_heavy"]
    assert any("SingleRaw gold set manifest is still empty" in risk for risk in report.open_risks)

    health = build_rawprep_benchmark_foundation_health(output_root="outputs")
    assert health.ok is True
    assert health.status == "foundation_ready"
    assert health.issue_counts == {"error": 0, "warning": 0}


def test_benchmark_status_reads_foundation_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_compare_decision_fixture(tmp_path / "outputs")

    status = benchmark_status()

    assert status["enabled"] is True
    assert status["status"] == "foundation_ready"
    assert status["catalog_version"] == "2026-04-07"
    assert status["single_raw_sample_count"] == 0
    assert status["single_raw_measured_sample_count"] == 0
    assert status["tri_raw_bucket_count"] == 2
    assert status["tri_raw_populated_bucket_count"] == 0
    assert status["tri_raw_measured_bucket_count"] == 0
    assert status["tri_raw_missing_bucket_ids"] == ["static_hdr", "motion_heavy"]
    assert status["hard_case_bucket_defined"] is True
    assert status["report_template_documented"] is True
    assert status["report_status"] == "foundation_ready"
    assert status["compare_decision_logging_defined"] is True
    assert status["compare_decision_count"] == 1


def test_run_rawprep_benchmark_reads_manifest_population(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_populated_benchmark_manifests(tmp_path)

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir="benchmarks/run_populated",
            output_root="outputs",
            label="population_preview",
        )
    )

    assert record.status == "partially_populated"
    assert record.single_raw_sample_count == 2
    assert record.single_raw_manifest_status == "partially_populated"
    assert [bucket.sample_count for bucket in record.tri_raw_buckets] == [1, 1]
    assert record.tri_raw_populated_bucket_ids == ["static_hdr", "motion_heavy"]
    assert record.tri_raw_missing_bucket_ids == []
    assert "partially populated" in record.summary
    assert record.report_status == "partially_populated"

    report = load_rawprep_benchmark_report("benchmarks/run_populated", output_root="outputs")
    assert report.status == "partially_populated"
    assert report.dataset_overview["single_raw_sample_count"] == 2
    assert report.tri_raw_summary["populated_bucket_ids"] == ["static_hdr", "motion_heavy"]
    assert report.bucket_findings[0]["sample_count"] == 1
    assert report.timing["status"] == "unmeasured"


def test_run_rawprep_benchmark_requires_measurement_evidence_for_measured_status(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_populated_benchmark_manifests(tmp_path, manifest_status="measured")

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir="benchmarks/run_missing_measurements",
            output_root="outputs",
            label="missing_measurements",
        )
    )

    assert record.status == "partially_populated"
    assert record.single_raw_measured_sample_count == 0
    assert record.tri_raw_measured_sample_count == 0
    assert record.single_raw_missing_measurement_sample_ids == ["single_001", "single_002"]
    assert record.tri_raw_missing_measurement_sample_ids == ["tri_001", "tri_002"]

    report = load_rawprep_benchmark_report("benchmarks/run_missing_measurements", output_root="outputs")
    assert report.status == "partially_populated"
    assert report.timing["status"] == "unmeasured"
    assert any("SingleRaw measured evidence is still missing" in risk for risk in report.open_risks)
    assert any("TriRaw measured evidence is still missing" in risk for risk in report.open_risks)


def test_run_rawprep_benchmark_reads_measured_result_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_benchmark_manifests_and_results(tmp_path)

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir="benchmarks/run_measured",
            output_root="outputs",
            label="measured_preview",
        )
    )

    assert record.status == "measured"
    assert record.single_raw_measured_sample_count == 2
    assert record.single_raw_timing_ms_mean == 800.0
    assert record.single_raw_metric_mean_by_axis["noise_reduction"] == 0.895
    assert record.tri_raw_measured_sample_count == 2
    assert record.tri_raw_measured_bucket_ids == ["static_hdr", "motion_heavy"]
    assert record.tri_raw_timing_ms_mean == 1280.0
    assert record.tri_raw_fallback_mode_counts == {
        "guarded_merge": 1,
        "reference_holdout": 1,
    }

    report = load_rawprep_benchmark_report("benchmarks/run_measured", output_root="outputs")
    assert report.status == "measured"
    assert report.timing["status"] == "measured"
    assert report.timing["single_raw_timing_ms_mean"] == 800.0
    assert report.timing["tri_raw_timing_ms_mean"] == 1280.0
    assert report.single_raw_summary["metric_mean_by_axis"]["detail_preservation"] == 0.885
    assert report.fallback_behavior["fallback_mode_counts"] == {
        "guarded_merge": 1,
        "reference_holdout": 1,
    }

    health = build_rawprep_benchmark_foundation_health(output_root="outputs")
    assert health.ok is True
    assert health.status == "measured_ready"
    assert health.issue_counts == {"error": 0, "warning": 0}


def test_build_rawprep_benchmark_foundation_health_reports_manifest_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "tri_bad",
                        "bucket_id": "unknown_bucket",
                        "source_paths": ["samples/tri_bad/frame_01.dng", "samples/tri_bad/frame_02.dng"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    health = build_rawprep_benchmark_foundation_health(output_root="outputs")

    assert health.ok is False
    assert health.status == "blocked"
    assert health.issue_counts["error"] >= 2
    assert any(issue.code == "tri_raw_unknown_bucket" for issue in health.issues)
    assert any(issue.code == "tri_raw_source_paths_invalid" for issue in health.issues)


def test_build_rawprep_benchmark_foundation_health_treats_pending_measurements_as_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_pending_benchmark_manifests_and_results(tmp_path)

    record = run_rawprep_benchmark(
        RawPrepBenchmarkRequest(
            output_dir="benchmarks/run_pending",
            output_root="outputs",
            label="pending_preview",
        )
    )
    health = build_rawprep_benchmark_foundation_health(output_root="outputs")

    assert record.status == "partially_populated"
    assert record.single_raw_measured_sample_count == 0
    assert record.tri_raw_measured_sample_count == 0
    assert health.ok is True
    assert health.status == "measurement_incomplete"
    assert health.single_raw_measured_sample_count == 0
    assert health.tri_raw_measured_sample_count == 0
    assert any(issue.code == "measurement_status_not_measured" for issue in health.issues)
