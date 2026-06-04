from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .rawprep_benchmark_service import (
    RawPrepBenchmarkFoundationIssue,
    load_benchmark_catalog,
)
from .studio_paths import repo_root, resolve_output_root


RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".erf",
    ".kdc",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".sr2",
    ".srf",
    ".x3f",
}


class RawPrepBenchmarkScaffoldRequest(BaseModel):
    mode: Literal["single_raw", "tri_raw"]
    source_root: str
    output_root: str = "outputs"
    manifest_path: str | None = None
    result_root: str | None = None
    manifest_merge_mode: Literal["replace", "merge_preserve_existing"] = "replace"
    write_manifest: bool = False
    write_result_stubs: bool = False


class RawPrepBenchmarkScaffoldSample(BaseModel):
    sample_id: str
    bucket_id: str | None = None
    raw_path: str | None = None
    source_paths: list[str] = Field(default_factory=list)
    benchmark_result_path: str


class RawPrepBenchmarkScaffold(BaseModel):
    mode: str
    source_root: str
    manifest_path: str
    result_root: str
    manifest_merge_mode: str = "replace"
    wrote_manifest: bool = False
    wrote_result_stubs: bool = False
    sample_count: int = 0
    existing_sample_count: int = 0
    added_sample_count: int = 0
    merged_sample_count: int = 0
    preserved_existing_sample_count: int = 0
    removed_sample_count: int = 0
    preserved_result_path_sample_ids: list[str] = Field(default_factory=list)
    bucket_ids: list[str] = Field(default_factory=list)
    populated_bucket_ids: list[str] = Field(default_factory=list)
    missing_bucket_ids: list[str] = Field(default_factory=list)
    result_stub_paths: list[str] = Field(default_factory=list)
    samples: list[RawPrepBenchmarkScaffoldSample] = Field(default_factory=list)
    issues: list[RawPrepBenchmarkFoundationIssue] = Field(default_factory=list)
    manifest_payload: dict[str, Any] = Field(default_factory=dict)
    summary: str


