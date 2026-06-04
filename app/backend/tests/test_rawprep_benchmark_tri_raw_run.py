import json
from pathlib import Path

from PIL import Image
import numpy as np

from app.core.rawprep_benchmark_tri_raw_run import (
    RawPrepBenchmarkTriRawRunRequest,
    run_rawprep_benchmark_tri_raw_samples,
)


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (foundation / "DREAMCATCHER_V2_CHECKLIST.md").write_text("# Checklist\n", encoding="utf-8")

    benchmark_root = repo_root / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-09",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "partially_populated",
                        "sample_count": 0,
                        "evaluation_axes": [
                            "noise_reduction",
                            "detail_preservation",
                            "color_stability",
                            "processing_time",
                        ],
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
                            "required_report_sections": ["hdr_gain", "deghost", "timing"],
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


def _write_textured_preview(path: Path, *, seed_offset: float) -> None:
    width, height = 96, 64
    y, x = np.indices((height, width), dtype=np.float32)
    base = ((x / max(width - 1, 1)) * (84.0 + seed_offset)) + ((y / max(height - 1, 1)) * 48.0) + 52.0
    ripple = ((np.sin((x + seed_offset) / 4.0) + 1.0) * 17.0) + ((np.cos((y + seed_offset) / 5.0) + 1.0) * 11.0)
    red = np.clip(base + ripple, 0.0, 255.0)
    green = np.clip(base * 0.91 + ripple * 0.7, 0.0, 255.0)
    blue = np.clip(base * 0.83 + ripple * 0.55, 0.0, 255.0)
    image = np.stack((red, green, blue), axis=2).astype(np.uint8)
    Image.fromarray(image, mode="RGB").save(path)


def _write_tri_raw_manifest(repo_root: Path, *, sample_id: str, bucket_id: str, source_paths: list[str], result_path: str) -> None:
    benchmark_root = repo_root / "benchmark"
    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {"manifest_version": "2026-04-09", "status": "partially_populated", "samples": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (benchmark_root / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": sample_id,
                        "bucket_id": bucket_id,
                        "source_paths": source_paths,
                        "benchmark_result_path": result_path,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_run_rawprep_benchmark_tri_raw_samples_materializes_and_writes_measurement(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_tri_raw_run.repo_root", lambda: tmp_path)

    _write_benchmark_foundation(tmp_path)

    sample_root = tmp_path / "benchmark" / "samples" / "tri_raw" / "static_hdr" / "window_demo"
    sample_root.mkdir(parents=True, exist_ok=True)
    raw_relative_paths: list[str] = []
    for index, seed_offset in enumerate((0.0, 4.0, 8.0), start=1):
        raw_path = sample_root / f"IMG_10{index}.CR3"
        raw_path.write_bytes(b"raw")
        _write_textured_preview(sample_root / f"IMG_10{index}.JPG", seed_offset=seed_offset)
        raw_relative_paths.append(
            f"benchmark/samples/tri_raw/static_hdr/window_demo/{raw_path.name}"
        )

    _write_tri_raw_manifest(
        tmp_path,
        sample_id="static_hdr__window_demo",
        bucket_id="static_hdr",
        source_paths=raw_relative_paths,
        result_path="outputs/_benchmark_results_staging/tri_raw/static_hdr/static_hdr__window_demo.json",
    )

    record = run_rawprep_benchmark_tri_raw_samples(
        RawPrepBenchmarkTriRawRunRequest(
            output_root="outputs",
            run_root="_benchmark_runs/tri_raw",
            requested_reference_policy="auto",
            benchmark_output_dir="benchmarks/route_tri_raw",
        )
    )

    assert record.processed_count == 1
    assert record.measured_count == 1
    assert record.success_sample_ids == ["static_hdr__window_demo"]
    assert record.benchmark_status == "partially_populated"
    assert record.benchmark_report_status == "partially_populated"
    assert record.measured_bucket_ids == ["static_hdr"]
    assert record.timing_ms_mean is not None
    assert record.metric_mean_by_axis["hdr_gain_coverage"] >= 0
    assert record.metric_mean_by_axis["mean_confidence"] >= 0
    assert record.metric_mean_by_axis["frontier_total_score"] >= 0
    assert "frontier_score_delta_vs_baseline" in record.metric_mean_by_axis

    sample = record.samples[0]
    assert sample.sample_id == "static_hdr__window_demo"
    assert sample.bucket_id == "static_hdr"
    assert sample.materialization_status == "preview_fused"
    assert sample.runtime_backend == "companion_preview"
    assert sample.wrote_measurement is True
    assert sample.measurement_status == "measured"
    assert sample.report_path is not None
    assert sample.measurement_path is not None
    assert sample.metrics["hdr_gain_coverage"] >= 0
    assert sample.metrics["alignment_pressure_score"] >= 0
    assert sample.metrics["frontier_total_score"] >= 0

    measurement_payload = json.loads((tmp_path / sample.measurement_path).read_text(encoding="utf-8"))
    assert measurement_payload["sample_id"] == "static_hdr__window_demo"
    assert measurement_payload["status"] == "measured"
    assert measurement_payload["metrics"]["hdr_gain_coverage"] >= 0
    assert measurement_payload["metrics"]["mean_confidence"] >= 0
    assert measurement_payload["metrics"]["frontier_total_score"] >= 0

    report_payload = json.loads((tmp_path / sample.report_path).read_text(encoding="utf-8"))
    assert report_payload["status"] == "preview_fused"
    assert report_payload["timing_report"]["runner_total_ms"] is not None
    assert report_payload["fallback_strategy"]["selected_action"]
    assert report_payload["frontier_eval"]["eval_id"] == "tri_raw_frontier_eval_v1"
    assert Path(report_payload["frontier_eval_path"]).is_file()
