from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .rawprep_benchmark_scaffold import (
    RawPrepBenchmarkScaffold,
    RawPrepBenchmarkScaffoldRequest,
    build_rawprep_benchmark_scaffold,
)
from .studio_paths import repo_root


class RawPrepBenchmarkSingleRawLibrarySample(BaseModel):
    sample_id: str
    label: str | None = None
    source_paths: list[str] = Field(default_factory=list)
    companion_paths: list[str] = Field(default_factory=list)
    selection_reason: str | None = None


class RawPrepBenchmarkTriRawLibrarySample(RawPrepBenchmarkSingleRawLibrarySample):
    bucket_id: str


class RawPrepBenchmarkSampleLibraryPlan(BaseModel):
    plan_version: str
    source_root_hint: str | None = None
    notes: list[str] = Field(default_factory=list)
    single_raw: list[RawPrepBenchmarkSingleRawLibrarySample] = Field(default_factory=list)
    tri_raw: list[RawPrepBenchmarkTriRawLibrarySample] = Field(default_factory=list)


class RawPrepBenchmarkSampleLibraryMaterializedSample(BaseModel):
    mode: Literal["single_raw", "tri_raw"]
    sample_id: str
    bucket_id: str | None = None
    label: str | None = None
    destination_dir: str
    copied_paths: list[str] = Field(default_factory=list)
    selection_reason: str | None = None


class RawPrepBenchmarkSampleLibraryMaterialization(BaseModel):
    source_root: str
    plan_path: str
    benchmark_sample_root: str
    plan_version: str
    single_raw_count: int = 0
    tri_raw_count: int = 0
    copied_file_count: int = 0
    samples: list[RawPrepBenchmarkSampleLibraryMaterializedSample] = Field(default_factory=list)
    summary: str


class RawPrepBenchmarkSampleLibrarySyncRequest(BaseModel):
    source_root: str
    plan_path: str = "benchmark/BENCHMARK_SAMPLE_LIBRARY.json"
    benchmark_sample_root: str = "benchmark/samples"
    output_root: str = "outputs"
    manifest_merge_mode: Literal["replace", "merge_preserve_existing"] = "replace"
    write_manifest: bool = True
    write_result_stubs: bool = True


class RawPrepBenchmarkSampleLibrarySync(BaseModel):
    materialization: RawPrepBenchmarkSampleLibraryMaterialization
    single_raw_scaffold: RawPrepBenchmarkScaffold
    tri_raw_scaffold: RawPrepBenchmarkScaffold
    summary: str


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    resolved = path.resolve() if path.is_absolute() else (repo_root() / path).resolve()
    root = repo_root().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside the repository: {resolved}") from exc
    return resolved


def _resolve_source_root(path_value: str) -> Path:
    path = Path(path_value)
    resolved = path.resolve() if path.is_absolute() else (repo_root() / path).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"Benchmark source_root was not found or is not a directory: {resolved}")
    return resolved


def _resolve_source_child(source_root: Path, relative_path: str) -> Path:
    candidate = (source_root / relative_path).resolve()
    try:
        candidate.relative_to(source_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Sample source path must stay inside source_root: {relative_path}") from exc
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"Sample source file was not found: {candidate}")
    return candidate


