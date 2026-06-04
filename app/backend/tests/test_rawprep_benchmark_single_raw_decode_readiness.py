import json
from pathlib import Path

from app.core.rawprep_benchmark_single_raw_decode_readiness import (
    RawPrepSingleRawDecodeReadinessRequest,
    build_rawprep_single_raw_decode_readiness,
    load_rawprep_single_raw_decode_readiness,
    write_rawprep_single_raw_decode_readiness,
)


def _write_healthcheck(path: Path, *, sample_decode_ok: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "preferred_backend": "rawpy",
                "required_modules": {
                    "rawpy": True,
                    "numpy": True,
                    "tifffile": True,
                    "PIL": True,
                },
                "supports_sensor_decode": True,
                "sample_raw_path": "/workspace/DreamCatcher/benchmark/samples/single_raw/sample/input.CR3",
                "sample_decode_ok": sample_decode_ok,
                "sample_result": {
                    "runtime_profile": "sensor_fast_preview_v1",
                    "input_preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/diagnostics/input_preview.jpg",
                    "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
                    "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
                    "scene_linear_format": "tiff",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_single_raw_decode_readiness_reports_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_decode_readiness.repo_root", lambda: tmp_path)
    healthcheck_path = tmp_path / "app" / "runtime" / "single_raw_healthcheck.json"
    _write_healthcheck(healthcheck_path)

    artifact = build_rawprep_single_raw_decode_readiness(
        RawPrepSingleRawDecodeReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is True
    assert artifact.status == "ready_for_sensor_decode"
    assert artifact.checks.sample_decode_ok is True
    assert artifact.checks.editable_artifacts_available is True


def test_build_single_raw_decode_readiness_reports_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_decode_readiness.repo_root", lambda: tmp_path)

    artifact = build_rawprep_single_raw_decode_readiness(
        RawPrepSingleRawDecodeReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is False
    assert artifact.status == "missing_evidence"
    assert artifact.blockers


def test_write_single_raw_decode_readiness_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_decode_readiness.repo_root", lambda: tmp_path)
    healthcheck_path = tmp_path / "app" / "runtime" / "single_raw_healthcheck.json"
    _write_healthcheck(healthcheck_path)

    artifact = write_rawprep_single_raw_decode_readiness(
        RawPrepSingleRawDecodeReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )
    loaded = load_rawprep_single_raw_decode_readiness("benchmarks/measured", output_root="outputs")

    assert Path(artifact.artifact_path).exists()
    assert loaded.status == "ready_for_sensor_decode"
    assert loaded.preferred_backend == "rawpy"
