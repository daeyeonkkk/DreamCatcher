import json
from pathlib import Path

from PIL import Image

from app.core.rawprep_benchmark_local_e2e_smoke import (
    RawPrepBenchmarkLocalE2ESmokeRequest,
    load_rawprep_benchmark_local_e2e_smoke,
    write_rawprep_benchmark_local_e2e_smoke,
)


def _write_preview(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (96, 72), color).save(path)


def _write_sample_manifests(repo_root: Path) -> None:
    benchmark_root = repo_root / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "BENCHMARK_CATALOG.json").write_text(
        json.dumps({"catalog_version": "2026-04-09"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    single_root = benchmark_root / "samples" / "single_raw" / "single_demo"
    single_root.mkdir(parents=True, exist_ok=True)
    (single_root / "IMG_0001.CR3").write_bytes(b"raw")
    _write_preview(single_root / "IMG_0001.JPG", (164, 132, 118))

    tri_root = benchmark_root / "samples" / "tri_raw" / "static_hdr" / "tri_demo"
    tri_root.mkdir(parents=True, exist_ok=True)
    for index, color in enumerate(((126, 118, 108), (148, 138, 124), (174, 160, 144)), start=1):
        (tri_root / f"IMG_100{index}.CR3").write_bytes(b"raw")
        _write_preview(tri_root / f"IMG_100{index}.JPG", color)

    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "single_demo",
                        "raw_path": "benchmark/samples/single_raw/single_demo/IMG_0001.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/single_demo.json",
                    }
                ],
            },
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
                        "sample_id": "static_hdr__tri_demo",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "benchmark/samples/tri_raw/static_hdr/tri_demo/IMG_1001.CR3",
                            "benchmark/samples/tri_raw/static_hdr/tri_demo/IMG_1002.CR3",
                            "benchmark/samples/tri_raw/static_hdr/tri_demo/IMG_1003.CR3",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results_staging/tri_raw/static_hdr/static_hdr__tri_demo.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_write_rawprep_benchmark_local_e2e_smoke_materializes_single_and_tri_raw(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_e2e_smoke.repo_root", lambda: tmp_path)

    _write_sample_manifests(tmp_path)

    smoke = write_rawprep_benchmark_local_e2e_smoke(
        RawPrepBenchmarkLocalE2ESmokeRequest(
            output_dir="benchmarks/local_e2e_demo",
            output_root="outputs",
        )
    )

    assert smoke.ok is True
    assert smoke.status == "passed"
    assert smoke.single_raw.sample_id == "single_demo"
    assert smoke.single_raw.ready_for_edit_ui is True
    assert smoke.single_raw.foundation_report_path is not None
    assert smoke.single_raw.scene_linear_path is not None
    assert smoke.single_raw.dreamisp_render_preview_path is not None
    assert smoke.tri_raw.sample_id == "static_hdr__tri_demo"
    assert smoke.tri_raw.ready_for_edit_ui is True
    assert smoke.tri_raw.foundation_report_path is not None
    assert smoke.tri_raw.foundation_preview_path is not None
    assert smoke.tri_raw.scene_linear_path is not None
    assert smoke.tri_raw.rawprep_job_path is not None
    assert smoke.tri_raw.dreamisp_render_preview_path is not None

    artifact_path = tmp_path / "outputs" / "benchmarks" / "local_e2e_demo" / "rawprep_local_e2e_smoke.json"
    assert artifact_path.exists()

    loaded = load_rawprep_benchmark_local_e2e_smoke("benchmarks/local_e2e_demo", output_root="outputs")
    assert loaded.status == "passed"
    assert loaded.single_raw.ready_for_edit_ui is True
    assert loaded.tri_raw.ready_for_edit_ui is True
