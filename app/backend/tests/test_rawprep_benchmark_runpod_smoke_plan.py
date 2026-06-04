import json
from pathlib import Path

from app.core.rawprep_benchmark_runpod_smoke_plan import (
    RawPrepBenchmarkRunPodSmokePlanRequest,
    load_rawprep_benchmark_runpod_smoke_plan,
    write_rawprep_benchmark_runpod_smoke_plan,
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


def test_write_runpod_smoke_plan_selects_ready_sample(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    _write_single_raw_manifest(tmp_path)

    plan = write_rawprep_benchmark_runpod_smoke_plan(
        RawPrepBenchmarkRunPodSmokePlanRequest(
            output_dir="benchmarks/runpod_plan",
            output_root="outputs",
        )
    )

    assert plan.status == "ready"
    assert plan.selected_sample_id == "sample_one"
    assert plan.sample_exists is True
    assert plan.runpod_sample_raw_path == "/workspace/DreamCatcher/benchmark/samples/single_raw/sample_one/input.CR3"
    assert plan.recommended_runtime_output_path == "/workspace/DreamCatcher/app/runtime/single_raw_healthcheck.json"
    assert plan.command_preview is not None and "--sample-raw /workspace/DreamCatcher/benchmark/samples/single_raw/sample_one/input.CR3" in plan.command_preview
    assert plan.plan_path is not None and Path(plan.plan_path).exists()

    loaded = load_rawprep_benchmark_runpod_smoke_plan("benchmarks/runpod_plan", output_root="outputs")
    assert loaded.status == "ready"
    assert loaded.expected_artifacts == [
        "app/runtime/single_raw_healthcheck.json",
        "preview.jpg",
        "scene_linear.tiff",
        "noise_map.png",
        "lowlight_recovery_map.png",
    ]
