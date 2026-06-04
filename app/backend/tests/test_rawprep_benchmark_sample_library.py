from __future__ import annotations

import json
from pathlib import Path

from app.core.rawprep_benchmark_sample_library import (
    load_rawprep_benchmark_sample_library_plan,
    materialize_rawprep_benchmark_sample_library,
)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_materialize_benchmark_sample_library_copies_curated_tree(tmp_path: Path) -> None:
    source_root = tmp_path / "dcim"
    repo_root = Path(__file__).resolve().parents[3]
    plan_path = repo_root / "benchmark" / "TEST_SAMPLE_LIBRARY_PLAN.json"
    sample_root = repo_root / "benchmark" / "test_samples"

    _write_bytes(source_root / "102_PANA" / "IMG_0001.CR3", b"raw-a")
    _write_bytes(source_root / "102_PANA" / "IMG_0001.JPG", b"jpg-a")
    _write_bytes(source_root / "104CANON" / "IMG_0002.CR3", b"raw-b")
    _write_bytes(source_root / "104CANON" / "IMG_0003.CR3", b"raw-c")
    _write_bytes(source_root / "104CANON" / "IMG_0004.CR3", b"raw-d")
    _write_bytes(source_root / "104CANON" / "IMG_0002.JPG", b"jpg-b")

    plan_payload = {
        "plan_version": "test",
        "single_raw": [
            {
                "sample_id": "single_sample_001",
                "source_paths": ["102_PANA/IMG_0001.CR3"],
                "companion_paths": ["102_PANA/IMG_0001.JPG"],
            }
        ],
        "tri_raw": [
            {
                "bucket_id": "motion_heavy",
                "sample_id": "tri_sample_001",
                "source_paths": [
                    "104CANON/IMG_0002.CR3",
                    "104CANON/IMG_0003.CR3",
                    "104CANON/IMG_0004.CR3",
                ],
                "companion_paths": ["104CANON/IMG_0002.JPG"],
            }
        ],
    }
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        result = materialize_rawprep_benchmark_sample_library(
            source_root=str(source_root),
            plan_path=_repo_relative(plan_path),
            benchmark_sample_root=_repo_relative(sample_root),
        )

        assert result.single_raw_count == 1
        assert result.tri_raw_count == 1
        assert (sample_root / "single_raw" / "single_sample_001" / "IMG_0001.CR3").read_bytes() == b"raw-a"
        assert (sample_root / "single_raw" / "single_sample_001" / "IMG_0001.JPG").read_bytes() == b"jpg-a"
        assert (sample_root / "tri_raw" / "motion_heavy" / "tri_sample_001" / "IMG_0004.CR3").read_bytes() == b"raw-d"
        assert (sample_root / "tri_raw" / "motion_heavy" / "tri_sample_001" / "IMG_0002.JPG").read_bytes() == b"jpg-b"
    finally:
        if plan_path.exists():
            plan_path.unlink()
        if sample_root.exists():
            import shutil

            shutil.rmtree(sample_root)


def test_materialize_benchmark_sample_library_rejects_source_escape(tmp_path: Path) -> None:
    source_root = tmp_path / "dcim"
    repo_root = Path(__file__).resolve().parents[3]
    plan_path = repo_root / "benchmark" / "TEST_SAMPLE_LIBRARY_PLAN.json"
    sample_root = repo_root / "benchmark" / "test_samples"

    _write_bytes(source_root / "102_PANA" / "IMG_0001.CR3", b"raw-a")

    plan_payload = {
        "plan_version": "test",
        "single_raw": [
            {
                "sample_id": "single_sample_001",
                "source_paths": ["../outside.CR3"],
            }
        ],
        "tri_raw": [],
    }
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        try:
            materialize_rawprep_benchmark_sample_library(
                source_root=str(source_root),
                plan_path=_repo_relative(plan_path),
                benchmark_sample_root=_repo_relative(sample_root),
            )
        except ValueError as exc:
            assert "inside source_root" in str(exc)
        else:
            raise AssertionError("Expected source path escape to raise ValueError.")
    finally:
        if plan_path.exists():
            plan_path.unlink()
        if sample_root.exists():
            import shutil

            shutil.rmtree(sample_root)


def test_load_benchmark_sample_library_plan_reads_committed_plan() -> None:
    plan = load_rawprep_benchmark_sample_library_plan("benchmark/BENCHMARK_SAMPLE_LIBRARY.json")
    assert plan.plan_version
    assert plan.single_raw
    assert plan.tri_raw


def _repo_relative(path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    return path.resolve().relative_to(repo_root.resolve()).as_posix()
