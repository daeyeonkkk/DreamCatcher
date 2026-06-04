import json
from pathlib import Path

from PIL import Image
import numpy as np

from app.core.rawprep_benchmark_single_raw_run import (
    RawPrepBenchmarkSingleRawRunRequest,
    run_rawprep_benchmark_single_raw_samples,
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
                        "status": "partially_populated",
                        "sample_count": 1,
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
                            "status": "spec_only",
                            "sample_count": 0,
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


def _write_single_raw_manifest(repo_root: Path, *, sample_id: str, raw_relative_path: str, result_relative_path: str) -> None:
    benchmark_root = repo_root / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": sample_id,
                        "raw_path": raw_relative_path,
                        "benchmark_result_path": result_relative_path,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (benchmark_root / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_textured_preview(path: Path) -> None:
    width, height = 96, 64
    y, x = np.indices((height, width), dtype=np.float32)
    base = ((x / max(width - 1, 1)) * 80.0) + ((y / max(height - 1, 1)) * 56.0) + 48.0
    ripple = ((np.sin(x / 4.0) + 1.0) * 18.0) + ((np.cos(y / 5.0) + 1.0) * 11.0)
    red = np.clip(base + ripple, 0.0, 255.0)
    green = np.clip(base * 0.92 + ripple * 0.7, 0.0, 255.0)
    blue = np.clip(base * 0.84 + ripple * 0.52, 0.0, 255.0)
    image = np.stack((red, green, blue), axis=2).astype(np.uint8)
    Image.fromarray(image, mode="RGB").save(path)


def test_run_rawprep_benchmark_single_raw_samples_materializes_and_writes_measurement(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_run.repo_root", lambda: tmp_path)

    _write_benchmark_foundation(tmp_path)
    benchmark_root = tmp_path / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "BENCHMARK_CATALOG.json").write_text(
        (tmp_path / "PROJECT_FOUNDATION" / "BENCHMARK_CATALOG.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    sample_root = tmp_path / "benchmark" / "samples" / "single_raw" / "route_single"
    sample_root.mkdir(parents=True, exist_ok=True)
    raw_path = sample_root / "IMG_0001.CR3"
    raw_path.write_bytes(b"raw")
    _write_textured_preview(sample_root / "IMG_0001.JPG")

    _write_single_raw_manifest(
        tmp_path,
        sample_id="route_single",
        raw_relative_path="benchmark/samples/single_raw/route_single/IMG_0001.CR3",
        result_relative_path="outputs/_benchmark_results_staging/single_raw/route_single.json",
    )

    record = run_rawprep_benchmark_single_raw_samples(
        RawPrepBenchmarkSingleRawRunRequest(
            output_root="outputs",
            run_root="_benchmark_runs/single_raw",
            mode_preference="fast",
            benchmark_output_dir="benchmarks/route_single_raw",
        )
    )

    assert record.processed_count == 1
    assert record.measured_count == 1
    assert record.success_sample_ids == ["route_single"]
    assert record.benchmark_status == "partially_populated"
    assert record.benchmark_report_status == "partially_populated"
    assert record.metric_mean_by_axis["noise_reduction"] >= 0
    assert record.metric_mean_by_axis["detail_preservation"] > 0
    assert record.metric_mean_by_axis["color_stability"] > 0
    assert record.metric_mean_by_axis["color_stability"] > 0
    assert record.timing_ms_mean is not None

    sample = record.samples[0]
    assert sample.sample_id == "route_single"
    assert sample.materialization_status == "preview_bootstrapped"
    assert sample.wrote_measurement is True
    assert sample.measurement_status == "measured"
    assert sample.report_path is not None
    assert sample.measurement_path is not None

    measurement_payload = json.loads((tmp_path / sample.measurement_path).read_text(encoding="utf-8"))
    assert measurement_payload["sample_id"] == "route_single"
    assert measurement_payload["status"] == "measured"
    assert measurement_payload["metrics"]["noise_reduction"] >= 0
    assert measurement_payload["metrics"]["detail_preservation"] > 0
    assert measurement_payload["metrics"]["color_stability"] > 0
    assert measurement_payload["metrics"]["color_stability"] > 0
