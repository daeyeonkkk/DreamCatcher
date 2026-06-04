import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement_batch import (
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry,
    RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest,
    RawPrepBenchmarkMeasurementBatchEntry,
    RawPrepBenchmarkMeasurementBatchRequest,
    load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries,
    load_rawprep_benchmark_measurement_batch_entries,
    write_rawprep_benchmark_measurement_batch_from_single_raw_report,
    write_rawprep_benchmark_measurement_batch,
)


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-08",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "spec_only",
                        "sample_count": 0,
                        "evaluation_axes": ["noise_reduction"],
                    }
                },
                "tri_raw": {
                    "bucket_definitions": [
                        {
                            "bucket_id": "motion_heavy",
                            "label": "Motion-heavy",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": True,
                            "traits": ["subject_motion"],
                            "required_report_sections": ["deghost"],
                        }
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


def _write_manifests(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-08",
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
                "manifest_version": "2026-04-08",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "motion_heavy__001",
                        "bucket_id": "motion_heavy",
                        "source_paths": [
                            "samples/tri/001/frame_01.dng",
                            "samples/tri/001/frame_02.dng",
                            "samples/tri/001/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/motion_heavy__001.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_single_raw_report(output_root: Path, sample_id: str, *, planner_total_ms: float = 555.0) -> Path:
    report_path = output_root / "session_demo" / "01_single_raw" / sample_id / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "resolved_mode": "fast",
                "runtime_profile": "sensor_fast_preview_v1",
                "status": "materialized",
                "timing_summary": f"Planner total: {planner_total_ms}ms",
                "timing_report": {
                    "planner_total_ms": planner_total_ms,
                    "total_ms": planner_total_ms + 50.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def test_write_rawprep_benchmark_measurement_batch_writes_multiple_entries_and_reports_missing_samples(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_manifests(tmp_path)

    batch = write_rawprep_benchmark_measurement_batch(
        RawPrepBenchmarkMeasurementBatchRequest(
            output_root="outputs",
            entries=[
                RawPrepBenchmarkMeasurementBatchEntry(
                    sample_id="single_001",
                    timing_ms=801.0,
                    metrics={"noise_reduction": 0.92},
                ),
                RawPrepBenchmarkMeasurementBatchEntry(
                    sample_id="motion_heavy__001",
                    timing_ms=1410.0,
                    metrics={"deghost_quality": 0.83},
                    fallback_mode="guarded_merge",
                ),
                RawPrepBenchmarkMeasurementBatchEntry(
                    sample_id="missing_sample",
                    timing_ms=999.0,
                ),
            ],
        )
    )

    assert batch.entry_count == 3
    assert batch.written_count == 2
    assert batch.skipped_count == 1
    assert batch.success_sample_ids == ["single_001", "motion_heavy__001"]
    assert batch.issues[0].sample_id == "missing_sample"


def test_load_rawprep_benchmark_measurement_batch_entries_supports_jsonl(tmp_path):
    input_path = tmp_path / "measurements.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps({"sample_id": "single_001", "timing_ms": 801.0, "metrics": {"noise_reduction": 0.92}}),
                json.dumps({"sample_id": "motion_heavy__001", "timing_ms": 1410.0, "fallback_mode": "guarded_merge"}),
            ]
        ),
        encoding="utf-8",
    )

    entries = load_rawprep_benchmark_measurement_batch_entries(str(input_path))

    assert len(entries) == 2
    assert entries[0].sample_id == "single_001"
    assert entries[1].fallback_mode == "guarded_merge"


def test_write_rawprep_benchmark_measurement_batch_from_single_raw_report_bridges_multiple_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_manifests(tmp_path)

    single_report = _write_single_raw_report(tmp_path / "outputs", "single_001", planner_total_ms=577.5)

    batch = write_rawprep_benchmark_measurement_batch_from_single_raw_report(
        RawPrepBenchmarkMeasurementFromSingleRawReportBatchRequest(
            output_root="outputs",
            entries=[
                RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(
                    sample_id="single_001",
                    report_path=str(single_report.relative_to(tmp_path)),
                    notes=["report bridge"],
                ),
                RawPrepBenchmarkMeasurementFromSingleRawReportBatchEntry(
                    sample_id="missing_sample",
                    report_path="outputs/missing/report.json",
                ),
            ],
        )
    )

    assert batch.entry_count == 2
    assert batch.written_count == 1
    assert batch.skipped_count == 1
    assert batch.success_sample_ids == ["single_001"]
    assert batch.issues[0].code == "measurement_report_bridge_failed"

    payload = json.loads((tmp_path / "outputs" / "_benchmark_results" / "single_001.json").read_text(encoding="utf-8"))
    assert payload["timing_ms"] == 577.5
    assert payload["notes"][-1] == "report bridge"


def test_load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries_supports_jsonl(tmp_path):
    input_path = tmp_path / "measurement_reports.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps({"sample_id": "single_001", "report_path": "outputs/session_demo/one/report.json"}),
                json.dumps({"sample_id": "single_002", "report_path": "outputs/session_demo/two/report.json", "notes": ["bridge"]}),
            ]
        ),
        encoding="utf-8",
    )

    entries = load_rawprep_benchmark_measurement_from_single_raw_report_batch_entries(str(input_path))

    assert len(entries) == 2
    assert entries[0].sample_id == "single_001"
    assert entries[1].report_path.endswith("two/report.json")
    assert entries[1].notes == ["bridge"]
