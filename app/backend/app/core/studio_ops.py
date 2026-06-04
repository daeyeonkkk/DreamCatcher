from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from .rawprep_service import load_job_record as load_rawprep_job_record
from .runpod_provider import StudioProviderSummary, provider_runtime_summary
from .studio_job_service import (
    check_comfy_readiness,
    comfy_base_url,
    load_job_record as load_studio_job_record,
)
from .studio_paths import resolve_output_root
from .studio_queue import (
    StudioQueueEntry,
    external_worker_idle_shutdown_seconds,
    list_known_output_roots,
    queue_summary,
)
from .studio_telemetry import StudioTelemetryEvent, list_recent_events


ActiveJobStatus = Literal["queued", "running", "submitted", "cancelling"]
DeadLetterInvestigationStatus = Literal["open", "acknowledged", "assigned", "resolved", "muted"]
PodState = Literal["offline", "booting", "ready", "busy", "failed", "stopping"]
BACKEND_RUNTIME_STARTED_AT = datetime.now(timezone.utc)


class StudioOpsJobSummary(BaseModel):
    job_id: str
    session_id: str
    job_type: Literal["rawprep", "studio"]
    output_root: str
    session_root: str | None = None
    tool: str | None = None
    status: str
    current_step: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    output_count: int = 0
    error: str | None = None


class StudioDeadLetterSummary(BaseModel):
    queue_id: str
    task_type: Literal["studio", "rawprep"]
    job_id: str
    session_id: str
    output_root: str
    status: str
    current_status: str | None = None
    tool: str | None = None
    current_step: str | None = None
    attempts: int = 0
    max_attempts: int = 0
    finished_at: str | None = None
    last_error: str | None = None
    history_path: str
    investigation_status: DeadLetterInvestigationStatus = "open"
    assigned_to: str | None = None
    acknowledged_at: str | None = None
    note: str | None = None
    investigation_updated_at: str | None = None


class StudioOpsSummary(BaseModel):
    output_root: str
    total_sessions: int
    active_jobs: int
    queued_jobs: int
    failed_jobs: int
    completed_jobs: int
    exported_packages: int
    saved_exports: int
    pending_queue: int
    delayed_queue: int
    running_queue: int
    active_queue_workers: int
    worker_mode: str | None = None
    worker_started_at: str | None = None
    worker_last_seen_at: str | None = None
    worker_pid: int | None = None
    worker_processing: bool = False
    worker_stop_requested_at: str | None = None
    worker_stop_requested_reason: str | None = None
    next_retry_at: str | None = None
    pod_state: PodState = "ready"
    pod_state_reason: str | None = None
    ai_ready: bool = False
    comfy_reason: str | None = None
    runtime_started_at: str | None = None
    runtime_uptime_seconds: int | None = None
    idle_timeout_seconds: int | None = None
    idle_shutdown_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_failure_reason: str | None = None
    resume_session_id: str | None = None
    provider: StudioProviderSummary = Field(default_factory=StudioProviderSummary)
    dead_letter_count: int = 0
    dead_letters: list[StudioDeadLetterSummary] = Field(default_factory=list)
    recent_jobs: list[StudioOpsJobSummary] = Field(default_factory=list)
    recent_events: list[StudioTelemetryEvent] = Field(default_factory=list)


class StudioOpsRootSummary(BaseModel):
    output_root: str
    total_sessions: int
    pending_queue: int
    delayed_queue: int
    running_queue: int
    active_queue_workers: int
    worker_mode: str | None = None
    worker_last_seen_at: str | None = None
    worker_stop_requested_at: str | None = None
    dead_letter_count: int = 0


class StudioDeadLetterInvestigation(BaseModel):
    history_path: str
    output_root: str
    investigation_status: DeadLetterInvestigationStatus = "open"
    assigned_to: str | None = None
    acknowledged_at: str | None = None
    note: str | None = None
    updated_at: str


