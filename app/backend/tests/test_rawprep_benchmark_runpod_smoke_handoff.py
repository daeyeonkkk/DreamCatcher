import json
from pathlib import Path
from zipfile import ZipFile

from app.core.rawprep_benchmark_runpod_smoke_handoff import (
    EMBEDDED_SMOKE_BUNDLE_RELATIVE_PATH,
    RawPrepBenchmarkRunPodSmokeHandoffRequest,
    build_rawprep_benchmark_runpod_smoke_handoff,
    load_rawprep_benchmark_runpod_smoke_handoff,
    write_rawprep_benchmark_runpod_smoke_handoff,
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


def _write_release_bundle_manifest(repo_root: Path) -> None:
    runpod_root = repo_root / "runpod"
    runpod_root.mkdir(parents=True, exist_ok=True)
    (runpod_root / "release_bundle_manifest.json").write_text(
        json.dumps({"official_artifact_name": "DreamCatcher.zip"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_release_bundle_zip(repo_root: Path) -> None:
    with ZipFile(repo_root / "DreamCatcher.zip", "w") as archive:
        archive.writestr("DreamCatcher/README.txt", "bundle")


def test_build_runpod_smoke_handoff_reports_missing_app_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_handoff.repo_root", lambda: tmp_path)
    _write_single_raw_manifest(tmp_path)
    _write_release_bundle_manifest(tmp_path)

    handoff = build_rawprep_benchmark_runpod_smoke_handoff(
        RawPrepBenchmarkRunPodSmokeHandoffRequest(
            output_dir="benchmarks/runpod_handoff",
            output_root="outputs",
        )
    )

    assert handoff.status == "missing_app_and_smoke_bundle"
    assert handoff.official_app_bundle_exists is False
    assert handoff.smoke_bundle_exists is False
    assert handoff.embedded_smoke_bundle_exists is False
    assert any("preflight_release_bundle.py" in action for action in handoff.recommended_actions)


def test_write_runpod_smoke_handoff_materializes_artifact_and_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_handoff.repo_root", lambda: tmp_path)
    _write_single_raw_manifest(tmp_path)
    _write_release_bundle_manifest(tmp_path)
    _write_release_bundle_zip(tmp_path)

    handoff = write_rawprep_benchmark_runpod_smoke_handoff(
        RawPrepBenchmarkRunPodSmokeHandoffRequest(
            output_dir="benchmarks/runpod_handoff",
            output_root="outputs",
        )
    )

    assert handoff.status == "ready_for_upload"
    assert handoff.official_app_bundle_exists is True
    assert handoff.smoke_bundle_exists is True
    assert handoff.embedded_smoke_bundle_exists is True
    assert handoff.handoff_path is not None and Path(handoff.handoff_path).exists()
    assert handoff.runbook_markdown_path is not None and Path(handoff.runbook_markdown_path).exists()
    assert handoff.runbook_script_path is not None and Path(handoff.runbook_script_path).exists()
    assert handoff.smoke_bundle_path is not None and Path(handoff.smoke_bundle_path).exists()
    assert [upload.runpod_path for upload in handoff.uploads] == ["/workspace/DreamCatcher.zip"]
    assert not any("rawprep_runpod_smoke_sample_bundle.zip" in command for command in handoff.runpod_prepare_commands)

    with ZipFile(tmp_path / "DreamCatcher.zip") as archive:
        assert f"DreamCatcher/{EMBEDDED_SMOKE_BUNDLE_RELATIVE_PATH}" in archive.namelist()

    loaded = load_rawprep_benchmark_runpod_smoke_handoff("benchmarks/runpod_handoff", output_root="outputs")
    assert loaded.status == "ready_for_upload"
    assert loaded.selected_sample_id == "sample_one"
    assert loaded.embedded_smoke_bundle_exists is True
