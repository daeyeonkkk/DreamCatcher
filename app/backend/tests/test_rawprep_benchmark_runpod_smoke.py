import json
from pathlib import Path

from app.core.rawprep_benchmark_runpod_smoke import (
    build_rawprep_benchmark_runpod_smoke,
    load_rawprep_benchmark_runpod_smoke,
    write_rawprep_benchmark_runpod_smoke,
)


def _write_runpod_smoke_evidence(repo_root: Path, *, include_sample_smoke: bool = True) -> None:
    runtime_root = repo_root / "app" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    rawprep_payload = {
        "ok": False,
        "message": "dreamcatcher-raw-engine-v2 is still scaffolded.",
    }
    single_raw_payload = {
        "ok": True,
        "preferred_backend": "rawpy",
    }
    if include_sample_smoke:
        single_raw_payload.update(
            {
                "sample_raw_path": "/workspace/sample_raw/input.CR3",
                "sample_decode_ok": True,
                "sample_result": {
                    "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
                    "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
                },
            }
        )
    bootstrap_payload = {
        "checks": {
            "comfy_ready": True,
            "backend_ready": True,
            "runtime_workflows_present": True,
            "rawprep_healthcheck_present": True,
            "single_raw_runtime_ready": True,
            "single_raw_healthcheck_present": True,
        },
        "rawprep_healthcheck": rawprep_payload,
        "single_raw_healthcheck": single_raw_payload,
    }
    (runtime_root / "rawprep_healthcheck.json").write_text(json.dumps(rawprep_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "single_raw_healthcheck.json").write_text(json.dumps(single_raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "bootstrap_summary.json").write_text(json.dumps(bootstrap_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_rawprep_benchmark_runpod_smoke_reports_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)

    smoke = build_rawprep_benchmark_runpod_smoke("benchmarks/run_measured", output_root="outputs")

    assert smoke.ok is False
    assert smoke.status == "missing"
    assert any(issue.code == "runpod_bootstrap_summary_missing" for issue in smoke.blockers)


def test_write_rawprep_benchmark_runpod_smoke_persists_canonical_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_runpod_smoke_evidence(tmp_path)

    smoke = write_rawprep_benchmark_runpod_smoke("benchmarks/run_measured", output_root="outputs")
    loaded = load_rawprep_benchmark_runpod_smoke("benchmarks/run_measured", output_root="outputs")

    assert smoke.ok is True
    assert smoke.status == "passed"
    assert smoke.smoke_path is not None
    assert Path(smoke.smoke_path).exists()
    assert loaded.preferred_single_raw_backend == "rawpy"
    assert loaded.single_raw_sample_smoke_status == "passed"
    assert any(issue.code == "runpod_rawprep_healthcheck_not_ok" for issue in loaded.warnings)


def test_build_rawprep_benchmark_runpod_smoke_marks_bootstrap_only_without_sample_decode(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_runpod_smoke_evidence(tmp_path, include_sample_smoke=False)

    smoke = build_rawprep_benchmark_runpod_smoke("benchmarks/run_measured", output_root="outputs")

    assert smoke.ok is False
    assert smoke.status == "bootstrap_only"
    assert smoke.single_raw_sample_smoke_status == "missing"
    assert any(issue.code == "runpod_single_raw_sample_smoke_missing" for issue in smoke.blockers)
