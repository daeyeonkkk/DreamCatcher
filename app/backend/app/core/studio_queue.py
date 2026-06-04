from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel

from .rawprep_service import (
    detect_rawprep_tools,
    execute_rawprep_job,
    load_job_plan as load_rawprep_job_plan,
    load_job_record as load_rawprep_job_record,
)
from .studio_job_service import (
    execute_studio_job,
    load_job_record as load_studio_job_record,
    refresh_studio_job,
)
from .studio_telemetry import record_studio_event, resolve_output_root


QueueTaskType = Literal["studio", "rawprep"]
QueueState = Literal["queued", "running", "done", "failed", "cancelled"]
WorkerMode = Literal["embedded", "external"]
DEFAULT_WORKER_HEARTBEAT_TTL_SECONDS = 15.0
DEFAULT_QUEUE_MAX_ATTEMPTS = 3
DEFAULT_QUEUE_RETRY_BASE_SECONDS = 3.0
DEFAULT_QUEUE_RETRY_MAX_SECONDS = 30.0
DEFAULT_EXTERNAL_WORKER_IDLE_SHUTDOWN_SECONDS = 600.0


class StudioQueueEntry(BaseModel):
    queue_id: str
    task_type: QueueTaskType
    job_id: str
    session_id: str
    output_root: str
    status: QueueState
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    attempts: int = 0
    max_attempts: int = DEFAULT_QUEUE_MAX_ATTEMPTS
    next_attempt_at: str | None = None
    last_error: str | None = None


class StudioWorkerHeartbeat(BaseModel):
    worker_id: str
    mode: WorkerMode
    output_root: str
    pid: int
    started_at: str
    last_heartbeat_at: str
    processing: bool = False
    poll_interval_seconds: float = 2.0


class StudioWorkerStopRequest(BaseModel):
    output_root: str
    requested_at: str
    requested_by: str
    reason: str | None = None


class StudioQueueSummary(BaseModel):
    output_root: str
    pending_jobs: int
    delayed_jobs: int
    running_jobs: int
    active_workers: int
    worker_mode: WorkerMode | None = None
    worker_started_at: str | None = None
    worker_last_seen_at: str | None = None
    worker_pid: int | None = None
    worker_processing: bool = False
    stop_requested_at: str | None = None
    stop_requested_reason: str | None = None
    next_retry_at: str | None = None


class QueueProcessingResult(BaseModel):
    status: QueueState
    detail: str | None = None
    retryable: bool = False


class StudioWorkerControlStatus(BaseModel):
    output_root: str
    running: bool
    mode: WorkerMode | None = None
    started_at: str | None = None
    last_seen_at: str | None = None
    pid: int | None = None
    processing: bool = False
    stop_requested_at: str | None = None
    stop_requested_reason: str | None = None


_registry_lock = threading.Lock()
_active_workers: dict[str, threading.Thread] = {}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _queue_root(output_root: str) -> Path:
    return resolve_output_root(output_root) / "_queue"


def _pending_dir(output_root: str) -> Path:
    path = _queue_root(output_root) / "pending"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _history_dir(output_root: str) -> Path:
    path = _queue_root(output_root) / "history"
    path.mkdir(parents=True, exist_ok=True)
    return path


def heartbeat_path(output_root: str) -> Path:
    return _queue_root(output_root) / "worker_heartbeat.json"


def worker_stop_request_path(output_root: str) -> Path:
    return _queue_root(output_root) / "worker_stop.json"


def _entry_path(output_root: str, task_type: QueueTaskType, job_id: str) -> Path:
    return _pending_dir(output_root) / f"{task_type}_{job_id}.json"


def _history_path(entry: StudioQueueEntry) -> Path:
    timestamp = entry.finished_at or utc_now_iso()
    stamp = timestamp.replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")
    return _history_dir(entry.output_root) / f"{entry.queue_id}_{stamp}.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_entry(path: Path, entry: StudioQueueEntry) -> None:
    _write_json(path, entry.model_dump())


