import json
from pathlib import Path

import pytest

from app.core.rawprep_benchmark_measurement import (
    RawPrepBenchmarkMeasurementFromSingleRawReportRequest,
    RawPrepBenchmarkMeasurementWriteRequest,
    build_rawprep_benchmark_measurement,
    write_rawprep_benchmark_measurement_from_single_raw_report,
    write_rawprep_benchmark_measurement,
)


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


def _write_single_raw_report(output_root: Path, sample_id: str, *, planner_total_ms: float = 512.25) -> Path:
    report_path = output_root / "session_demo" / "01_single_raw" / sample_id / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "resolved_mode": "fast",
                "runtime_profile": "sensor_fast_preview_v1",
                "status": "materialized",
                "timing_summary": f"Planner total: {planner_total_ms}ms",
                "noise_report": {
                    "suppression_ratio": 0.42,
                },
                "artifact_suppression": {
                    "texture_suppression_ratio": 0.12,
                    "saturation_suppression_ratio": 0.08,
                },
                "recovery_report": {
                    "lowlight_detail_gain_ratio": 0.34,
                },
                "fallback_decision": {
                    "reason_key": "fast_runtime_direct_preview",
                },
                "timing_report": {
                    "planner_total_ms": planner_total_ms,
                    "total_ms": planner_total_ms + 90.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def test_write_rawprep_benchmark_measurement_writes_single_raw_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "night_scene",
                        "raw_path": "samples/night_scene/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/night_scene.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    record = write_rawprep_benchmark_measurement(
        RawPrepBenchmarkMeasurementWriteRequest(
            sample_id="night_scene",
            output_root="outputs",
            timing_ms=812.5,
            metrics={"noise_reduction": 0.91, "detail_preservation": 0.88},
            notes=["single raw smoke"],
        )
    )

    measurement_path = tmp_path / "outputs" / "_benchmark_results" / "night_scene.json"
    payload = json.loads(measurement_path.read_text(encoding="utf-8"))

    assert record.scope == "single_raw"
    assert record.measurement_exists is True
    assert record.measurement_status == "measured"
    assert payload["sample_id"] == "night_scene"
    assert payload["timing_ms"] == 812.5
    assert payload["metrics"]["noise_reduction"] == 0.91


def test_write_rawprep_benchmark_measurement_writes_tri_raw_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "motion_heavy__street_walk",
                        "bucket_id": "motion_heavy",
                        "source_paths": [
                            "samples/tri/frame_01.dng",
                            "samples/tri/frame_02.dng",
                            "samples/tri/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/motion_heavy__street_walk.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    record = write_rawprep_benchmark_measurement(
        RawPrepBenchmarkMeasurementWriteRequest(
            sample_id="motion_heavy__street_walk",
            output_root="outputs",
            timing_ms=1430.0,
            metrics={"deghost_quality": 0.82},
            fallback_mode="guarded_merge",
            notes=["tri raw smoke"],
        )
    )

    measurement_path = tmp_path / "outputs" / "_benchmark_results" / "motion_heavy__street_walk.json"
    payload = json.loads(measurement_path.read_text(encoding="utf-8"))

    assert record.scope == "tri_raw"
    assert record.bucket_id == "motion_heavy"
    assert payload["fallback_mode"] == "guarded_merge"
    assert payload["metrics"]["deghost_quality"] == 0.82


def test_build_rawprep_benchmark_measurement_requires_manifest_entry(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        build_rawprep_benchmark_measurement("missing_sample", output_root="outputs")


def test_write_rawprep_benchmark_measurement_from_single_raw_report_derives_official_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "single_report_bridge",
                        "raw_path": "samples/single_report_bridge/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/single_report_bridge.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = _write_single_raw_report(tmp_path / "outputs", "single_report_bridge", planner_total_ms=544.5)

    record = write_rawprep_benchmark_measurement_from_single_raw_report(
        RawPrepBenchmarkMeasurementFromSingleRawReportRequest(
            sample_id="single_report_bridge",
            report_path=str(report_path.relative_to(tmp_path)),
            output_root="outputs",
            notes=["bridge smoke"],
        )
    )

    measurement_path = tmp_path / "outputs" / "_benchmark_results" / "single_report_bridge.json"
    payload = json.loads(measurement_path.read_text(encoding="utf-8"))

    assert record.scope == "single_raw"
    assert record.measurement_exists is True
    assert record.measurement_status == "measured"
    assert record.summary == "Official benchmark measurement evidence was derived from a SingleRaw report timing artifact."
    assert payload["sample_id"] == "single_report_bridge"
    assert payload["timing_ms"] == 544.5
    assert payload["metrics"] == {
        "noise_reduction": 0.42,
        "detail_preservation": 0.61,
        "color_stability": 0.92,
    }
    assert payload["fallback_mode"] == "fast_runtime_direct_preview"
    assert payload["notes"][0].startswith("Derived from SingleRaw report:")
    assert "Planner total: 544.5ms" in payload["notes"]
    assert "Resolved mode: fast" in payload["notes"]
    assert payload["notes"][-1] == "bridge smoke"
