from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from pydantic import BaseModel, Field

from .rawprep_benchmark_runpod_smoke_stage import (
    RawPrepBenchmarkRunPodSmokeStage,
    RawPrepBenchmarkRunPodSmokeStageRequest,
    build_rawprep_benchmark_runpod_smoke_stage,
    write_rawprep_benchmark_runpod_smoke_stage,
)
from .studio_paths import repo_root, resolve_output_root

EMBEDDED_SMOKE_BUNDLE_RELATIVE_PATH = "runpod_inputs/rawprep_runpod_smoke_sample_bundle.zip"


class RawPrepBenchmarkRunPodSmokeHandoffRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    manifest_path: str | None = None
    sample_id: str | None = None
    sample_working_root: str = "outputs/_single_raw_healthcheck"
    runtime_output_path: str = "app/runtime/single_raw_healthcheck.json"
    release_bundle_path: str | None = None


class RawPrepBenchmarkRunPodSmokeHandoffUpload(BaseModel):
    local_path: str
    runpod_path: str
    required: bool = True
    purpose: str


class RawPrepBenchmarkRunPodSmokeHandoff(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_app_bundle"
    summary: str
    handoff_path: str | None = None
    runbook_markdown_path: str | None = None
    runbook_script_path: str | None = None
    stage_record_path: str | None = None
    plan_path: str | None = None
    release_bundle_manifest_path: str | None = None
    official_app_bundle_path: str | None = None
    official_app_bundle_name: str = "DreamCatcher.zip"
    official_app_bundle_exists: bool = False
    smoke_bundle_path: str | None = None
    smoke_bundle_exists: bool = False
    embedded_smoke_bundle_relative_path: str = EMBEDDED_SMOKE_BUNDLE_RELATIVE_PATH
    embedded_smoke_bundle_exists: bool = False
    selected_sample_id: str | None = None
    runpod_app_root: str = "/workspace/DreamCatcher"
    runpod_workspace_root: str = "/workspace"
    uploads: list[RawPrepBenchmarkRunPodSmokeHandoffUpload] = Field(default_factory=list)
    local_prepare_commands: list[str] = Field(default_factory=list)
    runpod_prepare_commands: list[str] = Field(default_factory=list)
    runpod_health_commands: list[str] = Field(default_factory=list)
    runpod_smoke_commands: list[str] = Field(default_factory=list)
    expected_runpod_artifacts: list[str] = Field(default_factory=list)
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


def _handoff_path(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("RunPod smoke handoff output_dir must stay inside the configured output root.") from exc
    return resolved / "rawprep_runpod_smoke_handoff.json"


def _release_bundle_manifest_path() -> Path:
    return (repo_root() / "runpod" / "release_bundle_manifest.json").resolve()


def _runbook_markdown_path(output_dir: str, *, output_root: str) -> Path:
    return _handoff_path(output_dir, output_root=output_root).with_name("rawprep_runpod_smoke_handoff.md")


def _runbook_script_path(output_dir: str, *, output_root: str) -> Path:
    return _handoff_path(output_dir, output_root=output_root).with_name("rawprep_runpod_smoke_handoff.sh")


def _load_release_bundle_name() -> str:
    manifest_path = _release_bundle_manifest_path()
    if not manifest_path.exists():
        return "DreamCatcher.zip"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_name = str(payload.get("official_artifact_name") or "").strip()
    return artifact_name or "DreamCatcher.zip"


def _load_release_bundle_root() -> str:
    manifest_path = _release_bundle_manifest_path()
    if not manifest_path.exists():
        return "DreamCatcher"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_root = str(payload.get("bundle_root") or "").strip()
    return bundle_root or "DreamCatcher"


def _resolve_release_bundle_path(value: str | None, *, artifact_name: str) -> Path:
    if value:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    return (repo_root() / artifact_name).resolve()


def _embedded_smoke_bundle_entry_name(*, bundle_root: str) -> str:
    return f"{bundle_root}/{EMBEDDED_SMOKE_BUNDLE_RELATIVE_PATH}"


def _bundle_contains_entry(bundle_path: Path, *, entry_name: str) -> bool:
    if not bundle_path.exists() or not bundle_path.is_file():
        return False
    try:
        with ZipFile(bundle_path) as archive:
            return entry_name in archive.namelist()
    except BadZipFile:
        return False


def _embed_smoke_bundle_into_app_bundle(
    bundle_path: Path,
    smoke_bundle_path: Path,
    *,
    bundle_root: str,
) -> bool:
    if not bundle_path.exists() or not bundle_path.is_file():
        return False
    if not smoke_bundle_path.exists() or not smoke_bundle_path.is_file():
        return False

    entry_name = _embedded_smoke_bundle_entry_name(bundle_root=bundle_root)
    entry_bytes = smoke_bundle_path.read_bytes()
    existing_bytes: bytes | None = None
    if _bundle_contains_entry(bundle_path, entry_name=entry_name):
        with ZipFile(bundle_path) as archive:
            existing_bytes = archive.read(entry_name)
        if existing_bytes == entry_bytes:
            return True

        temp_path = bundle_path.with_suffix(bundle_path.suffix + ".tmp")
        with ZipFile(bundle_path) as source_archive, ZipFile(
            temp_path,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as rebuilt_archive:
            for info in source_archive.infolist():
                if info.is_dir() or info.filename == entry_name:
                    continue
                rebuilt_archive.writestr(info, source_archive.read(info.filename))
            rebuilt_archive.writestr(entry_name, entry_bytes)
        temp_path.replace(bundle_path)
        return True

    with ZipFile(bundle_path, "a", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(entry_name, entry_bytes)
    return True


def _stage_request(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> RawPrepBenchmarkRunPodSmokeStageRequest:
    return RawPrepBenchmarkRunPodSmokeStageRequest(
        output_dir=request.output_dir,
        output_root=request.output_root,
        manifest_path=request.manifest_path,
        sample_id=request.sample_id,
        sample_working_root=request.sample_working_root,
        runtime_output_path=request.runtime_output_path,
        write_archive=True,
    )


def _local_stage_command(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> str:
    command = [
        ".\\.venv\\Scripts\\python.exe app\\scripts\\benchmark_runpod_smoke_stage.py",
        f"--output-dir {request.output_dir}",
        f"--output-root {request.output_root}",
        "--write-canonical",
    ]
    if request.manifest_path:
        command.append(f"--manifest-path {request.manifest_path}")
    if request.sample_id:
        command.append(f"--sample-id {request.sample_id}")
    if request.sample_working_root != "outputs/_single_raw_healthcheck":
        command.append(f"--sample-working-root {request.sample_working_root}")
    if request.runtime_output_path != "app/runtime/single_raw_healthcheck.json":
        command.append(f"--runtime-output-path {request.runtime_output_path}")
    return " ".join(command)


def _local_handoff_command(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> str:
    command = [
        ".\\.venv\\Scripts\\python.exe app\\scripts\\benchmark_runpod_smoke_handoff.py",
        f"--output-dir {request.output_dir}",
        f"--output-root {request.output_root}",
        "--write-canonical",
    ]
    if request.manifest_path:
        command.append(f"--manifest-path {request.manifest_path}")
    if request.sample_id:
        command.append(f"--sample-id {request.sample_id}")
    if request.sample_working_root != "outputs/_single_raw_healthcheck":
        command.append(f"--sample-working-root {request.sample_working_root}")
    if request.runtime_output_path != "app/runtime/single_raw_healthcheck.json":
        command.append(f"--runtime-output-path {request.runtime_output_path}")
    if request.release_bundle_path:
        command.append(f"--release-bundle-path {request.release_bundle_path}")
    return " ".join(command)


def _runpod_plan_command(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> str:
    args = [
        "PYTHONPATH=/workspace/DreamCatcher/app/backend python3 scripts/benchmark_runpod_smoke_plan.py",
        f"--output-dir {request.output_dir}",
        f"--output-root {request.output_root}",
        "--write-canonical",
    ]
    if request.manifest_path:
        args.append(f"--manifest-path {request.manifest_path}")
    if request.sample_id:
        args.append(f"--sample-id {request.sample_id}")
    if request.sample_working_root != "outputs/_single_raw_healthcheck":
        args.append(f"--sample-working-root {request.sample_working_root}")
    if request.runtime_output_path != "app/runtime/single_raw_healthcheck.json":
        args.append(f"--runtime-output-path {request.runtime_output_path}")
    return "cd /workspace/DreamCatcher/app\n" + " \\\n".join(args)


def _runpod_smoke_write_command(request: RawPrepBenchmarkRunPodSmokeHandoffRequest) -> str:
    return "\n".join(
        [
            "cd /workspace/DreamCatcher/app",
            "PYTHONPATH=/workspace/DreamCatcher/app/backend python3 scripts/benchmark_runpod_smoke.py \\",
            f"  --output-dir {request.output_dir} \\",
            f"  --output-root {request.output_root} \\",
            "  --write-canonical",
        ]
    )


def _build_handoff_from_stage(
    request: RawPrepBenchmarkRunPodSmokeHandoffRequest,
    *,
    stage: RawPrepBenchmarkRunPodSmokeStage,
) -> RawPrepBenchmarkRunPodSmokeHandoff:
    artifact_name = _load_release_bundle_name()
    bundle_root = _load_release_bundle_root()
    bundle_path = _resolve_release_bundle_path(request.release_bundle_path, artifact_name=artifact_name)
    bundle_exists = bundle_path.exists() and bundle_path.is_file()
    smoke_bundle_path = Path(stage.archive_path).resolve() if stage.archive_path else None
    smoke_bundle_exists = bool(smoke_bundle_path and smoke_bundle_path.exists() and smoke_bundle_path.is_file())
    embedded_smoke_bundle_exists = bundle_exists and _bundle_contains_entry(
        bundle_path,
        entry_name=_embedded_smoke_bundle_entry_name(bundle_root=bundle_root),
    )

    uploads: list[RawPrepBenchmarkRunPodSmokeHandoffUpload] = []
    if bundle_path:
        uploads.append(
            RawPrepBenchmarkRunPodSmokeHandoffUpload(
                local_path=str(bundle_path),
                runpod_path=f"/workspace/{bundle_path.name}",
                purpose="Official DreamCatcher app bundle for RunPod bootstrap. Canonical smoke sample input is embedded in this zip during handoff.",
            )
        )

    status = "ready_for_upload"
    summary = "RunPod smoke handoff is ready: upload only DreamCatcher.zip, then follow the canonical commands."
    if not bundle_exists and not smoke_bundle_exists:
        status = "missing_app_and_smoke_bundle"
        summary = "RunPod smoke handoff is missing both DreamCatcher.zip and the staged smoke sample bundle."
    elif not bundle_exists:
        status = "missing_app_bundle"
        summary = "RunPod smoke handoff is waiting for DreamCatcher.zip."
    elif stage.status != "ready" or not smoke_bundle_exists:
        status = "missing_smoke_bundle"
        summary = "RunPod smoke handoff is waiting for a usable staged smoke sample bundle."
    elif not embedded_smoke_bundle_exists:
        status = "app_bundle_embed_pending"
        summary = "RunPod smoke handoff staged the sample bundle, but DreamCatcher.zip does not yet contain the embedded smoke input."

    recommended_actions: list[str] = []
    if not bundle_exists:
        recommended_actions.append(
            "Run .\\.venv\\Scripts\\python.exe runpod\\preflight_release_bundle.py from the repo root so DreamCatcher.zip exists before upload."
        )
    if stage.status != "ready" or not smoke_bundle_exists:
        recommended_actions.append(
            "Run the canonical smoke stage step so rawprep_runpod_smoke_sample_bundle.zip is ready before moving to RunPod."
        )
    stage_handoff_overrides = (
        "Keep this bundle separate from DreamCatcher.zip",
        "Upload rawprep_runpod_smoke_sample_bundle.zip",
        "Extract the smoke-input bundle into /workspace/DreamCatcher",
    )
    recommended_actions.extend(
        action for action in stage.recommended_actions if not any(token in action for token in stage_handoff_overrides)
    )
    if bundle_exists and smoke_bundle_exists and not embedded_smoke_bundle_exists:
        recommended_actions.append(
            "Run .\\.venv\\Scripts\\python.exe app\\scripts\\benchmark_runpod_smoke_handoff.py --output-dir "
            f"{request.output_dir} --output-root {request.output_root} --write-canonical so the smoke-input bundle is embedded into DreamCatcher.zip."
        )
    if embedded_smoke_bundle_exists:
        recommended_actions.append(
            "Upload only DreamCatcher.zip to /workspace on RunPod; bootstrap will extract the embedded smoke-input bundle automatically."
        )

    return RawPrepBenchmarkRunPodSmokeHandoff(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        handoff_path=str(_handoff_path(request.output_dir, output_root=request.output_root)),
        runbook_markdown_path=str(_runbook_markdown_path(request.output_dir, output_root=request.output_root)),
        runbook_script_path=str(_runbook_script_path(request.output_dir, output_root=request.output_root)),
        stage_record_path=stage.stage_record_path,
        plan_path=stage.plan_path,
        release_bundle_manifest_path=str(_release_bundle_manifest_path()),
        official_app_bundle_path=str(bundle_path),
        official_app_bundle_name=artifact_name,
        official_app_bundle_exists=bundle_exists,
        smoke_bundle_path=str(smoke_bundle_path) if smoke_bundle_path else None,
        smoke_bundle_exists=smoke_bundle_exists,
        embedded_smoke_bundle_exists=embedded_smoke_bundle_exists,
        selected_sample_id=stage.selected_sample_id,
        uploads=uploads,
        local_prepare_commands=[
            "cd C:\\my_project\\DreamCatcher",
            _local_handoff_command(request),
        ],
        runpod_prepare_commands=[
            "cd /workspace",
            _runpod_python_extract_command(
                archive_path=f"/workspace/{artifact_name}",
                target_dir="/workspace",
            ),
            "bash /workspace/DreamCatcher/runpod/bootstrap.sh",
        ],
        runpod_health_commands=[
            "curl -s http://127.0.0.1:8188/system_stats",
            "curl -s http://127.0.0.1:8000/health",
            "curl -s http://127.0.0.1:8000/api/rawprep/health",
            "curl -s http://127.0.0.1:8000/api/studio/ops/storage-contract",
            "cat /workspace/DreamCatcher/app/runtime/bootstrap_summary.json",
            "cat /workspace/DreamCatcher/app/runtime/rawprep_healthcheck.json",
            "cat /workspace/DreamCatcher/app/runtime/single_raw_healthcheck.json",
        ],
        runpod_smoke_commands=[
            _runpod_plan_command(request),
            stage.command_preview or "Run the single_raw_healthcheck.py sample decode command from rawprep_runpod_smoke_plan.json.",
            _runpod_smoke_write_command(request),
        ],
        expected_runpod_artifacts=[
            "/workspace/DreamCatcher/app/runtime/bootstrap_summary.json",
            "/workspace/DreamCatcher/app/runtime/rawprep_healthcheck.json",
            "/workspace/DreamCatcher/app/runtime/single_raw_healthcheck.json",
            f"/workspace/DreamCatcher/{request.output_root}/{request.output_dir}/rawprep_runpod_smoke.json".replace("\\", "/"),
        ],
        recommended_actions=recommended_actions,
    )


def _render_runbook_markdown(handoff: RawPrepBenchmarkRunPodSmokeHandoff) -> str:
    uploads = "\n".join(
        f"- `{upload.local_path}` -> `{upload.runpod_path}`: {upload.purpose}" for upload in handoff.uploads
    )
    prepare = "\n\n".join(f"```bash\n{command}\n```" for command in handoff.runpod_prepare_commands)
    health = "\n\n".join(f"```bash\n{command}\n```" for command in handoff.runpod_health_commands)
    smoke = "\n\n".join(f"```bash\n{command}\n```" for command in handoff.runpod_smoke_commands)
    artifacts = "\n".join(f"- `{path}`" for path in handoff.expected_runpod_artifacts)
    actions = "\n".join(f"- {action}" for action in handoff.recommended_actions)
    return "\n".join(
        [
            "# RunPod Smoke Handoff",
            "",
            f"Generated: {handoff.generated_at}",
            "",
            f"Status: `{handoff.status}`",
            "",
            "## Uploads",
            uploads,
            "",
            "## RunPod Prepare",
            prepare,
            "",
            "## RunPod Health",
            health,
            "",
            "## RunPod Smoke",
            smoke,
            "",
            "## Expected Artifacts",
            artifacts,
            "",
            "## Recommended Actions",
            actions,
            "",
        ]
    )


def _render_runbook_script(handoff: RawPrepBenchmarkRunPodSmokeHandoff) -> str:
    sections: list[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Canonical RunPod smoke handoff for DreamCatcher",
        f"# Generated: {handoff.generated_at}",
        f"# Status at generation time: {handoff.status}",
        "",
        "# Expected uploads:",
    ]
    for upload in handoff.uploads:
        sections.append(f"# - {upload.runpod_path} ({upload.purpose})")

    sections.extend(["", "# Prepare workspace"])
    sections.extend(handoff.runpod_prepare_commands)
    sections.extend(["", "# Health checks"])
    sections.extend(handoff.runpod_health_commands)
    sections.extend(["", "# Canonical smoke"])
    sections.extend(handoff.runpod_smoke_commands)
    sections.extend(["", "# Expected artifacts after success"])
    for artifact in handoff.expected_runpod_artifacts:
        sections.append(f"# - {artifact}")
    sections.append("")
    return "\n".join(sections)


def build_rawprep_benchmark_runpod_smoke_handoff(
    request: RawPrepBenchmarkRunPodSmokeHandoffRequest,
) -> RawPrepBenchmarkRunPodSmokeHandoff:
    stage = build_rawprep_benchmark_runpod_smoke_stage(_stage_request(request))
    return _build_handoff_from_stage(request, stage=stage)


def write_rawprep_benchmark_runpod_smoke_handoff(
    request: RawPrepBenchmarkRunPodSmokeHandoffRequest,
) -> RawPrepBenchmarkRunPodSmokeHandoff:
    stage = write_rawprep_benchmark_runpod_smoke_stage(_stage_request(request))
    artifact_name = _load_release_bundle_name()
    bundle_root = _load_release_bundle_root()
    bundle_path = _resolve_release_bundle_path(request.release_bundle_path, artifact_name=artifact_name)
    smoke_bundle_path = Path(stage.archive_path).resolve() if stage.archive_path else None
    if stage.status == "ready" and smoke_bundle_path is not None:
        _embed_smoke_bundle_into_app_bundle(
            bundle_path,
            smoke_bundle_path,
            bundle_root=bundle_root,
        )
    handoff = _build_handoff_from_stage(request, stage=stage)
    path = _handoff_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = _runbook_markdown_path(request.output_dir, output_root=request.output_root)
    markdown_path.write_text(_render_runbook_markdown(handoff), encoding="utf-8")
    script_path = _runbook_script_path(request.output_dir, output_root=request.output_root)
    script_path.write_text(_render_runbook_script(handoff), encoding="utf-8")
    return handoff


def load_rawprep_benchmark_runpod_smoke_handoff(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkRunPodSmokeHandoff:
    path = _handoff_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark RunPod smoke handoff artifact was not found: {path}")
    return RawPrepBenchmarkRunPodSmokeHandoff(**json.loads(path.read_text(encoding="utf-8")))
