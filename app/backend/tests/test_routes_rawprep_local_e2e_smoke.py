import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app


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

    single_root = benchmark_root / "samples" / "single_raw" / "route_single_demo"
    single_root.mkdir(parents=True, exist_ok=True)
    (single_root / "IMG_0001.CR3").write_bytes(b"raw")
    _write_preview(single_root / "IMG_0001.JPG", (166, 142, 128))

    tri_root = benchmark_root / "samples" / "tri_raw" / "static_hdr" / "route_tri_demo"
    tri_root.mkdir(parents=True, exist_ok=True)
    for index, color in enumerate(((118, 112, 102), (144, 134, 122), (172, 158, 142)), start=1):
        (tri_root / f"IMG_200{index}.CR3").write_bytes(b"raw")
        _write_preview(tri_root / f"IMG_200{index}.JPG", color)

    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_single_demo",
                        "raw_path": "benchmark/samples/single_raw/route_single_demo/IMG_0001.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/route_single_demo.json",
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
                        "sample_id": "static_hdr__route_tri_demo",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "benchmark/samples/tri_raw/static_hdr/route_tri_demo/IMG_2001.CR3",
                            "benchmark/samples/tri_raw/static_hdr/route_tri_demo/IMG_2002.CR3",
                            "benchmark/samples/tri_raw/static_hdr/route_tri_demo/IMG_2003.CR3",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results_staging/tri_raw/static_hdr/static_hdr__route_tri_demo.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_rawprep_local_e2e_smoke_route_writes_and_reads_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_e2e_smoke.repo_root", lambda: tmp_path)

    _write_sample_manifests(tmp_path)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/local-e2e-smoke",
        json={
            "output_dir": "benchmarks/route_local_e2e",
            "output_root": "outputs",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["single_raw"]["ready_for_edit_ui"] is True
    assert payload["single_raw"]["scene_linear_path"] is not None
    assert payload["tri_raw"]["ready_for_edit_ui"] is True
    assert payload["tri_raw"]["foundation_report_path"] is not None
    assert payload["tri_raw"]["scene_linear_path"] is not None

    artifact_response = client.get(
        "/api/rawprep/benchmark/local-e2e-smoke/artifact",
        params={"output_dir": "benchmarks/route_local_e2e", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "passed"
    assert artifact_payload["single_raw"]["sample_id"] == "route_single_demo"
    assert artifact_payload["tri_raw"]["sample_id"] == "static_hdr__route_tri_demo"
