from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, Field

from .studio_compare_memory import record_compare_decision
from .studio_paths import repo_root, resolve_output_root
from .studio_recovery import build_session_recovery_packet


class RawPrepBenchmarkLocalRecoverySmokeRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    run_root: str = "_benchmark_runs/local_recovery"
    session_id: str = "local_recovery_demo"
    preset: str = "master_archive"


class RawPrepBenchmarkLocalRecoveryCheck(BaseModel):
    session_id: str | None = None
    session_root: str | None = None
    status: str = "missing"
    packet_path: str | None = None
    metadata_snapshot_path: str | None = None
    package_archive_path: str | None = None
    package_file_count: int = 0
    compare_decision_count: int = 0
    ready_for_result_retrieval: bool = False
    ready_for_metadata_retrieval: bool = False
    ready_for_provider_pause: bool = False
    issues: list[str] = Field(default_factory=list)
    summary: str


class RawPrepBenchmarkLocalRecoverySmoke(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    smoke_path: str
    run_root: str
    session_id: str
    status: str = "failed"
    ok: bool = False
    blocked_without_package: RawPrepBenchmarkLocalRecoveryCheck
    ready_with_package: RawPrepBenchmarkLocalRecoveryCheck
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Local recovery smoke output_dir must stay inside the configured output root.") from exc
    return resolved


def _resolve_run_root(path_value: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Local recovery smoke run_root must stay inside the configured output root.") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _smoke_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_local_recovery_smoke.json"


def _repo_relative_string(path: Path) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(resolved)


def _existing_repo_relative(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    return _repo_relative_string(path)


def _prepare_clean_session_root(run_root: Path, *, session_id: str) -> Path:
    session_root = run_root / session_id
    if session_root.exists():
        try:
            session_root.resolve().relative_to(run_root.resolve())
        except ValueError as exc:
            raise ValueError("Refusing to remove a recovery smoke session outside the configured run_root.") from exc
        import shutil

        shutil.rmtree(session_root)
    return session_root


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), color).save(path)


def _write_recovery_fixture(run_root: Path, *, session_id: str) -> Path:
    session_root = run_root / session_id
    staged_dir = session_root / "00_input"
    staged_dir.mkdir(parents=True, exist_ok=True)

    primary_path = staged_dir / "frame_a.jpg"
    candidate_path = staged_dir / "frame_b.jpg"
    _write_image(primary_path, (200, 80, 40))
    _write_image(candidate_path, (40, 120, 200))

    intake_payload = {
        "session_id": session_id,
        "session_root": str(session_root),
        "manifest_path": str(session_root / "studio_intake.json"),
        "entry_mode": "direct_edit_image",
        "entry_preference": "auto",
        "rawprep_optional": True,
        "alternate_modes": [],
        "staged_assets": [
            {
                "source_path": str(primary_path),
                "staged_path": str(primary_path),
                "file_name": primary_path.name,
                "suffix": primary_path.suffix,
                "kind": "image",
            },
            {
                "source_path": str(candidate_path),
                "staged_path": str(candidate_path),
                "file_name": candidate_path.name,
                "suffix": candidate_path.suffix,
                "kind": "image",
            },
        ],
        "editable_asset_path": str(primary_path),
        "single_raw_plan": None,
        "dreamisp_plan": None,
        "rawprep_request": None,
        "notes": [],
    }
    (session_root / "studio_intake.json").write_text(json.dumps(intake_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (session_root / "session_catalog.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "output_root": str(run_root),
                "rating": 5,
                "pick_status": "selected",
                "review_status": "proofing",
                "keywords": ["hero"],
                "updated_at": "2026-04-09T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (session_root / "rawprep_job.json").write_text(
        json.dumps(
            {
                "job_id": "rawprep_demo",
                "session_id": session_id,
                "status": "done",
                "group_reports": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    studio_job_root = session_root / "03_ai" / "jobs" / "job_demo"
    studio_job_root.mkdir(parents=True, exist_ok=True)
    (studio_job_root / "studio_job.json").write_text(
        json.dumps(
            {
                "job_id": "job_demo",
                "session_id": session_id,
                "status": "done",
                "tool": "replaceObject",
                "prompt": "배경을 정리하고 제품 가장자리를 깨끗하게 다듬기",
                "outputs": [{"path": str(primary_path), "label": "generated_candidate"}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    record_compare_decision(
        session_id=session_id,
        output_root=str(run_root),
        tool="compare",
        select_path=str(primary_path),
        candidate_path=str(candidate_path),
        winner_path=str(primary_path),
        action="keep_select",
        note="keep the cleaner frame",
    )
    return session_root


def _evaluate_packet(*, packet, expected_ready: bool, session_root: Path, blocked_case: bool) -> RawPrepBenchmarkLocalRecoveryCheck:
    issues: list[str] = []
    metadata_snapshot_path = _existing_repo_relative(packet.metadata_snapshot_path)
    package_archive_path = _existing_repo_relative(packet.package_archive_path)
    packet_path = _existing_repo_relative(str(session_root / "04_export" / "recovery" / "session_recovery_packet.json"))

    if not metadata_snapshot_path:
        issues.append("Recovery metadata snapshot was not materialized.")
    if blocked_case:
        if packet.ready_for_provider_pause:
            issues.append("Recovery packet unexpectedly reported ready_for_provider_pause without an export package.")
        if packet.ready_for_result_retrieval:
            issues.append("Recovery packet unexpectedly reported ready_for_result_retrieval without an export package.")
        if package_archive_path:
            issues.append("Recovery packet unexpectedly created a recovery archive in the blocked case.")
    else:
        if not packet.ready_for_provider_pause:
            issues.append("Recovery packet did not report ready_for_provider_pause after creating the recovery package.")
        if not packet.ready_for_result_retrieval:
            issues.append("Recovery packet did not report ready_for_result_retrieval after creating the recovery package.")
        if not packet.ready_for_metadata_retrieval:
            issues.append("Recovery packet did not report ready_for_metadata_retrieval after creating the recovery package.")
        if not package_archive_path:
            issues.append("Recovery package archive was not materialized.")
        if packet.package_file_count <= 0:
            issues.append("Recovery package archive did not report any packaged files.")

    status = "passed" if not issues and packet.ready_for_provider_pause is expected_ready else "failed"
    summary = (
        "Recovery guard stayed blocked until the export package was built."
        if blocked_case
        else "Recovery export produced package and metadata artifacts that are ready for provider pause."
    )
    if status == "failed":
        summary = "Recovery smoke found issues in the result retrieval and provider pause readiness flow."

    return RawPrepBenchmarkLocalRecoveryCheck(
        session_id=packet.session_id,
        session_root=_repo_relative_string(session_root),
        status=status,
        packet_path=packet_path,
        metadata_snapshot_path=metadata_snapshot_path,
        package_archive_path=package_archive_path,
        package_file_count=packet.package_file_count,
        compare_decision_count=packet.compare_decision_count,
        ready_for_result_retrieval=packet.ready_for_result_retrieval,
        ready_for_metadata_retrieval=packet.ready_for_metadata_retrieval,
        ready_for_provider_pause=packet.ready_for_provider_pause,
        issues=issues,
        summary=summary,
    )


def build_rawprep_benchmark_local_recovery_smoke(
    request: RawPrepBenchmarkLocalRecoverySmokeRequest,
) -> RawPrepBenchmarkLocalRecoverySmoke:
    run_root = _resolve_run_root(request.run_root, output_root=request.output_root)
    session_root = _prepare_clean_session_root(run_root, session_id=request.session_id)
    _write_recovery_fixture(run_root, session_id=request.session_id)

    blocked_packet = build_session_recovery_packet(
        session_id=request.session_id,
        output_root=str(run_root),
        preset=request.preset,
        create_package=False,
    )
    blocked_check = _evaluate_packet(
        packet=blocked_packet,
        expected_ready=False,
        session_root=session_root,
        blocked_case=True,
    )

    ready_packet = build_session_recovery_packet(
        session_id=request.session_id,
        output_root=str(run_root),
        preset=request.preset,
        create_package=True,
    )
    ready_check = _evaluate_packet(
        packet=ready_packet,
        expected_ready=True,
        session_root=session_root,
        blocked_case=False,
    )

    recommended_actions: list[str] = []
    if blocked_check.status != "passed":
        recommended_actions.append(
            "Fix the recovery guard so provider pause stays blocked until the recovery package exists."
        )
    if ready_check.status != "passed":
        recommended_actions.append(
            "Fix the recovery export flow so the package archive and metadata snapshot are both materialized before provider pause."
        )

    if blocked_check.status == "passed" and ready_check.status == "passed":
        status = "passed"
        summary = "Local recovery smoke verified result retrieval artifacts and provider-pause readiness transitions."
    else:
        status = "failed"
        summary = "Local recovery smoke found issues in the result retrieval and provider-pause readiness flow."

    return RawPrepBenchmarkLocalRecoverySmoke(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        smoke_path=str(_smoke_path(request.output_dir, output_root=request.output_root)),
        run_root=_repo_relative_string(run_root),
        session_id=request.session_id,
        status=status,
        ok=status == "passed",
        blocked_without_package=blocked_check,
        ready_with_package=ready_check,
        recommended_actions=recommended_actions,
        summary=summary,
    )


def write_rawprep_benchmark_local_recovery_smoke(
    request: RawPrepBenchmarkLocalRecoverySmokeRequest,
) -> RawPrepBenchmarkLocalRecoverySmoke:
    smoke = build_rawprep_benchmark_local_recovery_smoke(request)
    path = _smoke_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return smoke


def load_rawprep_benchmark_local_recovery_smoke(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepBenchmarkLocalRecoverySmoke:
    path = _smoke_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep local recovery smoke artifact was not found: {path}")
    return RawPrepBenchmarkLocalRecoverySmoke(**json.loads(path.read_text(encoding="utf-8")))
