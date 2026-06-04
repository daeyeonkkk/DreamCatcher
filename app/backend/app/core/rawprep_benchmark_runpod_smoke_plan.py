from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .rawprep_benchmark_service import _load_optional_manifest, _sample_entries
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkRunPodSmokePlanRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    manifest_path: str | None = None
    sample_id: str | None = None
    sample_working_root: str = "outputs/_single_raw_healthcheck"
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json"


class RawPrepBenchmarkRunPodSmokePlan(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_sample"
    summary: str
    plan_path: str | None = None
    manifest_path: str
    selected_sample_id: str | None = None
    benchmark_result_path: str | None = None
    repo_sample_raw_path: str | None = None
    runpod_sample_raw_path: str | None = None
    sample_exists: bool = False
    recommended_sample_working_root: str | None = None
    recommended_runtime_output_path: str | None = None
    expected_artifacts: list[str] = Field(default_factory=list)
    command_preview: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("RunPod smoke plan output_dir must stay inside the configured output root.") from exc
    return resolved


def _plan_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_runpod_smoke_plan.json"


def _resolve_manifest_path(path_value: str | None) -> Path:
    root = repo_root().resolve()
    if path_value:
        candidate = Path(path_value)
        return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    return (root / "benchmark" / "SINGLE_RAW_GOLD_SET_MANIFEST.json").resolve()


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _runpod_workspace_path(path_value: str) -> str:
    normalized = path_value.replace("\\", "/").lstrip("/")
    return f"/workspace/DreamCatcher/{normalized}"


def _resolve_sample_entry(payload: dict, *, requested_sample_id: str | None) -> dict | None:
    entries = [entry for entry in _sample_entries(payload) if isinstance(entry, dict)]
    if requested_sample_id:
        requested = requested_sample_id.strip()
        for entry in entries:
            if str(entry.get("sample_id") or "").strip() == requested:
                return entry
        return None

    for entry in entries:
        raw_path_value = str(entry.get("raw_path") or "").strip()
        if not raw_path_value:
            continue
        candidate = (repo_root() / raw_path_value).resolve()
        if candidate.exists() and candidate.is_file():
            return entry
    return entries[0] if entries else None


def build_rawprep_benchmark_runpod_smoke_plan(
    request: RawPrepBenchmarkRunPodSmokePlanRequest,
) -> RawPrepBenchmarkRunPodSmokePlan:
    manifest_path = _resolve_manifest_path(request.manifest_path)
    payload = _load_optional_manifest(manifest_path)
    if payload is None:
        raise FileNotFoundError(f"SingleRaw benchmark manifest was not found: {manifest_path}")

    selected_entry = _resolve_sample_entry(payload, requested_sample_id=request.sample_id)
    if selected_entry is None:
        summary = "RunPod smoke plan could not select a canonical SingleRaw sample because the manifest has no usable entries."
        return RawPrepBenchmarkRunPodSmokePlan(
            output_dir=request.output_dir,
            output_root=request.output_root,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="missing_sample",
            summary=summary,
            plan_path=str(_plan_path(request.output_dir, output_root=request.output_root)),
            manifest_path=str(manifest_path),
            recommended_actions=[
                "Populate SINGLE_RAW_GOLD_SET_MANIFEST.json with at least one accessible SingleRaw sample before preparing RunPod smoke."
            ],
        )

    sample_id = str(selected_entry.get("sample_id") or "").strip() or None
    raw_path_value = str(selected_entry.get("raw_path") or "").strip()
    benchmark_result_path = str(selected_entry.get("benchmark_result_path") or "").strip() or None

    sample_path = (repo_root() / raw_path_value).resolve() if raw_path_value else None
    repo_sample_raw_path = _repo_relative_string(sample_path) if sample_path is not None else None
    sample_exists = bool(sample_path and sample_path.exists() and sample_path.is_file())
    runpod_sample_raw_path = _runpod_workspace_path(repo_sample_raw_path) if repo_sample_raw_path else None
    recommended_sample_working_root = _runpod_workspace_path(request.sample_working_root)
    recommended_runtime_output_path = _runpod_workspace_path(request.runtime_output_path)

    command_preview = None
    status = "missing_sample"
    summary = "RunPod smoke plan is missing a usable SingleRaw sample."
    recommended_actions: list[str] = []
    if sample_exists and sample_id and runpod_sample_raw_path:
        status = "ready"
        summary = "RunPod smoke plan selected a canonical SingleRaw sample and the expected sample-decode command."
        command_preview = (
            "cd /workspace/DreamCatcher/app\n"
            "PYTHONPATH=/workspace/DreamCatcher/app/backend python3 scripts/single_raw_healthcheck.py "
            f"--sample-raw {runpod_sample_raw_path} "
            f"--sample-working-root {recommended_sample_working_root} "
            f"--out {recommended_runtime_output_path}"
        )
        recommended_actions.append(
            "Run the command on RunPod after bootstrap so single_raw_healthcheck.json includes sample RAW decode evidence."
        )
        recommended_actions.append(
            "After the sample decode smoke passes, run benchmark_runpod_smoke.py with --write-canonical in the same measured output dir."
        )
    else:
        recommended_actions.append(
            "Sync benchmark/samples from the read-only photo source and ensure the selected SingleRaw sample exists before preparing RunPod smoke."
        )

    return RawPrepBenchmarkRunPodSmokePlan(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        plan_path=str(_plan_path(request.output_dir, output_root=request.output_root)),
        manifest_path=str(manifest_path),
        selected_sample_id=sample_id,
        benchmark_result_path=benchmark_result_path,
        repo_sample_raw_path=repo_sample_raw_path,
        runpod_sample_raw_path=runpod_sample_raw_path,
        sample_exists=sample_exists,
        recommended_sample_working_root=recommended_sample_working_root,
        recommended_runtime_output_path=recommended_runtime_output_path,
        expected_artifacts=[
            "app/runtime/single_raw_healthcheck.json",
            "preview.jpg",
            "scene_linear.tiff",
            "noise_map.png",
            "lowlight_recovery_map.png",
        ],
        command_preview=command_preview,
        recommended_actions=recommended_actions,
    )


def write_rawprep_benchmark_runpod_smoke_plan(
    request: RawPrepBenchmarkRunPodSmokePlanRequest,
) -> RawPrepBenchmarkRunPodSmokePlan:
    plan = build_rawprep_benchmark_runpod_smoke_plan(request)
    path = _plan_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def load_rawprep_benchmark_runpod_smoke_plan(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkRunPodSmokePlan:
    path = _plan_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark RunPod smoke plan artifact was not found: {path}")
    return RawPrepBenchmarkRunPodSmokePlan(**json.loads(path.read_text(encoding="utf-8")))
