import json
from pathlib import Path

from app.core.rawprep_benchmark_measurement_report_scaffold import (
    RawPrepBenchmarkMeasurementReportScaffoldRequest,
    build_rawprep_benchmark_measurement_report_scaffold,
)


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
                        "status": "spec_only",
                        "sample_count": 0,
                        "evaluation_axes": ["noise_reduction", "detail_preservation"],
                    }
                },
                "tri_raw": {"bucket_definitions": [], "hard_case_bucket": {"defined": False, "member_bucket_ids": []}},
                "report_template": {"defined": True, "sections": ["dataset_overview"]},
                "product_metrics": {"compare_decision_logging": {"defined": True, "storage": []}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_single_raw_manifest(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "needs_bridge",
                        "raw_path": "samples/needs_bridge/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/needs_bridge.json",
                    },
                    {
                        "sample_id": "already_measured",
                        "raw_path": "samples/already_measured/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/already_measured.json",
                    },
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


def _write_single_raw_report(output_root: Path, sample_id: str) -> Path:
    report_path = output_root / "session_demo" / "01_single_raw" / sample_id / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "timing_report": {"planner_total_ms": 500.0},
                "timing_summary": "Planner total: 500ms",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def test_build_measurement_report_scaffold_writes_batch_input_and_skips_existing_measurements(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_measurement_report_scaffold.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_single_raw_manifest(tmp_path)

    _write_single_raw_report(tmp_path / "outputs", "needs_bridge")
    _write_single_raw_report(tmp_path / "outputs", "already_measured")
    measured_path = tmp_path / "outputs" / "_benchmark_results" / "already_measured.json"
    measured_path.parent.mkdir(parents=True, exist_ok=True)
    measured_path.write_text(
        json.dumps({"sample_id": "already_measured", "status": "measured", "timing_ms": 777.0}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    scaffold = build_rawprep_benchmark_measurement_report_scaffold(
        RawPrepBenchmarkMeasurementReportScaffoldRequest(
            output_root="outputs",
            write_batch_input=True,
        )
    )

    assert scaffold.manifest_sample_count == 2
    assert scaffold.entry_count == 1
    assert scaffold.skipped_measured_sample_ids == ["already_measured"]
    assert scaffold.missing_report_sample_ids == []
    assert scaffold.wrote_batch_input is True
    assert scaffold.batch_input_path is not None

    batch_lines = Path(scaffold.batch_input_path).read_text(encoding="utf-8").splitlines()
    assert len(batch_lines) == 1
    payload = json.loads(batch_lines[0])
    assert payload["sample_id"] == "needs_bridge"
    assert payload["report_path"].endswith("needs_bridge/report.json")


def test_build_measurement_report_scaffold_reports_missing_and_ambiguous_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_measurement_report_scaffold.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "missing_report",
                        "raw_path": "samples/missing_report/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/missing_report.json",
                    },
                    {
                        "sample_id": "ambiguous_report",
                        "raw_path": "samples/ambiguous_report/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/ambiguous_report.json",
                    },
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

    _write_single_raw_report(tmp_path / "outputs" / "session_one", "ambiguous_report")
    _write_single_raw_report(tmp_path / "outputs" / "session_two", "ambiguous_report")

    scaffold = build_rawprep_benchmark_measurement_report_scaffold(
        RawPrepBenchmarkMeasurementReportScaffoldRequest(output_root="outputs")
    )

    assert scaffold.entry_count == 0
    assert scaffold.missing_report_sample_ids == ["missing_report"]
    assert scaffold.ambiguous_report_sample_ids == ["ambiguous_report"]
    assert {issue.code for issue in scaffold.issues} == {"single_raw_report_missing", "single_raw_report_ambiguous"}
