from pathlib import Path

from app.core.rawprep_benchmark_local_recovery_smoke import (
    RawPrepBenchmarkLocalRecoverySmokeRequest,
    load_rawprep_benchmark_local_recovery_smoke,
    write_rawprep_benchmark_local_recovery_smoke,
)


def test_write_rawprep_benchmark_local_recovery_smoke_materializes_blocked_and_ready_cases(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_recovery_smoke.repo_root", lambda: tmp_path)

    smoke = write_rawprep_benchmark_local_recovery_smoke(
        RawPrepBenchmarkLocalRecoverySmokeRequest(
            output_dir="benchmarks/local_recovery_demo",
            output_root="outputs",
        )
    )

    assert smoke.ok is True
    assert smoke.status == "passed"
    assert smoke.blocked_without_package.status == "passed"
    assert smoke.blocked_without_package.ready_for_provider_pause is False
    assert smoke.blocked_without_package.metadata_snapshot_path is not None
    assert smoke.blocked_without_package.package_archive_path is None
    assert smoke.ready_with_package.status == "passed"
    assert smoke.ready_with_package.ready_for_provider_pause is True
    assert smoke.ready_with_package.metadata_snapshot_path is not None
    assert smoke.ready_with_package.package_archive_path is not None
    assert Path(tmp_path / smoke.ready_with_package.package_archive_path).exists()

    artifact_path = tmp_path / "outputs" / "benchmarks" / "local_recovery_demo" / "rawprep_local_recovery_smoke.json"
    assert artifact_path.exists()

    loaded = load_rawprep_benchmark_local_recovery_smoke("benchmarks/local_recovery_demo", output_root="outputs")
    assert loaded.status == "passed"
    assert loaded.ready_with_package.ready_for_provider_pause is True
