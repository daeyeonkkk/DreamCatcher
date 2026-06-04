import json
from pathlib import Path

from app.core.rawprep_benchmark_scaffold import (
    RawPrepBenchmarkScaffoldRequest,
    build_rawprep_benchmark_scaffold,
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
                            "bucket_id": "static_hdr",
                            "label": "Static HDR",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": False,
                            "traits": ["static_scene"],
                            "required_report_sections": ["hdr_gain"],
                        },
                        {
                            "bucket_id": "high_iso_hdr",
                            "label": "High-ISO HDR",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": True,
                            "traits": ["high_iso"],
                            "required_report_sections": ["joint_denoise"],
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
                        {
                            "bucket_id": "narrow_bracket",
                            "label": "Narrow bracket",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": True,
                            "traits": ["narrow_ev_span"],
                            "required_report_sections": ["fallback"],
                        },
                    ],
                    "hard_case_bucket": {
                        "defined": True,
                        "member_bucket_ids": ["high_iso_hdr", "motion_heavy", "narrow_bracket"],
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
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_build_single_raw_benchmark_scaffold_preview(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    source_root = tmp_path / "benchmark_sources" / "single_raw"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "night_scene.CR3").write_bytes(b"raw")
    detail_dir = source_root / "detail_case"
    detail_dir.mkdir()
    (detail_dir / "capture.dng").write_bytes(b"raw")

    scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="single_raw",
            source_root=str(source_root),
            output_root="outputs",
        )
    )

    assert scaffold.sample_count == 2
    assert scaffold.wrote_manifest is False
    assert scaffold.wrote_result_stubs is False
    assert scaffold.manifest_payload["status"] == "partially_populated"
    assert scaffold.samples[0].benchmark_result_path.startswith("outputs/_benchmark_results_staging/single_raw/")
    assert scaffold.issues == []


def test_build_tri_raw_benchmark_scaffold_writes_manifest_and_result_stubs(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    source_root = tmp_path / "benchmark_sources" / "tri_raw"
    for bucket_id, sample_name in [("static_hdr", "tripod_room"), ("motion_heavy", "street_walk")]:
        sample_root = source_root / bucket_id / sample_name
        sample_root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            (sample_root / f"frame_0{index}.dng").write_bytes(b"raw")

    scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="tri_raw",
            source_root=str(source_root),
            output_root="outputs",
            write_manifest=True,
            write_result_stubs=True,
        )
    )

    manifest_path = tmp_path / "PROJECT_FOUNDATION" / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json"
    assert scaffold.sample_count == 2
    assert scaffold.wrote_manifest is True
    assert scaffold.wrote_result_stubs is True
    assert manifest_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["status"] == "partially_populated"
    assert scaffold.populated_bucket_ids == ["static_hdr", "motion_heavy"]
    assert scaffold.missing_bucket_ids == ["high_iso_hdr", "narrow_bracket"]
    assert len(scaffold.result_stub_paths) == 2

    stub_payload = json.loads(Path(scaffold.result_stub_paths[0]).read_text(encoding="utf-8"))
    assert stub_payload["status"] == "pending_measurement"


def test_build_tri_raw_benchmark_scaffold_reports_invalid_sample_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    source_root = tmp_path / "benchmark_sources" / "tri_raw" / "static_hdr" / "broken_case"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "frame_01.dng").write_bytes(b"raw")
    (source_root / "frame_02.dng").write_bytes(b"raw")

    scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="tri_raw",
            source_root=str(tmp_path / "benchmark_sources" / "tri_raw"),
            output_root="outputs",
        )
    )

    assert scaffold.sample_count == 0
    assert any(issue.code == "tri_raw_sample_dir_invalid" for issue in scaffold.issues)


def test_build_single_raw_benchmark_scaffold_merges_official_manifest_without_clobbering_result_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    manifest_path = tmp_path / "PROJECT_FOUNDATION" / "SINGLE_RAW_GOLD_SET_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "updated_scene",
                        "raw_path": "samples/old/input.dng",
                        "benchmark_result_path": "outputs/benchmarks/existing/updated_scene.json",
                        "notes": ["preserve me"],
                    },
                    {
                        "sample_id": "kept_manual",
                        "raw_path": "samples/manual/input.dng",
                        "benchmark_result_path": "outputs/benchmarks/existing/kept_manual.json",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    source_root = tmp_path / "benchmark_sources" / "single_raw"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "updated_scene.CR3").write_bytes(b"raw")
    (source_root / "new_scene.CR3").write_bytes(b"raw")

    scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="single_raw",
            source_root=str(source_root),
            output_root="outputs",
            manifest_merge_mode="merge_preserve_existing",
            write_manifest=True,
        )
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples_by_id = {entry["sample_id"]: entry for entry in payload["samples"]}

    assert scaffold.manifest_merge_mode == "merge_preserve_existing"
    assert scaffold.existing_sample_count == 2
    assert scaffold.added_sample_count == 1
    assert scaffold.merged_sample_count == 1
    assert scaffold.preserved_existing_sample_count == 1
    assert scaffold.removed_sample_count == 0
    assert scaffold.preserved_result_path_sample_ids == ["updated_scene"]
    assert len(payload["samples"]) == 3
    assert samples_by_id["updated_scene"]["raw_path"] == "benchmark_sources/single_raw/updated_scene.CR3"
    assert samples_by_id["updated_scene"]["benchmark_result_path"] == "outputs/benchmarks/existing/updated_scene.json"
    assert samples_by_id["updated_scene"]["notes"] == ["preserve me"]
    assert samples_by_id["kept_manual"]["benchmark_result_path"] == "outputs/benchmarks/existing/kept_manual.json"
    assert samples_by_id["new_scene"]["benchmark_result_path"].startswith("outputs/_benchmark_results_staging/single_raw/")
