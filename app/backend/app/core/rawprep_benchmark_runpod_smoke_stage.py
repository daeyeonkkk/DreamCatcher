from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, Field

from .rawprep_benchmark_runpod_smoke_plan import (
    RawPrepBenchmarkRunPodSmokePlan,
    RawPrepBenchmarkRunPodSmokePlanRequest,
    build_rawprep_benchmark_runpod_smoke_plan,
    write_rawprep_benchmark_runpod_smoke_plan,
)
from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkRunPodSmokeStageRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    manifest_path: str | None = None
    sample_id: str | None = None
    sample_working_root: str = "outputs/_single_raw_healthcheck"
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json"
    write_archive: bool = True


class RawPrepBenchmarkRunPodSmokeStage(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_sample"
    summary: str
    stage_record_path: str | None = None
    plan_path: str | None = None
    stage_root_path: str | None = None
    archive_path: str | None = None
    archive_created: bool = False
    manifest_path: str | None = None
    selected_sample_id: str | None = None
    repo_sample_raw_path: str | None = None
    staged_sample_raw_path: str | None = None
    runpod_sample_raw_path: str | None = None
    sample_exists: bool = False
    bundle_file_name: str = "rawprep_runpod_smoke_sample_bundle.zip"
    runpod_extract_root: str = "/workspace/DreamCatcher"
    runpod_extract_command: str | None = None
    command_preview: str | None = None
    bundle_relative_paths: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _runpod_python_extract_command(*, archive_path: str, target_dir: str) -> str:
    return "\n".join(
        [
            "python3 - <<'PY'",
            "from pathlib import Path",
            "import zipfile",
            f"archive = Path(r'{archive_path}')",
            f"target = Path(r'{target_dir}')",
            "target.mkdir(parents=True, exist_ok=True)",
            "with zipfile.ZipFile(archive, 'r') as zf:",
            "    zf.extractall(target)",
            "PY",
        ]
    )


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("RunPod smoke stage output_dir must stay inside the configured output root.") from exc
    return resolved


def _stage_record_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_runpod_smoke_stage.json"


def _stage_root_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "_runpod_smoke_sample_bundle"


def _stage_archive_path(output_dir: str, *, output_root: str, bundle_file_name: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / bundle_file_name


def _plan_request_from_stage_request(
    request: RawPrepBenchmarkRunPodSmokeStageRequest,
) -> RawPrepBenchmarkRunPodSmokePlanRequest:
    return RawPrepBenchmarkRunPodSmokePlanRequest(
        output_dir=request.output_dir,
        output_root=request.output_root,
        manifest_path=request.manifest_path,
        sample_id=request.sample_id,
        sample_working_root=request.sample_working_root,
        runtime_output_path=request.runtime_output_path,
    )


def _sample_source_path(plan: RawPrepBenchmarkRunPodSmokePlan) -> Path | None:
    raw_path_value = str(plan.repo_sample_raw_path or "").strip()
    if not raw_path_value:
        return None
    candidate = Path(raw_path_value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root() / candidate).resolve()


def _stage_relative_paths(plan: RawPrepBenchmarkRunPodSmokePlan) -> list[str]:
    raw_path_value = str(plan.repo_sample_raw_path or "").replace("\\", "/").strip().lstrip("/")
    return [raw_path_value] if raw_path_value else []


def _build_stage_from_plan(
    plan: RawPrepBenchmarkRunPodSmokePlan,
    *,
    request: RawPrepBenchmarkRunPodSmokeStageRequest,
    stage_created: bool,
    archive_created: bool,
) -> RawPrepBenchmarkRunPodSmokeStage:
    bundle_relative_paths = _stage_relative_paths(plan)
    stage_root = _stage_root_path(request.output_dir, output_root=request.output_root)
    archive_path = _stage_archive_path(
        request.output_dir,
        output_root=request.output_root,
        bundle_file_name="rawprep_runpod_smoke_sample_bundle.zip",
    )
    staged_sample_raw_path = (
        str((stage_root / bundle_relative_paths[0]).resolve()) if stage_created and bundle_relative_paths else None
    )
    recommended_actions = list(plan.recommended_actions)
    runpod_extract_command = None
    summary = "RunPod smoke sample bundle is waiting for a usable canonical SingleRaw sample."

    if plan.status == "ready" and bundle_relative_paths:
        runpod_extract_command = (
            _runpod_python_extract_command(
                archive_path=f"/workspace/{archive_path.name}",
                target_dir="/workspace/DreamCatcher",
            )
            if request.write_archive
            else "Copy the staged benchmark/samples tree into /workspace/DreamCatcher before running the smoke plan."
        )
        recommended_actions.extend(
            [
                "Keep this bundle separate from DreamCatcher.zip; it is a zip-excluded smoke-input artifact, not the official app build.",
                f"Upload {archive_path.name} to /workspace on RunPod alongside DreamCatcher.zip.",
                "Extract the smoke-input bundle into /workspace/DreamCatcher before generating the RunPod smoke plan and running single_raw_healthcheck.py.",
            ]
        )
        if stage_created and archive_created:
            summary = "RunPod smoke sample bundle mirrored the canonical SingleRaw sample and created an upload-ready zip."
        elif stage_created:
            summary = "RunPod smoke sample bundle mirrored the canonical SingleRaw sample into a local staging tree."
        else:
            summary = "RunPod smoke sample bundle can mirror the canonical SingleRaw sample into a zip-excluded upload bundle."

    return RawPrepBenchmarkRunPodSmokeStage(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=plan.status,
        summary=summary,
        stage_record_path=str(_stage_record_path(request.output_dir, output_root=request.output_root)),
        plan_path=plan.plan_path,
        stage_root_path=str(stage_root),
        archive_path=str(archive_path),
        archive_created=archive_created,
        manifest_path=plan.manifest_path,
        selected_sample_id=plan.selected_sample_id,
        repo_sample_raw_path=plan.repo_sample_raw_path,
        staged_sample_raw_path=staged_sample_raw_path,
        runpod_sample_raw_path=plan.runpod_sample_raw_path,
        sample_exists=plan.sample_exists,
        runpod_extract_command=runpod_extract_command,
        command_preview=plan.command_preview,
        bundle_relative_paths=bundle_relative_paths,
        recommended_actions=recommended_actions,
    )


def build_rawprep_benchmark_runpod_smoke_stage(
    request: RawPrepBenchmarkRunPodSmokeStageRequest,
) -> RawPrepBenchmarkRunPodSmokeStage:
    plan = build_rawprep_benchmark_runpod_smoke_plan(_plan_request_from_stage_request(request))
    return _build_stage_from_plan(plan, request=request, stage_created=False, archive_created=False)


def _write_stage_tree(plan: RawPrepBenchmarkRunPodSmokePlan, *, request: RawPrepBenchmarkRunPodSmokeStageRequest) -> Path:
    stage_root = _stage_root_path(request.output_dir, output_root=request.output_root)
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    for relative_path in _stage_relative_paths(plan):
        source_path = _sample_source_path(plan)
        if source_path is None or not source_path.exists():
            raise FileNotFoundError("RunPod smoke stage could not locate the canonical sample RAW on disk.")
        staged_path = stage_root / relative_path
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, staged_path)

    return stage_root


def _write_stage_archive(stage_root: Path, *, output_dir: str, output_root: str, bundle_file_name: str) -> Path:
    archive_path = _stage_archive_path(output_dir, output_root=output_root, bundle_file_name=bundle_file_name)
    if archive_path.exists():
        archive_path.unlink()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(stage_root.rglob("*")):
            if not path.is_file():
                continue
            archive.write(path, arcname=path.relative_to(stage_root).as_posix())
    return archive_path


def write_rawprep_benchmark_runpod_smoke_stage(
    request: RawPrepBenchmarkRunPodSmokeStageRequest,
) -> RawPrepBenchmarkRunPodSmokeStage:
    plan = write_rawprep_benchmark_runpod_smoke_plan(_plan_request_from_stage_request(request))
    stage_root = _stage_root_path(request.output_dir, output_root=request.output_root)
    archive_path = _stage_archive_path(
        request.output_dir,
        output_root=request.output_root,
        bundle_file_name="rawprep_runpod_smoke_sample_bundle.zip",
    )
    if stage_root.exists():
        shutil.rmtree(stage_root)
    if archive_path.exists():
        archive_path.unlink()

    stage_created = False
    archive_created = False

    if plan.status == "ready" and plan.sample_exists:
        stage_root = _write_stage_tree(plan, request=request)
        stage_created = stage_root.exists()
        if request.write_archive:
            archive_path = _write_stage_archive(
                stage_root,
                output_dir=request.output_dir,
                output_root=request.output_root,
                bundle_file_name="rawprep_runpod_smoke_sample_bundle.zip",
            )
            archive_created = archive_path.exists()

    stage = _build_stage_from_plan(plan, request=request, stage_created=stage_created, archive_created=archive_created)
    record_path = _stage_record_path(request.output_dir, output_root=request.output_root)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(stage.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return stage


def load_rawprep_benchmark_runpod_smoke_stage(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkRunPodSmokeStage:
    path = _stage_record_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark RunPod smoke stage artifact was not found: {path}")
    return RawPrepBenchmarkRunPodSmokeStage(**json.loads(path.read_text(encoding="utf-8")))