def _read_entry(path: Path) -> StudioQueueEntry | None:
    try:
        return StudioQueueEntry(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def queue_max_attempts() -> int:
    raw_value = os.getenv("DREAMCATCHER_QUEUE_MAX_ATTEMPTS")
    if not raw_value:
        return DEFAULT_QUEUE_MAX_ATTEMPTS
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_QUEUE_MAX_ATTEMPTS


def queue_retry_base_seconds() -> float:
    raw_value = os.getenv("DREAMCATCHER_QUEUE_RETRY_BASE_SECONDS")
    if not raw_value:
        return DEFAULT_QUEUE_RETRY_BASE_SECONDS
    try:
        return max(0.5, float(raw_value))
    except ValueError:
        return DEFAULT_QUEUE_RETRY_BASE_SECONDS


def queue_retry_max_seconds() -> float:
    raw_value = os.getenv("DREAMCATCHER_QUEUE_RETRY_MAX_SECONDS")
    if not raw_value:
        return DEFAULT_QUEUE_RETRY_MAX_SECONDS
    try:
        return max(queue_retry_base_seconds(), float(raw_value))
    except ValueError:
        return DEFAULT_QUEUE_RETRY_MAX_SECONDS


def queue_retry_delay_seconds(attempts: int) -> float:
    exponent = max(0, attempts - 1)
    delay = queue_retry_base_seconds() * (2 ** exponent)
    return min(delay, queue_retry_max_seconds())


def external_worker_idle_shutdown_seconds() -> float:
    raw_value = os.getenv("DREAMCATCHER_QUEUE_IDLE_SHUTDOWN_SECONDS")
    if raw_value is None or raw_value == "":
        return DEFAULT_EXTERNAL_WORKER_IDLE_SHUTDOWN_SECONDS
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_EXTERNAL_WORKER_IDLE_SHUTDOWN_SECONDS


def _entry_ready_for_attempt(entry: StudioQueueEntry) -> bool:
    next_attempt = _parse_iso(entry.next_attempt_at)
    if next_attempt is None:
        return True
    return next_attempt <= _utc_now()


def normalize_output_roots(output_roots: Iterable[str] | None) -> list[str]:
    roots: list[str] = []
    seen = set()
    for output_root in output_roots or []:
        normalized = str(resolve_output_root(output_root))
        if normalized in seen:
            continue
        seen.add(normalized)
        roots.append(normalized)
    return roots


def external_worker_output_roots(default_output_root: str = "outputs") -> list[str]:
    raw_value = os.getenv("DREAMCATCHER_QUEUE_OUTPUT_ROOTS")
    if raw_value:
        parts = [part.strip() for part in raw_value.split(",") if part.strip()]
        normalized = normalize_output_roots(parts)
        if normalized:
            return normalized
    return normalize_output_roots([default_output_root])


def read_worker_heartbeat(output_root: str) -> StudioWorkerHeartbeat | None:
    path = heartbeat_path(output_root)
    if not path.exists() or not path.is_file():
        return None
    try:
        return StudioWorkerHeartbeat(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def read_worker_stop_request(output_root: str) -> StudioWorkerStopRequest | None:
    path = worker_stop_request_path(output_root)
    if not path.exists() or not path.is_file():
        return None
    try:
        return StudioWorkerStopRequest(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def worker_heartbeat_is_fresh(
    heartbeat: StudioWorkerHeartbeat | None,
    *,
    stale_after_seconds: float = DEFAULT_WORKER_HEARTBEAT_TTL_SECONDS,
) -> bool:
    last_seen = _parse_iso(heartbeat.last_heartbeat_at if heartbeat else None)
    if last_seen is None:
        return False
    age_seconds = (_utc_now() - last_seen).total_seconds()
    return age_seconds <= stale_after_seconds


def write_worker_heartbeat(
    output_root: str,
    *,
    worker_id: str,
    mode: WorkerMode,
    processing: bool,
    poll_interval_seconds: float,
    started_at: str | None = None,
    pid: int | None = None,
) -> StudioWorkerHeartbeat:
    resolved_output_root = str(resolve_output_root(output_root))
    existing = read_worker_heartbeat(resolved_output_root)
    heartbeat = StudioWorkerHeartbeat(
        worker_id=worker_id,
        mode=mode,
        output_root=resolved_output_root,
        pid=pid or os.getpid(),
        started_at=started_at or (
            existing.started_at
            if existing and existing.worker_id == worker_id and existing.mode == mode
            else utc_now_iso()
        ),
        last_heartbeat_at=utc_now_iso(),
        processing=processing,
        poll_interval_seconds=poll_interval_seconds,
    )
    _write_json(heartbeat_path(resolved_output_root), heartbeat.model_dump())
    return heartbeat


def clear_worker_heartbeat(output_root: str, *, worker_id: str | None = None) -> None:
    path = heartbeat_path(output_root)
    if not path.exists():
        return
    if worker_id is not None:
        current = read_worker_heartbeat(output_root)
        if current is None or current.worker_id != worker_id:
            return
    path.unlink(missing_ok=True)


def clear_worker_stop_request(output_root: str) -> None:
    worker_stop_request_path(output_root).unlink(missing_ok=True)


def request_worker_stop(
    output_root: str,
    *,
    requested_by: str = "api",
    reason: str | None = None,
) -> StudioWorkerStopRequest:
    resolved_output_root = str(resolve_output_root(output_root))
    request = StudioWorkerStopRequest(
        output_root=resolved_output_root,
        requested_at=utc_now_iso(),
        requested_by=requested_by,
        reason=reason,
    )
    _write_json(worker_stop_request_path(resolved_output_root), request.model_dump())
    record_studio_event(
        output_root=resolved_output_root,
        source="queue",
        event_type="worker_stop_requested",
        status="queued",
        detail=reason or "처리 대기열 일시정지 요청",
        metadata={"requested_by": requested_by},
    )
    return request


def _healthy_external_worker(output_root: str) -> StudioWorkerHeartbeat | None:
    heartbeat = read_worker_heartbeat(output_root)
    if heartbeat is None or heartbeat.mode != "external":
        return None
    return heartbeat if worker_heartbeat_is_fresh(heartbeat) else None


def _inline_mode() -> bool:
    return os.getenv("DREAMCATCHER_QUEUE_INLINE") == "1" or os.getenv("PYTEST_CURRENT_TEST") is not None


def _embedded_worker_active(output_root: str) -> bool:
    with _registry_lock:
        existing = _active_workers.get(output_root)
        if existing is not None and not existing.is_alive():
            _active_workers.pop(output_root, None)
            existing = None
        return existing is not None


def _any_stop_requested(output_roots: Iterable[str]) -> bool:
    return any(read_worker_stop_request(output_root) is not None for output_root in output_roots)


def enqueue_job(*, task_type: QueueTaskType, job_id: str, session_id: str, output_root: str) -> StudioQueueEntry:
    resolved_output_root = str(resolve_output_root(output_root))
    queue_id = f"{task_type}_{job_id}"
    path = _entry_path(resolved_output_root, task_type, job_id)
    existing = _read_entry(path)
    created_at = existing.created_at if existing else utc_now_iso()
    entry = StudioQueueEntry(
        queue_id=queue_id,
        task_type=task_type,
        job_id=job_id,
        session_id=session_id,
        output_root=resolved_output_root,
        status="queued",
        created_at=created_at,
        updated_at=utc_now_iso(),
        attempts=existing.attempts if existing else 0,
        max_attempts=existing.max_attempts if existing else queue_max_attempts(),
        next_attempt_at=None,
        last_error=None,
    )
    _write_entry(path, entry)
    record_studio_event(
        output_root=resolved_output_root,
        source="queue",
        event_type="job_enqueued",
        task_type=task_type,
        job_id=job_id,
        session_id=session_id,
        status="queued",
    )
    return entry


def list_pending_entries(output_root: str) -> list[StudioQueueEntry]:
    entries: list[StudioQueueEntry] = []
    for path in _pending_dir(output_root).glob("*.json"):
        entry = _read_entry(path)
        if entry is None:
            continue
        entries.append(entry)
    entries.sort(
        key=lambda item: (
            1 if item.next_attempt_at else 0,
            item.next_attempt_at or item.created_at,
            item.created_at,
        )
    )
    return entries


def _recover_stale_entries(output_root: str) -> None:
    for path in _pending_dir(output_root).glob("*.json"):
        entry = _read_entry(path)
        if entry is None or entry.status != "running":
            continue
        entry.status = "queued"
        entry.updated_at = utc_now_iso()
        entry.next_attempt_at = None
        entry.last_error = None
        _write_entry(path, entry)
        record_studio_event(
            output_root=entry.output_root,
            source="queue",
            event_type="job_recovered",
            task_type=entry.task_type,
            job_id=entry.job_id,
            session_id=entry.session_id,
            status="queued",
            detail="작업기 중단 뒤 남아 있던 실행 중 항목을 다시 대기열로 복구했습니다.",
        )


def queue_summary(output_root: str) -> StudioQueueSummary:
    entries = list_pending_entries(output_root)
    resolved = str(resolve_output_root(output_root))
    heartbeat = read_worker_heartbeat(resolved)
    heartbeat_fresh = worker_heartbeat_is_fresh(heartbeat)
    stop_request = read_worker_stop_request(resolved)
    embedded_active = _embedded_worker_active(resolved)
    active_workers = 1 if embedded_active or heartbeat_fresh else 0
    next_retry = min(
        (entry.next_attempt_at for entry in entries if entry.next_attempt_at),
        default=None,
    )
    return StudioQueueSummary(
        output_root=resolved,
        pending_jobs=sum(1 for entry in entries if entry.status == "queued" and _entry_ready_for_attempt(entry)),
        delayed_jobs=sum(1 for entry in entries if entry.status == "queued" and not _entry_ready_for_attempt(entry)),
        running_jobs=sum(1 for entry in entries if entry.status == "running"),
        active_workers=active_workers,
        worker_mode=heartbeat.mode if heartbeat_fresh and heartbeat else ("embedded" if embedded_active else None),
        worker_started_at=heartbeat.started_at if heartbeat_fresh and heartbeat else None,
        worker_last_seen_at=heartbeat.last_heartbeat_at if heartbeat_fresh and heartbeat else None,
        worker_pid=heartbeat.pid if heartbeat_fresh and heartbeat else None,
        worker_processing=heartbeat.processing if heartbeat_fresh and heartbeat else False,
        stop_requested_at=stop_request.requested_at if stop_request else None,
        stop_requested_reason=stop_request.reason if stop_request else None,
        next_retry_at=next_retry,
    )


def worker_control_status(output_root: str) -> StudioWorkerControlStatus:
    resolved = str(resolve_output_root(output_root))
    heartbeat = read_worker_heartbeat(resolved)
    heartbeat_fresh = worker_heartbeat_is_fresh(heartbeat)
    stop_request = read_worker_stop_request(resolved)
    embedded_active = _embedded_worker_active(resolved)
    return StudioWorkerControlStatus(
        output_root=resolved,
        running=embedded_active or heartbeat_fresh,
        mode=heartbeat.mode if heartbeat_fresh and heartbeat else ("embedded" if embedded_active else None),
        started_at=heartbeat.started_at if heartbeat_fresh and heartbeat else None,
        last_seen_at=heartbeat.last_heartbeat_at if heartbeat_fresh and heartbeat else None,
        pid=heartbeat.pid if heartbeat_fresh and heartbeat else None,
        processing=heartbeat.processing if heartbeat_fresh and heartbeat else False,
        stop_requested_at=stop_request.requested_at if stop_request else None,
        stop_requested_reason=stop_request.reason if stop_request else None,
    )


def _queue_worker_launch_command(output_root: str, *, poll_interval_seconds: float) -> list[str]:
    return _queue_worker_launch_command_many([output_root], poll_interval_seconds=poll_interval_seconds)


def _queue_worker_launch_command_many(output_roots: Iterable[str], *, poll_interval_seconds: float) -> list[str]:
    resolved_roots = normalize_output_roots(output_roots)
    command = [
        sys.executable,
        "-m",
        "app.queue_worker",
    ]
    for output_root in resolved_roots:
        command.extend(["--output-root", output_root])
    command.extend([
        "--poll-interval",
        f"{max(0.25, poll_interval_seconds):g}",
    ])
    return command


def _spawn_queue_worker_process(command: list[str]) -> None:
    subprocess.Popen(  # noqa: S603
        command,
        cwd=str(_queue_worker_cwd()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_queue_worker_creationflags(),
    )


def _roots_requiring_external_launch(output_roots: Iterable[str]) -> list[str]:
    roots: list[str] = []
    for output_root in normalize_output_roots(output_roots):
        if _healthy_external_worker(output_root) is not None or _embedded_worker_active(output_root):
            continue
        roots.append(output_root)
    return roots


def list_known_output_roots(primary_output_root: str = "outputs") -> list[str]:
    return normalize_output_roots([primary_output_root, *external_worker_output_roots(primary_output_root)])


def _record_worker_launch_requested(output_roots: list[str], *, poll_interval_seconds: float) -> None:
    for output_root in output_roots:
        record_studio_event(
            output_root=output_root,
            source="queue",
            event_type="worker_launch_requested",
            status="queued",
            detail="외부 작업기 시작 요청",
            metadata={"mode": "external", "poll_interval_seconds": max(0.25, poll_interval_seconds), "roots": output_roots},
        )


def launch_external_worker_processes(
    output_roots: Iterable[str],
    *,
    poll_interval_seconds: float = 2.0,
) -> list[StudioWorkerControlStatus]:
    target_roots = normalize_output_roots(output_roots)
    if not target_roots:
        target_roots = external_worker_output_roots()

    launch_roots = _roots_requiring_external_launch(target_roots)
    for output_root in launch_roots:
        clear_worker_stop_request(output_root)

    if launch_roots:
        command = _queue_worker_launch_command_many(launch_roots, poll_interval_seconds=poll_interval_seconds)
        try:
            _spawn_queue_worker_process(command)
        except OSError as exc:
            for output_root in launch_roots:
                record_studio_event(
                    output_root=output_root,
                    source="queue",
                    event_type="worker_launch_failed",
                    status="failed",
                    detail=str(exc),
                    metadata={"mode": "external", "command": command, "roots": launch_roots},
                )
            raise RuntimeError(f"외부 대기열 작업기를 시작하지 못했습니다: {exc}") from exc
        _record_worker_launch_requested(launch_roots, poll_interval_seconds=poll_interval_seconds)

    return [worker_control_status(output_root) for output_root in target_roots]


def request_worker_stop_many(
    output_roots: Iterable[str],
    *,
    requested_by: str = "api",
    reason: str | None = None,
) -> list[StudioWorkerStopRequest]:
    return [
        request_worker_stop(output_root, requested_by=requested_by, reason=reason)
        for output_root in normalize_output_roots(output_roots)
    ]


def worker_control_status_many(output_roots: Iterable[str]) -> list[StudioWorkerControlStatus]:
    return [worker_control_status(output_root) for output_root in normalize_output_roots(output_roots)]


def _queue_worker_cwd() -> Path:
    return Path(__file__).resolve().parents[2]


def _queue_worker_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(getattr(subprocess, "DETACHED_PROCESS", 0))


def launch_external_worker_process(output_root: str, *, poll_interval_seconds: float = 2.0) -> StudioWorkerControlStatus:
    statuses = launch_external_worker_processes([output_root], poll_interval_seconds=poll_interval_seconds)
    return statuses[0]


def cancel_pending_entry(
    *,
    task_type: QueueTaskType,
    job_id: str,
    output_root: str,
    detail: str | None = None,
) -> bool:
    resolved_output_root = str(resolve_output_root(output_root))
    path = _entry_path(resolved_output_root, task_type, job_id)
    entry = _read_entry(path)
    if entry is None:
        return False
    _archive_entry(entry, status="cancelled", detail=detail)
    return True


def _mark_running(entry: StudioQueueEntry, *, count_attempt: bool = True) -> StudioQueueEntry:
    entry.status = "running"
    if count_attempt:
        entry.attempts += 1
    now_iso = utc_now_iso()
    if entry.started_at is None:
        entry.started_at = now_iso
    entry.updated_at = now_iso
    entry.next_attempt_at = None
    entry.last_error = None
    _write_entry(_entry_path(entry.output_root, entry.task_type, entry.job_id), entry)
    record_studio_event(
        output_root=entry.output_root,
        source="queue",
        event_type="job_started",
        task_type=entry.task_type,
        job_id=entry.job_id,
        session_id=entry.session_id,
        status="running",
        metadata={"attempt": entry.attempts, "max_attempts": entry.max_attempts},
    )
    return entry


def _requeue_for_poll(
    entry: StudioQueueEntry,
    *,
    detail: str | None = None,
    delay_seconds: float,
) -> StudioQueueEntry:
    next_attempt = _utc_now() + timedelta(seconds=max(0.25, delay_seconds))
    entry.status = "queued"
    entry.updated_at = utc_now_iso()
    entry.next_attempt_at = next_attempt.isoformat()
    entry.last_error = None
    _write_entry(_entry_path(entry.output_root, entry.task_type, entry.job_id), entry)
    record_studio_event(
        output_root=entry.output_root,
        source="queue",
        event_type="job_poll_scheduled",
        task_type=entry.task_type,
        job_id=entry.job_id,
        session_id=entry.session_id,
        status="queued",
        detail=detail,
        metadata={
            "attempt": entry.attempts,
            "max_attempts": entry.max_attempts,
            "delay_seconds": max(0.25, delay_seconds),
            "next_attempt_at": entry.next_attempt_at,
        },
    )
    return entry


def _schedule_retry(entry: StudioQueueEntry, *, detail: str | None = None) -> StudioQueueEntry:
    delay_seconds = queue_retry_delay_seconds(entry.attempts)
    next_attempt = _utc_now() + timedelta(seconds=delay_seconds)
    entry.status = "queued"
    entry.updated_at = utc_now_iso()
    entry.next_attempt_at = next_attempt.isoformat()
    entry.last_error = detail
    _write_entry(_entry_path(entry.output_root, entry.task_type, entry.job_id), entry)
    record_studio_event(
        output_root=entry.output_root,
        source="queue",
        event_type="job_retry_scheduled",
        task_type=entry.task_type,
        job_id=entry.job_id,
        session_id=entry.session_id,
        status="queued",
        detail=detail,
        metadata={
            "attempt": entry.attempts,
            "max_attempts": entry.max_attempts,
            "delay_seconds": delay_seconds,
            "next_attempt_at": entry.next_attempt_at,
        },
    )
    return entry


def _archive_entry(entry: StudioQueueEntry, *, status: QueueState, detail: str | None = None) -> None:
    pending_path = _entry_path(entry.output_root, entry.task_type, entry.job_id)
    entry.status = status
    entry.updated_at = utc_now_iso()
    entry.finished_at = entry.updated_at
    entry.last_error = detail
    history_path = _history_path(entry)
    _write_entry(history_path, entry)
    if pending_path.exists():
        pending_path.unlink()
    event_type = {
        "done": "job_completed",
        "failed": "job_failed",
        "cancelled": "job_cancelled",
    }.get(status, "job_finished")
    record_studio_event(
        output_root=entry.output_root,
        source="queue",
        event_type=event_type,
        task_type=entry.task_type,
        job_id=entry.job_id,
        session_id=entry.session_id,
        status=status,
        detail=detail,
        metadata={"attempts": entry.attempts, "max_attempts": entry.max_attempts},
    )


def _process_studio_entry(entry: StudioQueueEntry) -> QueueProcessingResult:
    record = load_studio_job_record(entry.job_id, output_root=entry.output_root)
    if record.status == "done":
        return QueueProcessingResult(status="done")
    if record.status == "cancelled":
        return QueueProcessingResult(status="cancelled", detail=record.error)
    if record.status == "blocked":
        return QueueProcessingResult(status="failed", detail=record.error, retryable=False)
    if record.status == "error":
        return QueueProcessingResult(status="failed", detail=record.error, retryable=True)
    if record.status in {"submitted", "running"} and record.comfy_prompt_id:
        refreshed = refresh_studio_job(record)
        if refreshed.status == "done":
            return QueueProcessingResult(status="done")
        if refreshed.status == "cancelled":
            return QueueProcessingResult(status="cancelled", detail=refreshed.error)
        if refreshed.status == "blocked":
            return QueueProcessingResult(status="failed", detail=refreshed.error, retryable=False)
        if refreshed.status == "error":
            return QueueProcessingResult(status="failed", detail=refreshed.error, retryable=True)
        return QueueProcessingResult(status="queued", detail=refreshed.current_step or refreshed.status)

    result = execute_studio_job(record)
    if result.status == "error":
        return QueueProcessingResult(status="failed", detail=result.error, retryable=True)
    if result.status == "blocked":
        return QueueProcessingResult(status="failed", detail=result.error, retryable=False)
    if result.status == "cancelled":
        return QueueProcessingResult(status="cancelled", detail=result.error)
    if result.status in {"submitted", "running"} and result.comfy_prompt_id:
        return QueueProcessingResult(status="queued", detail=result.current_step or result.status)
    return QueueProcessingResult(status="done")


def _process_rawprep_entry(entry: StudioQueueEntry) -> QueueProcessingResult:
    record = load_rawprep_job_record(entry.job_id, output_root=entry.output_root)
    if record.status == "done":
        return QueueProcessingResult(status="done")
    if record.status == "cancelled":
        return QueueProcessingResult(status="cancelled")
    if record.status == "blocked":
        return QueueProcessingResult(status="failed", detail=record.error, retryable=False)
    if record.status == "failed":
        return QueueProcessingResult(status="failed", detail=record.error, retryable=True)

    plan = load_rawprep_job_plan(entry.job_id, output_root=entry.output_root)
    result = execute_rawprep_job(plan, detect_rawprep_tools())
    if result.status == "done":
        return QueueProcessingResult(status="done")
    if result.status == "cancelled":
        return QueueProcessingResult(status="cancelled")
    if result.status == "blocked":
        return QueueProcessingResult(status="failed", detail=result.error, retryable=False)
    return QueueProcessingResult(status="failed", detail=result.error, retryable=True)


def _process_entry(running_entry: StudioQueueEntry) -> QueueProcessingResult:
    if running_entry.task_type == "studio":
        return _process_studio_entry(running_entry)
    return _process_rawprep_entry(running_entry)


def process_pending_queue(
    output_root: str,
    *,
    worker_id: str | None = None,
    mode: WorkerMode | None = None,
    poll_interval_seconds: float = 2.0,
) -> None:
    _recover_stale_entries(output_root)
    if read_worker_stop_request(output_root) is not None:
        return
    if worker_id and mode:
        write_worker_heartbeat(output_root, worker_id=worker_id, mode=mode, processing=False, poll_interval_seconds=poll_interval_seconds)
    for entry in list_pending_entries(output_root):
        if read_worker_stop_request(output_root) is not None:
            break
        if entry.status != "queued" or not _entry_ready_for_attempt(entry):
            continue
        if worker_id and mode:
            write_worker_heartbeat(output_root, worker_id=worker_id, mode=mode, processing=True, poll_interval_seconds=poll_interval_seconds)
        count_attempt = True
        if entry.task_type == "studio":
            try:
                record = load_studio_job_record(entry.job_id, output_root=entry.output_root)
            except FileNotFoundError:
                record = None
            count_attempt = not (
                record is not None
                and record.status in {"submitted", "running"}
                and bool(record.comfy_prompt_id)
            )
        running_entry = _mark_running(entry, count_attempt=count_attempt)
        try:
            result = _process_entry(running_entry)
        except Exception as exc:  # pragma: no cover - defensive fallback
            result = QueueProcessingResult(status="failed", detail=str(exc), retryable=True)
        if result.status == "queued":
            _requeue_for_poll(running_entry, detail=result.detail, delay_seconds=poll_interval_seconds)
        elif result.status == "failed" and result.retryable and running_entry.attempts < running_entry.max_attempts:
            _schedule_retry(running_entry, detail=result.detail)
        else:
            _archive_entry(running_entry, status=result.status, detail=result.detail)
        if worker_id and mode:
            write_worker_heartbeat(output_root, worker_id=worker_id, mode=mode, processing=False, poll_interval_seconds=poll_interval_seconds)


def start_queue_worker(output_root: str) -> None:
    resolved_output_root = str(resolve_output_root(output_root))
    if read_worker_stop_request(resolved_output_root) is not None:
        return
    if _healthy_external_worker(resolved_output_root):
        return
    if _inline_mode():
        process_pending_queue(resolved_output_root)
        return

    with _registry_lock:
        existing = _active_workers.get(resolved_output_root)
        if existing is not None and existing.is_alive():
            return

        def run() -> None:
            worker_id = f"embedded-{os.getpid()}-{threading.get_ident()}-{Path(resolved_output_root).name}"
            record_studio_event(
                output_root=resolved_output_root,
                source="queue",
                event_type="worker_started",
                status="running",
                detail="embedded queue worker started",
                metadata={"mode": "embedded"},
            )
            try:
                process_pending_queue(
                    resolved_output_root,
                    worker_id=worker_id,
                    mode="embedded",
                    poll_interval_seconds=2.0,
                )
            finally:
                clear_worker_heartbeat(resolved_output_root, worker_id=worker_id)
                record_studio_event(
                    output_root=resolved_output_root,
                    source="queue",
                    event_type="worker_stopped",
                    status="done",
                    detail="embedded queue worker stopped",
                    metadata={"mode": "embedded"},
                )
                with _registry_lock:
                    _active_workers.pop(resolved_output_root, None)

        worker = threading.Thread(
            target=run,
            name=f"dreamcatcher-queue-{Path(resolved_output_root).name}",
            daemon=True,
        )
        _active_workers[resolved_output_root] = worker
        worker.start()


def _assert_no_conflicting_external_workers(output_roots: list[str]) -> None:
    conflicts = [
        output_root
        for output_root in output_roots
        if (heartbeat := _healthy_external_worker(output_root)) is not None and heartbeat.pid != os.getpid()
    ]
    if conflicts:
        joined = ", ".join(conflicts)
        raise RuntimeError(f"Another external queue worker is already active for: {joined}")


def run_external_worker_service(
    output_roots: Iterable[str],
    *,
    poll_interval_seconds: float = 2.0,
    once: bool = False,
) -> None:
    resolved_roots = normalize_output_roots(output_roots)
    if not resolved_roots:
        resolved_roots = external_worker_output_roots()
    _assert_no_conflicting_external_workers(resolved_roots)
    idle_shutdown_seconds = external_worker_idle_shutdown_seconds()
    last_work_seen_at = time.monotonic()

    worker_id = f"external-{os.getpid()}-{len(resolved_roots)}roots"
    for output_root in resolved_roots:
        record_studio_event(
            output_root=output_root,
            source="queue",
            event_type="worker_started",
            status="running",
            detail="external queue worker started",
            metadata={"mode": "external", "poll_interval_seconds": poll_interval_seconds, "roots": resolved_roots},
        )
    try:
        while True:
            if _any_stop_requested(resolved_roots):
                break
            any_work_remaining = False
            for output_root in resolved_roots:
                if _any_stop_requested(resolved_roots):
                    break
                pending_entries = list_pending_entries(output_root)
                any_work_remaining = any_work_remaining or bool(pending_entries)
                ready_entries = [
                    entry
                    for entry in pending_entries
                    if entry.status == "queued" and _entry_ready_for_attempt(entry)
                ]
                if pending_entries:
                    last_work_seen_at = time.monotonic()
                write_worker_heartbeat(
                    output_root,
                    worker_id=worker_id,
                    mode="external",
                    processing=bool(ready_entries),
                    poll_interval_seconds=poll_interval_seconds,
                )
                if ready_entries:
                    process_pending_queue(
                        output_root,
                        worker_id=worker_id,
                        mode="external",
                        poll_interval_seconds=poll_interval_seconds,
                    )
                    last_work_seen_at = time.monotonic()
            if once:
                break
            if _any_stop_requested(resolved_roots):
                break
            if (
                idle_shutdown_seconds > 0
                and not any_work_remaining
                and time.monotonic() - last_work_seen_at >= idle_shutdown_seconds
            ):
                for output_root in resolved_roots:
                    record_studio_event(
                        output_root=output_root,
                        source="queue",
                        event_type="worker_idle_shutdown",
                        status="done",
                        detail="external queue worker stopped after the idle timeout elapsed",
                        metadata={"mode": "external", "idle_shutdown_seconds": idle_shutdown_seconds},
                    )
                break
            time.sleep(max(0.25, poll_interval_seconds))
    finally:
        for output_root in resolved_roots:
            clear_worker_heartbeat(output_root, worker_id=worker_id)
            record_studio_event(
                output_root=output_root,
                source="queue",
                event_type="worker_stopped",
                status="done",
                detail="external queue worker stopped",
                metadata={"mode": "external", "roots": resolved_roots},
            )


def run_external_worker_loop(output_root: str, *, poll_interval_seconds: float = 2.0, once: bool = False) -> None:
    run_external_worker_service(
        [output_root],
        poll_interval_seconds=poll_interval_seconds,
        once=once,
    )


def resume_known_queues(default_output_roots: list[str] | None = None) -> None:
    configured_roots = default_output_roots if default_output_roots is not None else external_worker_output_roots("outputs")
    for output_root in normalize_output_roots(configured_roots):
        if list_pending_entries(output_root):
            start_queue_worker(output_root)