def _replace_directory(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Refusing to replace a directory outside benchmark_sample_root: {resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def load_rawprep_benchmark_sample_library_plan(plan_path: str | Path) -> RawPrepBenchmarkSampleLibraryPlan:
    resolved_path = _resolve_repo_path(str(plan_path))
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark sample library plan must be a JSON object: {resolved_path}")
    return RawPrepBenchmarkSampleLibraryPlan.model_validate(payload)


def materialize_rawprep_benchmark_sample_library(
    *,
    source_root: str,
    plan_path: str = "benchmark/BENCHMARK_SAMPLE_LIBRARY.json",
    benchmark_sample_root: str = "benchmark/samples",
) -> RawPrepBenchmarkSampleLibraryMaterialization:
    resolved_source_root = _resolve_source_root(source_root)
    resolved_plan_path = _resolve_repo_path(plan_path)
    resolved_sample_root = _resolve_repo_path(benchmark_sample_root)
    resolved_sample_root.mkdir(parents=True, exist_ok=True)
    (resolved_sample_root / "single_raw").mkdir(parents=True, exist_ok=True)
    (resolved_sample_root / "tri_raw").mkdir(parents=True, exist_ok=True)

    plan = load_rawprep_benchmark_sample_library_plan(resolved_plan_path)
    samples: list[RawPrepBenchmarkSampleLibraryMaterializedSample] = []
    copied_file_count = 0

    for entry in plan.single_raw:
        if len(entry.source_paths) != 1:
            raise ValueError(f"SingleRaw sample '{entry.sample_id}' must declare exactly 1 source_paths entry.")
        destination_dir = resolved_sample_root / "single_raw" / entry.sample_id
        _replace_directory(destination_dir, resolved_sample_root)

        copied_paths: list[str] = []
        for relative_path in [*entry.source_paths, *entry.companion_paths]:
            source_path = _resolve_source_child(resolved_source_root, relative_path)
            target_path = destination_dir / source_path.name
            shutil.copy2(source_path, target_path)
            copied_paths.append(_repo_relative_string(target_path))
            copied_file_count += 1

        samples.append(
            RawPrepBenchmarkSampleLibraryMaterializedSample(
                mode="single_raw",
                sample_id=entry.sample_id,
                label=entry.label,
                destination_dir=_repo_relative_string(destination_dir),
                copied_paths=copied_paths,
                selection_reason=entry.selection_reason,
            )
        )

    for entry in plan.tri_raw:
        if len(entry.source_paths) != 3:
            raise ValueError(f"TriRaw sample '{entry.sample_id}' must declare exactly 3 source_paths entries.")
        destination_dir = resolved_sample_root / "tri_raw" / entry.bucket_id / entry.sample_id
        _replace_directory(destination_dir, resolved_sample_root)

        copied_paths: list[str] = []
        for relative_path in [*entry.source_paths, *entry.companion_paths]:
            source_path = _resolve_source_child(resolved_source_root, relative_path)
            target_path = destination_dir / source_path.name
            shutil.copy2(source_path, target_path)
            copied_paths.append(_repo_relative_string(target_path))
            copied_file_count += 1

        samples.append(
            RawPrepBenchmarkSampleLibraryMaterializedSample(
                mode="tri_raw",
                sample_id=entry.sample_id,
                bucket_id=entry.bucket_id,
                label=entry.label,
                destination_dir=_repo_relative_string(destination_dir),
                copied_paths=copied_paths,
                selection_reason=entry.selection_reason,
            )
        )

    summary = "Curated benchmark samples were copied into the local benchmark sample library without modifying the source DCIM tree."
    return RawPrepBenchmarkSampleLibraryMaterialization(
        source_root=str(resolved_source_root),
        plan_path=str(resolved_plan_path),
        benchmark_sample_root=str(resolved_sample_root),
        plan_version=plan.plan_version,
        single_raw_count=len(plan.single_raw),
        tri_raw_count=len(plan.tri_raw),
        copied_file_count=copied_file_count,
        samples=samples,
        summary=summary,
    )


def sync_rawprep_benchmark_sample_library(
    request: RawPrepBenchmarkSampleLibrarySyncRequest,
) -> RawPrepBenchmarkSampleLibrarySync:
    materialization = materialize_rawprep_benchmark_sample_library(
        source_root=request.source_root,
        plan_path=request.plan_path,
        benchmark_sample_root=request.benchmark_sample_root,
    )
    sample_root = _resolve_repo_path(request.benchmark_sample_root)

    single_raw_scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="single_raw",
            source_root=str(sample_root / "single_raw"),
            output_root=request.output_root,
            manifest_merge_mode=request.manifest_merge_mode,
            write_manifest=request.write_manifest,
            write_result_stubs=request.write_result_stubs,
        )
    )
    tri_raw_scaffold = build_rawprep_benchmark_scaffold(
        RawPrepBenchmarkScaffoldRequest(
            mode="tri_raw",
            source_root=str(sample_root / "tri_raw"),
            output_root=request.output_root,
            manifest_merge_mode=request.manifest_merge_mode,
            write_manifest=request.write_manifest,
            write_result_stubs=request.write_result_stubs,
        )
    )

    summary = "Curated benchmark samples were synchronized into the local sample library and official manifests/result stubs were refreshed."
    return RawPrepBenchmarkSampleLibrarySync(
        materialization=materialization,
        single_raw_scaffold=single_raw_scaffold,
        tri_raw_scaffold=tri_raw_scaffold,
        summary=summary,
    )