def _is_raw_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in RAW_EXTENSIONS


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_input_directory(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (repo_root() / path).resolve()
    else:
        path = path.resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Benchmark scaffold source_root was not found or is not a directory: {path}")
    return path


def _resolve_manifest_path(mode: str, requested_path: str | None) -> Path:
    if requested_path:
        path = Path(requested_path)
        return path.resolve() if path.is_absolute() else (repo_root() / path).resolve()
    foundation = repo_root() / "benchmark"
    if not foundation.exists():
        foundation = repo_root() / "PROJECT_FOUNDATION"
    if mode == "single_raw":
        return (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").resolve()
    return (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").resolve()


def _load_optional_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Benchmark scaffold manifest must be a JSON object: {path}")
    return payload


def _sample_entries(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    samples = payload.get("samples", [])
    if not isinstance(samples, list):
        return []
    return [entry for entry in samples if isinstance(entry, dict)]


def _resolve_result_root(request: RawPrepBenchmarkScaffoldRequest) -> Path:
    if request.result_root:
        path = Path(request.result_root)
        return path.resolve() if path.is_absolute() else (repo_root() / path).resolve()
    return (resolve_output_root(request.output_root) / "_benchmark_results_staging" / request.mode).resolve()


def _issue(
    *,
    severity: str,
    code: str,
    scope: str,
    message: str,
    sample_id: str | None = None,
    bucket_id: str | None = None,
    path: str | None = None,
) -> RawPrepBenchmarkFoundationIssue:
    return RawPrepBenchmarkFoundationIssue(
        severity=severity,
        code=code,
        scope=scope,
        message=message,
        sample_id=sample_id,
        bucket_id=bucket_id,
        path=path,
    )


def _single_raw_entries(
    source_root: Path,
    result_root: Path,
) -> tuple[list[RawPrepBenchmarkScaffoldSample], list[RawPrepBenchmarkFoundationIssue]]:
    samples: list[RawPrepBenchmarkScaffoldSample] = []
    issues: list[RawPrepBenchmarkFoundationIssue] = []
    seen_ids: set[str] = set()

    direct_raw_files = sorted(path for path in source_root.iterdir() if _is_raw_file(path))
    for raw_path in direct_raw_files:
        sample_id = raw_path.stem
        if sample_id in seen_ids:
            issues.append(
                _issue(
                    severity="error",
                    code="single_raw_duplicate_sample_id",
                    scope="single_raw",
                    message="Derived sample_id collides with another SingleRaw sample.",
                    sample_id=sample_id,
                    path=str(raw_path),
                )
            )
            continue
        seen_ids.add(sample_id)
        result_path = result_root / f"{sample_id}.json"
        samples.append(
            RawPrepBenchmarkScaffoldSample(
                sample_id=sample_id,
                raw_path=_repo_relative_string(raw_path),
                benchmark_result_path=_repo_relative_string(result_path),
            )
        )

    for sample_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        raw_files = sorted(path for path in sample_dir.rglob("*") if _is_raw_file(path))
        if not raw_files:
            continue
        if len(raw_files) != 1:
            issues.append(
                _issue(
                    severity="error",
                    code="single_raw_sample_dir_invalid",
                    scope="single_raw",
                    message="SingleRaw sample directory must contain exactly 1 RAW file.",
                    sample_id=sample_dir.name,
                    path=str(sample_dir),
                )
            )
            continue
        sample_id = sample_dir.name
        if sample_id in seen_ids:
            issues.append(
                _issue(
                    severity="error",
                    code="single_raw_duplicate_sample_id",
                    scope="single_raw",
                    message="Derived sample_id collides with another SingleRaw sample.",
                    sample_id=sample_id,
                    path=str(sample_dir),
                )
            )
            continue
        seen_ids.add(sample_id)
        result_path = result_root / f"{sample_id}.json"
        samples.append(
            RawPrepBenchmarkScaffoldSample(
                sample_id=sample_id,
                raw_path=_repo_relative_string(raw_files[0]),
                benchmark_result_path=_repo_relative_string(result_path),
            )
        )

    return samples, issues


def _tri_raw_entries(
    source_root: Path,
    result_root: Path,
) -> tuple[list[RawPrepBenchmarkScaffoldSample], list[RawPrepBenchmarkFoundationIssue], list[str], list[str], list[str]]:
    catalog = load_benchmark_catalog()
    bucket_ids = [
        str(entry.get("bucket_id") or "")
        for entry in catalog.get("tri_raw", {}).get("bucket_definitions", [])
        if isinstance(entry, dict) and str(entry.get("bucket_id") or "")
    ]
    samples: list[RawPrepBenchmarkScaffoldSample] = []
    issues: list[RawPrepBenchmarkFoundationIssue] = []
    populated_bucket_ids: list[str] = []
    missing_bucket_ids: list[str] = []
    seen_ids: set[str] = set()

    for bucket_id in bucket_ids:
        bucket_root = source_root / bucket_id
        if not bucket_root.exists() or not bucket_root.is_dir():
            missing_bucket_ids.append(bucket_id)
            continue

        bucket_has_sample = False
        for sample_dir in sorted(path for path in bucket_root.iterdir() if path.is_dir()):
            raw_files = sorted(path for path in sample_dir.rglob("*") if _is_raw_file(path))
            if not raw_files:
                continue
            sample_id = f"{bucket_id}__{sample_dir.name}"
            if len(raw_files) != 3:
                issues.append(
                    _issue(
                        severity="error",
                        code="tri_raw_sample_dir_invalid",
                        scope="tri_raw",
                        message="TriRaw sample directory must contain exactly 3 RAW files.",
                        sample_id=sample_id,
                        bucket_id=bucket_id,
                        path=str(sample_dir),
                    )
                )
                continue
            if sample_id in seen_ids:
                issues.append(
                    _issue(
                        severity="error",
                        code="tri_raw_duplicate_sample_id",
                        scope="tri_raw",
                        message="Derived sample_id collides with another TriRaw sample.",
                        sample_id=sample_id,
                        bucket_id=bucket_id,
                        path=str(sample_dir),
                    )
                )
                continue
            seen_ids.add(sample_id)
            result_path = result_root / bucket_id / f"{sample_id}.json"
            samples.append(
                RawPrepBenchmarkScaffoldSample(
                    sample_id=sample_id,
                    bucket_id=bucket_id,
                    source_paths=[_repo_relative_string(path) for path in raw_files],
                    benchmark_result_path=_repo_relative_string(result_path),
                )
            )
            bucket_has_sample = True
        if bucket_has_sample:
            populated_bucket_ids.append(bucket_id)
        else:
            missing_bucket_ids.append(bucket_id)

    return samples, issues, bucket_ids, populated_bucket_ids, missing_bucket_ids


def _result_stub_payload(sample: RawPrepBenchmarkScaffoldSample) -> dict[str, Any]:
    payload = {
        "sample_id": sample.sample_id,
        "status": "pending_measurement",
        "timing_ms": None,
        "metrics": {},
        "notes": ["Populate measured benchmark values before promoting this sample to measured evidence."],
    }
    if sample.bucket_id:
        payload["bucket_id"] = sample.bucket_id
        payload["fallback_mode"] = None
    return payload


def _manifest_entry_from_sample(
    sample: RawPrepBenchmarkScaffoldSample,
    *,
    mode: Literal["single_raw", "tri_raw"],
) -> dict[str, Any]:
    if mode == "single_raw":
        return {
            "sample_id": sample.sample_id,
            "raw_path": sample.raw_path,
            "benchmark_result_path": sample.benchmark_result_path,
        }
    return {
        "sample_id": sample.sample_id,
        "bucket_id": sample.bucket_id,
        "source_paths": sample.source_paths,
        "benchmark_result_path": sample.benchmark_result_path,
    }


def _entry_sample_id(entry: dict[str, Any]) -> str:
    return str(entry.get("sample_id") or "").strip()


def _merge_manifest_payload(
    *,
    mode: Literal["single_raw", "tri_raw"],
    discovered_entries: list[dict[str, Any]],
    existing_payload: dict[str, Any] | None,
    merge_mode: Literal["replace", "merge_preserve_existing"],
) -> tuple[dict[str, Any], int, int, int, int, int, list[str]]:
    existing_entries = _sample_entries(existing_payload)
    existing_sample_count = len(existing_entries)
    preserved_result_path_sample_ids: list[str] = []

    if merge_mode == "replace":
        existing_ids = {_entry_sample_id(entry) for entry in existing_entries if _entry_sample_id(entry)}
        discovered_ids = {_entry_sample_id(entry) for entry in discovered_entries if _entry_sample_id(entry)}
        added_sample_count = sum(1 for sample_id in discovered_ids if sample_id not in existing_ids)
        merged_sample_count = sum(1 for sample_id in discovered_ids if sample_id in existing_ids)
        removed_sample_count = sum(1 for sample_id in existing_ids if sample_id and sample_id not in discovered_ids)
        return (
            {
                "manifest_version": datetime.now(timezone.utc).date().isoformat(),
                "status": "partially_populated" if discovered_entries else "unpopulated",
                "samples": discovered_entries,
            },
            existing_sample_count,
            added_sample_count,
            merged_sample_count,
            0,
            removed_sample_count,
            preserved_result_path_sample_ids,
        )

    final_entries: list[dict[str, Any]] = []
    matched_existing_indices: set[int] = set()
    added_sample_count = 0
    merged_sample_count = 0

    for discovered_entry in discovered_entries:
        sample_id = _entry_sample_id(discovered_entry)
        match_index: int | None = None
        for index, existing_entry in enumerate(existing_entries):
            if index in matched_existing_indices:
                continue
            if _entry_sample_id(existing_entry) == sample_id:
                match_index = index
                break

        if match_index is None:
            final_entries.append(discovered_entry)
            added_sample_count += 1
            continue

        matched_existing_indices.add(match_index)
        existing_entry = existing_entries[match_index]
        merged_entry = dict(existing_entry)
        for key, value in discovered_entry.items():
            if key == "benchmark_result_path" and str(existing_entry.get(key) or "").strip():
                if sample_id:
                    preserved_result_path_sample_ids.append(sample_id)
                continue
            merged_entry[key] = value
        final_entries.append(merged_entry)
        merged_sample_count += 1

    preserved_existing_entries = [
        dict(entry)
        for index, entry in enumerate(existing_entries)
        if index not in matched_existing_indices
    ]
    final_entries.extend(preserved_existing_entries)
    preserved_existing_sample_count = len(preserved_existing_entries)

    return (
        {
            "manifest_version": datetime.now(timezone.utc).date().isoformat(),
            "status": "partially_populated" if final_entries else "unpopulated",
            "samples": final_entries,
        },
        existing_sample_count,
        added_sample_count,
        merged_sample_count,
        preserved_existing_sample_count,
        0,
        preserved_result_path_sample_ids,
    )


def build_rawprep_benchmark_scaffold(request: RawPrepBenchmarkScaffoldRequest) -> RawPrepBenchmarkScaffold:
    source_root = _resolve_input_directory(request.source_root)
    manifest_path = _resolve_manifest_path(request.mode, request.manifest_path)
    result_root = _resolve_result_root(request)

    if request.mode == "single_raw":
        samples, issues = _single_raw_entries(source_root, result_root)
        bucket_ids: list[str] = []
        populated_bucket_ids: list[str] = []
        missing_bucket_ids: list[str] = []
    else:
        samples, issues, bucket_ids, populated_bucket_ids, missing_bucket_ids = _tri_raw_entries(source_root, result_root)

    discovered_entries = [
        _manifest_entry_from_sample(sample, mode=request.mode)
        for sample in samples
    ]
    existing_payload = _load_optional_manifest(manifest_path) if manifest_path.exists() else None
    (
        manifest_payload,
        existing_sample_count,
        added_sample_count,
        merged_sample_count,
        preserved_existing_sample_count,
        removed_sample_count,
        preserved_result_path_sample_ids,
    ) = _merge_manifest_payload(
        mode=request.mode,
        discovered_entries=discovered_entries,
        existing_payload=existing_payload,
        merge_mode=request.manifest_merge_mode,
    )

    result_stub_paths: list[str] = []
    wrote_manifest = False
    wrote_result_stubs = False
    if request.write_manifest:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        wrote_manifest = True
    if request.write_result_stubs:
        for sample in samples:
            result_path = repo_root() / sample.benchmark_result_path
            result_path.parent.mkdir(parents=True, exist_ok=True)
            if not result_path.exists():
                result_path.write_text(
                    json.dumps(_result_stub_payload(sample), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            result_stub_paths.append(str(result_path.resolve()))
        wrote_result_stubs = True

    error_count = sum(1 for issue in issues if issue.severity == "error")
    if error_count > 0:
        summary = "Benchmark scaffold found source-structure issues that should be fixed before manifest population."
    elif not samples:
        summary = "Benchmark scaffold found no valid samples yet."
    elif request.mode == "tri_raw" and missing_bucket_ids:
        summary = "TriRaw scaffold populated some buckets, but benchmark coverage is still incomplete."
    elif request.manifest_merge_mode == "merge_preserve_existing" and preserved_existing_sample_count > 0:
        summary = "Benchmark scaffold merged discovered samples into the official manifest while preserving existing entries."
    else:
        summary = "Benchmark scaffold produced manifest-ready sample entries."

    return RawPrepBenchmarkScaffold(
        mode=request.mode,
        source_root=str(source_root),
        manifest_path=str(manifest_path),
        result_root=str(result_root),
        manifest_merge_mode=request.manifest_merge_mode,
        wrote_manifest=wrote_manifest,
        wrote_result_stubs=wrote_result_stubs,
        sample_count=len(samples),
        existing_sample_count=existing_sample_count,
        added_sample_count=added_sample_count,
        merged_sample_count=merged_sample_count,
        preserved_existing_sample_count=preserved_existing_sample_count,
        removed_sample_count=removed_sample_count,
        preserved_result_path_sample_ids=preserved_result_path_sample_ids,
        bucket_ids=bucket_ids,
        populated_bucket_ids=populated_bucket_ids,
        missing_bucket_ids=missing_bucket_ids,
        result_stub_paths=result_stub_paths,
        samples=samples,
        issues=issues,
        manifest_payload=manifest_payload,
        summary=summary,
    )
