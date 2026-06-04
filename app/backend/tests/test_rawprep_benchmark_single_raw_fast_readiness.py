import json
from pathlib import Path

from app.core.rawprep_benchmark_single_raw_fast_readiness import (
    RawPrepSingleRawFastReadinessRequest,
    build_rawprep_single_raw_fast_readiness,
    load_rawprep_single_raw_fast_readiness,
    write_rawprep_single_raw_fast_readiness,
)


def _write_report(path: Path, *, timing_ms_mean: float = 4884.4729, measured: int = 8, expected: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "single_raw_summary": {
                    "sample_count": expected,
                    "measured_sample_count": measured,
                    "timing_ms_mean": timing_ms_mean,
                    "metric_mean_by_axis": {
                        "detail_preservation": 0.5,
                        "color_stability": 1.0,
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_healthcheck(path: Path, *, total_ms: float = 9701.986, execution_mode: str = "fast") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "sample_raw_path": "/workspace/DreamCatcher/benchmark/samples/single_raw/sample/input.CR3",
                "sample_decode_ok": True,
                "sample_result": {
                    "execution_mode": execution_mode,
                    "runtime_profile": "sensor_fast_preview_v1",
                    "input_preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/diagnostics/input_preview.jpg",
                    "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
                    "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
                    "noise_report": {"summary": "ok"},
                    "artifact_guardrail": {"summary": "ok"},
                    "timing_report": {"total_ms": total_ms},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_single_raw_fast_readiness_reports_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_fast_readiness.repo_root", lambda: tmp_path)
    report_path = tmp_path / "outputs" / "benchmarks" / "measured" / "rawprep_benchmark_report.json"
    healthcheck_path = tmp_path / "app" / "runtime" / "single_raw_healthcheck.json"
    _write_report(report_path)
    _write_healthcheck(healthcheck_path)

    artifact = build_rawprep_single_raw_fast_readiness(
        RawPrepSingleRawFastReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is True
    assert artifact.status == "ready_for_practical_use"
    assert artifact.checks.local_fast_timing_within_target is True
    assert artifact.checks.runpod_fast_timing_within_target is True


def test_build_single_raw_fast_readiness_reports_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_fast_readiness.repo_root", lambda: tmp_path)

    artifact = build_rawprep_single_raw_fast_readiness(
        RawPrepSingleRawFastReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is False
    assert artifact.status == "missing_evidence"
    assert artifact.blockers


def test_write_single_raw_fast_readiness_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_fast_readiness.repo_root", lambda: tmp_path)
    report_path = tmp_path / "outputs" / "benchmarks" / "measured" / "rawprep_benchmark_report.json"
    healthcheck_path = tmp_path / "app" / "runtime" / "single_raw_healthcheck.json"
    _write_report(report_path)
    _write_healthcheck(healthcheck_path)

    artifact = write_rawprep_single_raw_fast_readiness(
        RawPrepSingleRawFastReadinessRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )
    loaded = load_rawprep_single_raw_fast_readiness("benchmarks/measured", output_root="outputs")

    assert Path(artifact.artifact_path).exists()
    assert loaded.status == "ready_for_practical_use"
    assert loaded.runpod_runtime_profile == "sensor_fast_preview_v1"
