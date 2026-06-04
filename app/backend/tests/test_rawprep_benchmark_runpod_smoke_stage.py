import json
from pathlib import Path
from zipfile import ZipFile

from app.core.rawprep_benchmark_runpod_smoke_stage import (
    RawPrepBenchmarkRunPodSmokeStageRequest,
    build_rawprep_benchmark_runpod_smoke_stage,
    load_rawprep_benchmark_runpod_smoke_stage,
    write_rawprep_benchmark_runpod_smoke_stage,
)


def _write_single_raw_manifest(repo_root: Path) -> None:
    benchmark_root = repo_root / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    sample_root = benchmark_root / "samples" / "single_raw" / "sample_one"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "input.CR3").write_bytes(b"raw")
    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "sample_one",
                        "raw_path": "benchmark/samples/single_raw/sample_one/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/sample_one.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_runpod_smoke_stage_previews_bundle_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    _write_single_raw_manifest(tmp_path)

    stage = build_rawprep_benchmark_runpod_smoke_stage(
        RawPrepBenchmarkRunPodSmokeStageRequest(
            output_dir="benchmarks/runpod_stage",
            output_root="outputs",
        )
    )

    assert stage.status == "ready"
    assert stage.archive_created is False
    assert stage.stage_root_path is not None and stage.stage_root_path.endswith("_runpod_smoke_sample_bundle")
    assert stage.archive_path is not None and stage.archive_path.endswith("rawprep_runpod_smoke_sample_bundle.zip")
    assert stage.bundle_relative_paths == ["benchmark/samples/single_raw/sample_one/input.CR3"]
    assert stage.runpod_extract_command is not None
    assert "zipfile.ZipFile" in stage.runpod_extract_command
    assert "/workspace/rawprep_runpod_smoke_sample_bundle.zip" in stage.runpod_extract_command
    assert "/workspace/DreamCatcher" in stage.runpod_extract_command


def test_write_runpod_smoke_stage_materializes_bundle_and_archive(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    _write_single_raw_manifest(tmp_path)

    stage = write_rawprep_benchmark_runpod_smoke_stage(
        RawPrepBenchmarkRunPodSmokeStageRequest(
            output_dir="benchmarks/runpod_stage",
            output_root="outputs",
            write_archive=True,
        )
    )

    assert stage.status == "ready"
    assert stage.archive_created is True
    assert stage.plan_path is not None and Path(stage.plan_path).exists()
    assert stage.stage_record_path is not None and Path(stage.stage_record_path).exists()
    assert stage.staged_sample_raw_path is not None and Path(stage.staged_sample_raw_path).exists()
    assert stage.archive_path is not None and Path(stage.archive_path).exists()

    with ZipFile(stage.archive_path) as archive:
        assert archive.namelist() == ["benchmark/samples/single_raw/sample_one/input.CR3"]

    loaded = load_rawprep_benchmark_runpod_smoke_stage("benchmarks/runpod_stage", output_root="outputs")
    assert loaded.archive_created is True
    assert loaded.selected_sample_id == "sample_one"