ACTIVE_STATUSES = {"queued", "running", "submitted", "cancelling"}
FAILED_STATUSES = {"failed", "error", "blocked"}
COMPLETED_STATUSES = {"done", "cancelled"}
CLOSED_INVESTIGATION_STATUSES = {"resolved", "muted"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def try_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _output_root_path(output_root: str) -> Path:
    return resolve_output_root(output_root)


def _dead_letter_state_path(output_root: str) -> Path:
    return _output_root_path(output_root) / "_ops" / "dead_letter_investigations.json"


def _load_index_entries(index_path: Path) -> list[dict[str, Any]]:
    payload = try_read_json(index_path)
    if not payload:
        return []
    return [value for value in payload.values() if isinstance(value, dict)]


def _job_sort_key(job: StudioOpsJobSummary) -> str:
    return job.updated_at or job.finished_at or job.started_at or job.created_at or ""


def _job_timestamp(job: StudioOpsJobSummary) -> datetime | None:
    for value in (job.finished_at, job.updated_at, job.started_at, job.created_at):
        parsed = _parse_iso(value)
        if parsed is not None:
            return parsed
    return None


def _latest_job_match(
    jobs: list[StudioOpsJobSummary],
    *,
    statuses: set[str],
) -> StudioOpsJobSummary | None:
    matching = [job for job in jobs if job.status in statuses]
    matching.sort(key=lambda job: _job_timestamp(job) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return matching[0] if matching else None


def _idle_shutdown_at(queue, *, active_jobs: int) -> str | None:
    idle_timeout_seconds = external_worker_idle_shutdown_seconds()
    if (
        idle_timeout_seconds <= 0
        or not queue.worker_last_seen_at
        or active_jobs > 0
        or queue.pending_jobs > 0
        or queue.delayed_jobs > 0
        or queue.running_jobs > 0
        or not queue.active_workers
    ):
        return None
    last_seen = _parse_iso(queue.worker_last_seen_at)
    if last_seen is None:
        return None
    return (last_seen + timedelta(seconds=idle_timeout_seconds)).isoformat()


def _resume_session_id(jobs: list[StudioOpsJobSummary], dead_letters: list[StudioDeadLetterSummary]) -> str | None:
    active_job = _latest_job_match(jobs, statuses=ACTIVE_STATUSES)
    if active_job is not None:
        return active_job.session_id
    if dead_letters:
        return dead_letters[0].session_id
    if jobs:
        return jobs[0].session_id
    return None


def _derive_pod_state(
    *,
    queue,
    active_jobs: int,
    failed_jobs: int,
    dead_letter_count: int,
    comfy_ready: bool,
    comfy_reason: str | None,
    last_failure_reason: str | None,
    provider: StudioProviderSummary,
) -> tuple[PodState, str]:
    if provider.configured and provider.control_state in {"offline", "stopped"}:
        return "offline", provider.reason or "RunPod pod is not running."
    if provider.configured and provider.control_state == "starting":
        return "booting", provider.reason or "RunPod pod is starting."
    if provider.configured and provider.control_state == "stopping":
        return "stopping", provider.reason or "RunPod pod stop is in progress."
    if queue.stop_requested_at and (active_jobs > 0 or queue.pending_jobs > 0 or queue.running_jobs > 0 or queue.delayed_jobs > 0):
        return "stopping", queue.stop_requested_reason or "Queue pause requested; waiting for work to drain."
    if not comfy_ready:
        if failed_jobs > 0 or dead_letter_count > 0:
            return "failed", last_failure_reason or comfy_reason or "ComfyUI is unavailable and recent jobs need attention."
        return "booting", comfy_reason or "ComfyUI is still starting."
    if failed_jobs > 0 or dead_letter_count > 0:
        return "failed", last_failure_reason or "Recent jobs failed and need review."
    if active_jobs > 0 or queue.pending_jobs > 0 or queue.running_jobs > 0 or queue.delayed_jobs > 0 or queue.worker_processing:
        return "busy", "Jobs are active or queued."
    if queue.stop_requested_at:
        return "ready", queue.stop_requested_reason or "Queue is paused and ready to resume."
    return "ready", "Backend and ComfyUI are ready."


def _studio_job_summary(payload: dict[str, Any], *, output_root: str) -> StudioOpsJobSummary | None:
    job_id = payload.get("job_id")
    session_id = payload.get("session_id")
    status = payload.get("status")
    if not isinstance(job_id, str) or not isinstance(session_id, str) or not isinstance(status, str):
        return None
    outputs = payload.get("outputs")
    output_count = len(outputs) if isinstance(outputs, list) else 0
    return StudioOpsJobSummary(
        job_id=job_id,
        session_id=session_id,
        job_type="studio",
        output_root=output_root,
        session_root=payload.get("session_root") if isinstance(payload.get("session_root"), str) else None,
        tool=payload.get("tool") if isinstance(payload.get("tool"), str) else None,
        status=status,
        current_step=payload.get("current_step") if isinstance(payload.get("current_step"), str) else None,
        created_at=payload.get("created_at") if isinstance(payload.get("created_at"), str) else None,
        updated_at=payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else None,
        started_at=payload.get("started_at") if isinstance(payload.get("started_at"), str) else None,
        finished_at=payload.get("finished_at") if isinstance(payload.get("finished_at"), str) else None,
        output_count=output_count,
        error=payload.get("error") if isinstance(payload.get("error"), str) else None,
    )


def _rawprep_job_summary(payload: dict[str, Any], *, output_root: str) -> StudioOpsJobSummary | None:
    job_id = payload.get("job_id")
    session_id = payload.get("session_id")
    status = payload.get("status")
    if not isinstance(job_id, str) or not isinstance(session_id, str) or not isinstance(status, str):
        return None
    artifacts = payload.get("artifacts")
    output_count = 0
    if isinstance(artifacts, list):
        output_count = sum(1 for artifact in artifacts if isinstance(artifact, dict) and artifact.get("exists"))
    return StudioOpsJobSummary(
        job_id=job_id,
        session_id=session_id,
        job_type="rawprep",
        output_root=output_root,
        session_root=payload.get("session_root") if isinstance(payload.get("session_root"), str) else None,
        tool="TriRaw",
        status=status,
        current_step=payload.get("current_step") if isinstance(payload.get("current_step"), str) else None,
        created_at=payload.get("created_at") if isinstance(payload.get("created_at"), str) else None,
        updated_at=payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else None,
        started_at=payload.get("started_at") if isinstance(payload.get("started_at"), str) else None,
        finished_at=payload.get("finished_at") if isinstance(payload.get("finished_at"), str) else None,
        output_count=output_count,
        error=payload.get("error") if isinstance(payload.get("error"), str) else None,
    )


def list_ops_jobs(output_root: str, *, limit: int = 12) -> list[StudioOpsJobSummary]:
    output_root_path = _output_root_path(output_root)
    jobs: list[StudioOpsJobSummary] = []

    for entry in _load_index_entries(output_root_path / "studio_job_index.json"):
        state_path = entry.get("state_path")
        if not isinstance(state_path, str):
            continue
        payload = try_read_json(Path(state_path))
        if not payload:
            continue
        summary = _studio_job_summary(payload, output_root=str(output_root_path))
        if summary:
            jobs.append(summary)

    for entry in _load_index_entries(output_root_path / "rawprep_job_index.json"):
        state_path = entry.get("state_path")
        if not isinstance(state_path, str):
            continue
        payload = try_read_json(Path(state_path))
        if not payload:
            continue
        summary = _rawprep_job_summary(payload, output_root=str(output_root_path))
        if summary:
            jobs.append(summary)

    jobs.sort(key=_job_sort_key, reverse=True)
    return jobs[: max(1, limit)]


def _history_queue_entries(output_root: Path) -> list[tuple[StudioQueueEntry, Path]]:
    history_root = output_root / "_queue" / "history"
    entries: list[tuple[StudioQueueEntry, Path]] = []
    if not history_root.exists():
        return entries
    for path in history_root.glob("*.json"):
        payload = try_read_json(path)
        if not payload:
            continue
        try:
            entry = StudioQueueEntry(**payload)
        except ValidationError:
            continue
        entries.append((entry, path))
    entries.sort(
        key=lambda item: item[0].finished_at or item[0].updated_at or item[0].created_at,
        reverse=True,
    )
    return entries


def load_dead_letter_investigations(output_root: str) -> dict[str, StudioDeadLetterInvestigation]:
    path = _dead_letter_state_path(output_root)
    payload = try_read_json(path)
    if not payload:
        return {}
    investigations: dict[str, StudioDeadLetterInvestigation] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        try:
            investigations[key] = StudioDeadLetterInvestigation(**value)
        except ValidationError:
            continue
    return investigations


def save_dead_letter_investigations(output_root: str, investigations: dict[str, StudioDeadLetterInvestigation]) -> None:
    path = _dead_letter_state_path(output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({key: value.model_dump() for key, value in investigations.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_dead_letter_investigation(
    output_root: str,
    *,
    history_path: str,
    assigned_to: str | None = None,
    acknowledged: bool | None = None,
    note: str | None = None,
    investigation_status: DeadLetterInvestigationStatus | None = None,
) -> StudioDeadLetterInvestigation:
    output_root_path = _output_root_path(output_root)
    resolved_history_path = Path(history_path).expanduser().resolve()
    try:
        resolved_history_path.relative_to(output_root_path)
    except ValueError as exc:
        raise ValueError("Dead-letter history path must stay inside the configured output root.") from exc
    if not resolved_history_path.exists() or not resolved_history_path.is_file():
        raise FileNotFoundError(f"Dead-letter history file does not exist: {resolved_history_path}")

    investigations = load_dead_letter_investigations(str(output_root_path))
    key = str(resolved_history_path)
    existing = investigations.get(key)
    normalized_assignee = assigned_to.strip() if isinstance(assigned_to, str) else None
    normalized_assignee = normalized_assignee or None
    normalized_note = note.strip() if isinstance(note, str) else None
    normalized_note = normalized_note or None
    acknowledged_at = existing.acknowledged_at if existing else None
    if acknowledged:
        acknowledged_at = acknowledged_at or utc_now_iso()
    status = investigation_status or (existing.investigation_status if existing else "open")
    if normalized_assignee is not None and investigation_status is None and status == "open":
        status = "assigned"
    if acknowledged and investigation_status is None and status == "open":
        status = "acknowledged"

    investigation = StudioDeadLetterInvestigation(
        history_path=key,
        output_root=str(output_root_path),
        investigation_status=status,
        assigned_to=normalized_assignee if assigned_to is not None else (existing.assigned_to if existing else None),
        acknowledged_at=acknowledged_at,
        note=normalized_note if note is not None else (existing.note if existing else None),
        updated_at=utc_now_iso(),
    )
    investigations[key] = investigation
    save_dead_letter_investigations(str(output_root_path), investigations)
    return investigation


def _dead_letter_summary(
    entry: StudioQueueEntry,
    history_path: Path,
    *,
    output_root: Path,
    investigations: dict[str, StudioDeadLetterInvestigation],
) -> StudioDeadLetterSummary | None:
    current_status: str | None = None
    current_step: str | None = None
    tool: str | None = None
    last_error = entry.last_error

    if entry.task_type == "studio":
        try:
            record = load_studio_job_record(entry.job_id, output_root=str(output_root))
        except FileNotFoundError:
            record = None
        if record is not None:
            current_status = record.status
            current_step = record.current_step
            tool = record.tool
            last_error = record.error or last_error
    else:
        try:
            record = load_rawprep_job_record(entry.job_id, output_root=str(output_root))
        except FileNotFoundError:
            record = None
        if record is not None:
            current_status = record.status
            current_step = record.current_step
            last_error = record.error or last_error
        tool = "TriRaw"

    if current_status is not None and current_status not in FAILED_STATUSES:
        return None

    investigation = investigations.get(str(history_path.resolve()))
    return StudioDeadLetterSummary(
        queue_id=entry.queue_id,
        task_type=entry.task_type,
        job_id=entry.job_id,
        session_id=entry.session_id,
        output_root=str(output_root),
        status=entry.status,
        current_status=current_status,
        tool=tool,
        current_step=current_step,
        attempts=entry.attempts,
        max_attempts=entry.max_attempts,
        finished_at=entry.finished_at,
        last_error=last_error,
        history_path=str(history_path),
        investigation_status=investigation.investigation_status if investigation else "open",
        assigned_to=investigation.assigned_to if investigation else None,
        acknowledged_at=investigation.acknowledged_at if investigation else None,
        note=investigation.note if investigation else None,
        investigation_updated_at=investigation.updated_at if investigation else None,
    )


def list_dead_letters(
    output_root: str,
    *,
    limit: int = 8,
    include_closed: bool = False,
) -> tuple[int, list[StudioDeadLetterSummary]]:
    output_root_path = _output_root_path(output_root)
    investigations = load_dead_letter_investigations(str(output_root_path))
    dead_letters: list[StudioDeadLetterSummary] = []
    for entry, history_path in _history_queue_entries(output_root_path):
        if entry.status != "failed":
            continue
        summary = _dead_letter_summary(
            entry,
            history_path,
            output_root=output_root_path,
            investigations=investigations,
        )
        if summary is None:
            continue
        if not include_closed and summary.investigation_status in CLOSED_INVESTIGATION_STATUSES:
            continue
        dead_letters.append(summary)
    return len(dead_letters), dead_letters[: max(1, limit)]


def summarize_operations_root(output_root: str) -> StudioOpsRootSummary:
    output_root_path = _output_root_path(output_root)
    queue = queue_summary(str(output_root_path))
    dead_letter_count, _dead_letters = list_dead_letters(str(output_root_path), limit=1)
    total_sessions = len(list(output_root_path.glob("*/studio_intake.json"))) if output_root_path.exists() else 0
    return StudioOpsRootSummary(
        output_root=str(output_root_path),
        total_sessions=total_sessions,
        pending_queue=queue.pending_jobs,
        delayed_queue=queue.delayed_jobs,
        running_queue=queue.running_jobs,
        active_queue_workers=queue.active_workers,
        worker_mode=queue.worker_mode,
        worker_last_seen_at=queue.worker_last_seen_at,
        worker_stop_requested_at=queue.stop_requested_at,
        dead_letter_count=dead_letter_count,
    )


def list_operations_roots(output_root: str, *, limit: int = 8) -> list[StudioOpsRootSummary]:
    roots = list_known_output_roots(output_root)
    summaries = [summarize_operations_root(root) for root in roots[: max(1, limit)]]
    summaries.sort(
        key=lambda item: (
            item.output_root != str(_output_root_path(output_root)),
            -(item.pending_queue + item.delayed_queue + item.running_queue + item.dead_letter_count),
            item.output_root,
        )
    )
    return summaries


def summarize_studio_operations(output_root: str, *, limit: int = 12) -> StudioOpsSummary:
    output_root_path = _output_root_path(output_root)
    all_jobs = list_ops_jobs(str(output_root_path), limit=10000)
    recent_jobs = all_jobs[: max(1, limit)]
    queue = queue_summary(str(output_root_path))
    recent_events = list_recent_events(str(output_root_path), limit=limit)
    dead_letter_count, dead_letters = list_dead_letters(str(output_root_path), limit=limit)
    comfy_ready, comfy_reason = check_comfy_readiness(base_url=comfy_base_url(), use_cache=True)

    total_sessions = len(list(output_root_path.glob("*/studio_intake.json"))) if output_root_path.exists() else 0
    exported_packages = len(list(output_root_path.glob("*/04_export/*.zip"))) if output_root_path.exists() else 0
    saved_exports = sum(
        1
        for path in output_root_path.glob("*/04_export/*")
        if path.is_file() and path.suffix.lower() != ".zip"
    ) if output_root_path.exists() else 0

    active_jobs = sum(1 for job in all_jobs if job.status in ACTIVE_STATUSES)
    queued_jobs = sum(1 for job in all_jobs if job.status == "queued")
    failed_jobs = sum(1 for job in all_jobs if job.status in FAILED_STATUSES)
    completed_jobs = sum(1 for job in all_jobs if job.status in COMPLETED_STATUSES)
    last_success_job = _latest_job_match(all_jobs, statuses=COMPLETED_STATUSES)
    last_failure_job = _latest_job_match(all_jobs, statuses=FAILED_STATUSES)
    last_success_at = _job_sort_key(last_success_job) if last_success_job else None
    last_failure_at = _job_sort_key(last_failure_job) if last_failure_job else None
    last_failure_reason = last_failure_job.error if last_failure_job else None
    resume_session_id = _resume_session_id(recent_jobs, dead_letters)
    provider = provider_runtime_summary(output_root=str(output_root_path), resume_session_id=resume_session_id)
    pod_state, pod_state_reason = _derive_pod_state(
        queue=queue,
        active_jobs=active_jobs,
        failed_jobs=failed_jobs,
        dead_letter_count=dead_letter_count,
        comfy_ready=comfy_ready,
        comfy_reason=comfy_reason,
        last_failure_reason=last_failure_reason,
        provider=provider,
    )
    runtime_now = datetime.now(timezone.utc)

    return StudioOpsSummary(
        output_root=str(output_root_path),
        total_sessions=total_sessions,
        active_jobs=active_jobs,
        queued_jobs=queued_jobs,
        failed_jobs=failed_jobs,
        completed_jobs=completed_jobs,
        exported_packages=exported_packages,
        saved_exports=saved_exports,
        pending_queue=queue.pending_jobs,
        delayed_queue=queue.delayed_jobs,
        running_queue=queue.running_jobs,
        active_queue_workers=queue.active_workers,
        worker_mode=queue.worker_mode,
        worker_started_at=queue.worker_started_at,
        worker_last_seen_at=queue.worker_last_seen_at,
        worker_pid=queue.worker_pid,
        worker_processing=queue.worker_processing,
        worker_stop_requested_at=queue.stop_requested_at,
        worker_stop_requested_reason=queue.stop_requested_reason,
        next_retry_at=queue.next_retry_at,
        pod_state=pod_state,
        pod_state_reason=pod_state_reason,
        ai_ready=comfy_ready,
        comfy_reason=comfy_reason,
        runtime_started_at=BACKEND_RUNTIME_STARTED_AT.isoformat(),
        runtime_uptime_seconds=max(0, int((runtime_now - BACKEND_RUNTIME_STARTED_AT).total_seconds())),
        idle_timeout_seconds=int(external_worker_idle_shutdown_seconds()),
        idle_shutdown_at=_idle_shutdown_at(queue, active_jobs=active_jobs),
        last_success_at=last_success_at,
        last_failure_at=last_failure_at,
        last_failure_reason=last_failure_reason,
        resume_session_id=resume_session_id,
        provider=provider,
        dead_letter_count=dead_letter_count,
        dead_letters=dead_letters,
        recent_jobs=recent_jobs,
        recent_events=recent_events,
    )
