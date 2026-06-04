from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import requests
from pydantic import BaseModel, Field, ValidationError

from .rawprep_service import load_job_record as load_rawprep_job_record
from .rawprep_service import save_job_record as save_rawprep_job_record
from .studio_job_service import load_job_record as load_studio_job_record
from .studio_job_service import save_job_record as save_studio_job_record
from .studio_paths import repo_root
from .studio_queue import (
    WorkerMode,
    clear_worker_stop_request,
    external_worker_output_roots,
    launch_external_worker_processes,
    list_pending_entries,
    normalize_output_roots,
    queue_summary,
    request_worker_stop_many,
    start_queue_worker,
    worker_control_status,
)
from .studio_telemetry import record_studio_event


ProviderDesiredStatus = Literal["RUNNING", "EXITED", "TERMINATED", "UNKNOWN"]
ProviderControlState = Literal["unconfigured", "offline", "starting", "running", "stopping", "stopped", "error"]
ProviderTaskType = Literal["studio", "rawprep"]

ACTIVE_PROVIDER_JOB_STATUSES = {"queued", "running", "submitted", "cancelling"}
TERMINAL_PROVIDER_JOB_STATUSES = {"done", "cancelled", "failed", "blocked", "error"}


class RunPodProviderError(RuntimeError):
    pass


class RunPodProviderConfig(BaseModel):
    provider: Literal["runpod"] = "runpod"
    api_base_url: str = "https://rest.runpod.io/v1"
    api_token: str | None = None
    pod_id: str | None = None
    backend_url: str | None = None
    frontend_url: str | None = None
    backend_internal_port: int | None = None
    frontend_internal_port: int | None = None
    backend_health_path: str = "/health"
    request_timeout_seconds: float = 20.0

    @property
    def configured(self) -> bool:
        return bool(self.api_token and self.pod_id)


class StudioProviderCheckpointSavedVersion(BaseModel):
    id: str
    label: str
    path: str
    created_at: str


class StudioProviderCheckpointSessionSnapshot(BaseModel):
    session_id: str
    output_root: str
    rawprep_job_id: str | None = None
    studio_job_id: str | None = None
    direct_path: str | None = None
    compare_primary: str | None = None
    compare_candidate: str | None = None
    source_history: list[str] = Field(default_factory=list)
    source_history_index: int = -1
    saved_versions: list[StudioProviderCheckpointSavedVersion] = Field(default_factory=list)


class StudioProviderCheckpointActiveJob(BaseModel):
    task_type: ProviderTaskType
    job_id: str
    session_id: str
    output_root: str
    status: str
    current_step: str | None = None


class StudioProviderCheckpoint(BaseModel):
    checkpoint_id: str
    created_at: str
    updated_at: str
    reason: str | None = None
    pending_resume: bool = True
    output_roots: list[str] = Field(default_factory=list)
    worker_mode: WorkerMode = "external"
    poll_interval_seconds: float = 2.0
    session_snapshot: StudioProviderCheckpointSessionSnapshot | None = None
    active_jobs: list[StudioProviderCheckpointActiveJob] = Field(default_factory=list)
    last_resume_trigger: str | None = None
    last_resumed_at: str | None = None


class StudioProviderSummary(BaseModel):
    configured: bool = False
    provider: Literal["runpod"] = "runpod"
    pod_id: str | None = None
    control_state: ProviderControlState = "unconfigured"
    desired_status: ProviderDesiredStatus = "UNKNOWN"
    last_status_change: str | None = None
    public_ip: str | None = None
    host_id: str | None = None
    machine_id: str | None = None
    allocation_state: str | None = None
    migration_state: str | None = None
    pod_uptime_seconds: int | None = None
    gpu_count: int | None = None
    port_mappings: dict[str, int] = Field(default_factory=dict)
    backend_url: str | None = None
    frontend_url: str | None = None
    network_volume_attached: bool = False
    supports_stop: bool = True
    reason: str | None = None
    checkpoint_pending_resume: bool = False
    checkpoint_id: str | None = None
    checkpoint_updated_at: str | None = None
    checkpoint_reason: str | None = None
    checkpoint_session_id: str | None = None
    checkpoint_output_roots: list[str] = Field(default_factory=list)
    checkpoint_active_jobs: list[StudioProviderCheckpointActiveJob] = Field(default_factory=list)
    checkpoint_session_snapshot: StudioProviderCheckpointSessionSnapshot | None = None
    lifecycle_hints: list[str] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def provider_runtime_root() -> Path:
    path = repo_root() / "app" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def private_runtime_config_path() -> Path:
    return provider_runtime_root() / "private_config.json"


def load_private_runtime_config() -> dict[str, Any]:
    path = private_runtime_config_path()
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _private_setting(name: str, *, default: Any = None) -> Any:
    env_value = os.getenv(name)
    if env_value not in {None, ""}:
        return env_value
    payload = load_private_runtime_config()
    file_value = payload.get(name)
    if file_value in {None, ""}:
        return default
    return file_value


def provider_checkpoint_path() -> Path:
    return provider_runtime_root() / "provider_checkpoint.json"


def provider_lifecycle_state_path() -> Path:
    return provider_runtime_root() / "provider_lifecycle_state.json"


def load_provider_lifecycle_state() -> dict[str, Any]:
    path = provider_lifecycle_state_path()
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_provider_lifecycle_state(payload: dict[str, Any]) -> None:
    path = provider_lifecycle_state_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_runpod_provider_config() -> RunPodProviderConfig:
    backend_internal = _private_setting("RUNPOD_BACKEND_INTERNAL_PORT")
    frontend_internal = _private_setting("RUNPOD_FRONTEND_INTERNAL_PORT")
    timeout_raw = _private_setting("RUNPOD_API_TIMEOUT_SECONDS")
    try:
        timeout_seconds = max(5.0, float(timeout_raw)) if timeout_raw else 20.0
    except ValueError:
        timeout_seconds = 20.0
    return RunPodProviderConfig(
        api_base_url=str(_private_setting("RUNPOD_API_BASE_URL", default="https://rest.runpod.io/v1")).rstrip("/"),
        api_token=_private_setting("RUNPOD_API_TOKEN") or _private_setting("RUNPOD_API_KEY"),
        pod_id=_private_setting("RUNPOD_POD_ID"),
        backend_url=_private_setting("RUNPOD_BACKEND_URL"),
        frontend_url=_private_setting("RUNPOD_FRONTEND_URL"),
        backend_internal_port=int(backend_internal) if backend_internal and str(backend_internal).isdigit() else None,
        frontend_internal_port=int(frontend_internal) if frontend_internal and str(frontend_internal).isdigit() else None,
        backend_health_path=str(_private_setting("RUNPOD_BACKEND_HEALTH_PATH", default="/health")),
        request_timeout_seconds=timeout_seconds,
    )


def load_provider_checkpoint() -> StudioProviderCheckpoint | None:
    path = provider_checkpoint_path()
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StudioProviderCheckpoint(**payload)
    except (OSError, json.JSONDecodeError, TypeError, ValidationError):
        return None


def save_provider_checkpoint(checkpoint: StudioProviderCheckpoint) -> StudioProviderCheckpoint:
    checkpoint.updated_at = utc_now_iso()
    path = provider_checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return checkpoint


def _request_provider(
    config: RunPodProviderConfig,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not config.configured:
        raise RunPodProviderError(
            "RunPod provider control is not configured. "
            "Set RUNPOD_API_TOKEN and RUNPOD_POD_ID first, or fill app/runtime/private_config.json."
        )
    url = f"{config.api_base_url}{path}"
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.request_timeout_seconds,
    )
    if response.status_code >= 400:
        detail = response.text.strip()
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            detail = str(body.get("detail") or body.get("message") or detail or response.reason)
        raise RunPodProviderError(f"RunPod API {method} {path} failed: {detail or response.reason}")
    if not response.content:
        return {}
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def get_provider_pod(config: RunPodProviderConfig | None = None) -> dict[str, Any]:
    resolved = config or load_runpod_provider_config()
    return _request_provider(resolved, "GET", f"/pods/{resolved.pod_id}")


def start_provider_pod(config: RunPodProviderConfig | None = None) -> dict[str, Any]:
    resolved = config or load_runpod_provider_config()
    return _request_provider(resolved, "POST", f"/pods/{resolved.pod_id}/start")


def stop_provider_pod(config: RunPodProviderConfig | None = None) -> dict[str, Any]:
    resolved = config or load_runpod_provider_config()
    return _request_provider(resolved, "POST", f"/pods/{resolved.pod_id}/stop")


def wait_for_provider_control_state(
    expected: set[ProviderControlState],
    *,
    timeout_seconds: float = 240.0,
    poll_interval_seconds: float = 5.0,
) -> StudioProviderSummary:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    last_summary = provider_runtime_summary()
    while time.monotonic() < deadline:
        if last_summary.control_state in expected:
            return last_summary
        time.sleep(max(0.5, poll_interval_seconds))
        last_summary = provider_runtime_summary()
    return last_summary


def wait_for_backend_health(
    *,
    timeout_seconds: float = 240.0,
    poll_interval_seconds: float = 4.0,
    summary: StudioProviderSummary | None = None,
) -> bool:
    current = summary or provider_runtime_summary()
    if not current.backend_url:
        return False
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{current.backend_url.rstrip('/')}/health", timeout=10.0)
            if response.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(max(0.5, poll_interval_seconds))
        current = provider_runtime_summary()
        if not current.backend_url:
            return False
    return False


def _port_mappings_from_payload(pod_payload: dict[str, Any]) -> dict[str, int]:
    raw = pod_payload.get("portMappings")
    if not isinstance(raw, dict):
        return {}
    mappings: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        try:
            mappings[key] = int(value)
        except (TypeError, ValueError):
            continue
    return mappings


def _http_ports_from_payload(pod_payload: dict[str, Any]) -> list[int]:
    ports = pod_payload.get("ports")
    if not isinstance(ports, list):
        return []
    internal_ports: list[int] = []
    for item in ports:
        if not isinstance(item, str) or "/" not in item:
            continue
        raw_port, protocol = item.split("/", 1)
        if protocol != "http":
            continue
        try:
            internal_ports.append(int(raw_port))
        except ValueError:
            continue
    return internal_ports


def _derive_public_url(
    pod_payload: dict[str, Any],
    *,
    explicit_url: str | None,
    internal_port: int | None,
) -> str | None:
    if explicit_url:
        return explicit_url
    public_ip = pod_payload.get("publicIp")
    if not isinstance(public_ip, str) or not public_ip:
        return None
    mappings = _port_mappings_from_payload(pod_payload)
    if internal_port is not None:
        public_port = mappings.get(str(internal_port))
        if public_port is not None:
            return f"http://{public_ip}:{public_port}"
    http_ports = _http_ports_from_payload(pod_payload)
    if len(http_ports) == 1:
        public_port = mappings.get(str(http_ports[0]))
        if public_port is not None:
            return f"http://{public_ip}:{public_port}"
    return None


def _desired_status(pod_payload: dict[str, Any] | None) -> ProviderDesiredStatus:
    raw = pod_payload.get("desiredStatus") if isinstance(pod_payload, dict) else None
    if raw in {"RUNNING", "EXITED", "TERMINATED"}:
        return raw
    return "UNKNOWN"


def _control_state_from_payload(pod_payload: dict[str, Any] | None, checkpoint: StudioProviderCheckpoint | None) -> ProviderControlState:
    desired = _desired_status(pod_payload)
    if desired == "RUNNING":
        public_ip = pod_payload.get("publicIp") if isinstance(pod_payload, dict) else None
        return "running" if isinstance(public_ip, str) and public_ip else "starting"
    if desired == "EXITED":
        return "stopped"
    if desired == "TERMINATED":
        return "offline"
    if checkpoint and checkpoint.pending_resume:
        return "offline"
    return "error"


def _reason_from_summary_state(
    *,
    config: RunPodProviderConfig,
    checkpoint: StudioProviderCheckpoint | None,
    desired_status: ProviderDesiredStatus,
    control_state: ProviderControlState,
    provider_error: str | None,
) -> str | None:
    if not config.configured:
        return "Provider 수명주기 제어를 쓰려면 RUNPOD_API_TOKEN과 RUNPOD_POD_ID가 필요하며, 없으면 app/runtime/private_config.json에 설정해야 합니다."
    if provider_error:
        return provider_error
    if checkpoint and checkpoint.pending_resume and control_state in {"running", "starting"}:
        return "Provider 체크포인트가 대기 중이며, 스튜디오 처리 대기열을 자동으로 다시 이어서 실행합니다."
    if checkpoint and checkpoint.pending_resume and control_state in {"offline", "stopped"}:
        return "Provider 체크포인트가 대기 중입니다. 저장된 스튜디오 세션을 다시 이어가려면 Pod를 시작해야 합니다."
    if desired_status == "EXITED":
        return "RunPod Pod가 종료된 상태입니다."
    if desired_status == "TERMINATED":
        return "RunPod Pod가 완전히 종료되어 provider 계층에서 다시 시작해야 합니다."
    if control_state == "running":
        return "RunPod provider 제어가 정상 연결 상태입니다."
    if control_state == "starting":
        return "RunPod provider가 Pod 시작 중 상태를 보고했습니다."
    return None


def _checkpoint_session_id(checkpoint: StudioProviderCheckpoint | None, resume_session_id: str | None) -> str | None:
    if checkpoint and checkpoint.session_snapshot is not None:
        return checkpoint.session_snapshot.session_id
    if checkpoint and checkpoint.active_jobs:
        return checkpoint.active_jobs[0].session_id
    return resume_session_id


def _first_text(payload: dict[str, Any] | None, *keys: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(payload: dict[str, Any] | None, *keys: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _lifecycle_hints(pod_payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(pod_payload, dict):
        return []
    hints: list[str] = []
    if pod_payload.get("interruptible") is True:
        hints.append("interruptible")
    if pod_payload.get("locked") is True:
        hints.append("locked")
    if pod_payload.get("networkVolume"):
        hints.append("network_volume_attached")
    migration_state = _first_text(pod_payload, "migrationState", "migrationStatus", "migration")
    if migration_state:
        hints.append(f"migration:{migration_state}")
    allocation_state = _first_text(pod_payload, "allocationState", "allocationStatus")
    if allocation_state:
        hints.append(f"allocation:{allocation_state}")
    return hints


def _provider_event_state(summary: StudioProviderSummary) -> dict[str, Any]:
    return {
        "control_state": summary.control_state,
        "desired_status": summary.desired_status,
        "public_ip": summary.public_ip,
        "host_id": summary.host_id,
        "machine_id": summary.machine_id,
        "allocation_state": summary.allocation_state,
        "migration_state": summary.migration_state,
        "last_status_change": summary.last_status_change,
    }


def _sync_provider_lifecycle_events(summary: StudioProviderSummary, *, output_root: str) -> None:
    current = _provider_event_state(summary)
    previous = load_provider_lifecycle_state()
    if previous == current:
        return
    change_labels: list[str] = []
    for key in ("control_state", "desired_status", "public_ip", "host_id", "machine_id", "allocation_state", "migration_state"):
        previous_value = previous.get(key)
        current_value = current.get(key)
        if previous_value != current_value:
            change_labels.append(f"{key} {previous_value or 'none'} -> {current_value or 'none'}")
    event_type = "provider_lifecycle_changed"
    if previous.get("host_id") and previous.get("host_id") != current.get("host_id"):
        event_type = "provider_migration_detected"
    elif previous.get("allocation_state") != current.get("allocation_state"):
        event_type = "provider_allocation_changed"
    record_studio_event(
        output_root=output_root,
        source="ops",
        event_type=event_type,
        status=summary.control_state,
        detail=" | ".join(change_labels) if change_labels else summary.reason,
        metadata=current,
    )
    save_provider_lifecycle_state(current)


def provider_runtime_summary(*, output_root: str = "outputs", resume_session_id: str | None = None) -> StudioProviderSummary:
    config = load_runpod_provider_config()
    checkpoint = load_provider_checkpoint()
    provider_error: str | None = None
    pod_payload: dict[str, Any] | None = None
    if config.configured:
        try:
            pod_payload = get_provider_pod(config)
        except RunPodProviderError as exc:
            provider_error = str(exc)

    desired_status = _desired_status(pod_payload)
    control_state = _control_state_from_payload(pod_payload, checkpoint) if pod_payload is not None else ("unconfigured" if not config.configured else "error")
    reason = _reason_from_summary_state(
        config=config,
        checkpoint=checkpoint,
        desired_status=desired_status,
        control_state=control_state,
        provider_error=provider_error,
    )
    network_volume = pod_payload.get("networkVolume") if isinstance(pod_payload, dict) else None
    summary = StudioProviderSummary(
        configured=config.configured,
        pod_id=config.pod_id,
        control_state=control_state,
        desired_status=desired_status,
        last_status_change=pod_payload.get("lastStatusChange") if isinstance(pod_payload, dict) and isinstance(pod_payload.get("lastStatusChange"), str) else None,
        public_ip=pod_payload.get("publicIp") if isinstance(pod_payload, dict) and isinstance(pod_payload.get("publicIp"), str) else None,
        host_id=_first_text(pod_payload, "hostId", "hostID"),
        machine_id=_first_text(pod_payload, "machineId", "machineID"),
        allocation_state=_first_text(pod_payload, "allocationState", "allocationStatus"),
        migration_state=_first_text(pod_payload, "migrationState", "migrationStatus", "migration"),
        pod_uptime_seconds=_first_int(pod_payload, "uptimeSeconds", "runtimeSeconds", "podUptimeSeconds"),
        gpu_count=_first_int(pod_payload, "gpuCount"),
        port_mappings=_port_mappings_from_payload(pod_payload or {}),
        backend_url=_derive_public_url(
            pod_payload or {},
            explicit_url=config.backend_url,
            internal_port=config.backend_internal_port,
        ),
        frontend_url=_derive_public_url(
            pod_payload or {},
            explicit_url=config.frontend_url,
            internal_port=config.frontend_internal_port,
        ),
        network_volume_attached=isinstance(network_volume, dict),
        supports_stop=True,
        reason=reason,
        checkpoint_pending_resume=checkpoint.pending_resume if checkpoint else False,
        checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
        checkpoint_updated_at=checkpoint.updated_at if checkpoint else None,
        checkpoint_reason=checkpoint.reason if checkpoint else None,
        checkpoint_session_id=_checkpoint_session_id(checkpoint, resume_session_id),
        checkpoint_output_roots=list(checkpoint.output_roots) if checkpoint else [],
        checkpoint_active_jobs=list(checkpoint.active_jobs) if checkpoint else [],
        checkpoint_session_snapshot=checkpoint.session_snapshot if checkpoint else None,
        lifecycle_hints=_lifecycle_hints(pod_payload),
    )
    if config.configured:
        _sync_provider_lifecycle_events(summary, output_root=output_root)
    return summary


def _guess_checkpoint_worker_mode(output_roots: list[str], requested_mode: WorkerMode | None) -> WorkerMode:
    if requested_mode in {"external", "embedded"}:
        return requested_mode
    for output_root in output_roots:
        status = worker_control_status(output_root)
        if status.mode in {"external", "embedded"}:
            return status.mode
    return "external"


def _guess_checkpoint_poll_interval_seconds(output_roots: list[str], requested: float | None) -> float:
    if requested is not None:
        return max(0.25, requested)
    for output_root in output_roots:
        status = worker_control_status(output_root)
        if status.running:
            return 2.0
    return 2.0


def _collect_checkpoint_active_jobs(
    output_roots: list[str],
    *,
    session_snapshot: StudioProviderCheckpointSessionSnapshot | None,
) -> list[StudioProviderCheckpointActiveJob]:
    jobs: list[StudioProviderCheckpointActiveJob] = []
    seen: set[tuple[str, str, str]] = set()
    for output_root in output_roots:
        for entry in list_pending_entries(output_root):
            key = (entry.task_type, entry.job_id, entry.output_root)
            if key in seen:
                continue
            seen.add(key)
            status = entry.status
            current_step: str | None = None
            if entry.task_type == "studio":
                try:
                    record = load_studio_job_record(entry.job_id, output_root=entry.output_root)
                    status = record.status
                    current_step = record.current_step
                except FileNotFoundError:
                    current_step = None
            else:
                try:
                    record = load_rawprep_job_record(entry.job_id, output_root=entry.output_root)
                    status = record.status
                    current_step = record.current_step
                except FileNotFoundError:
                    current_step = None
            if status not in ACTIVE_PROVIDER_JOB_STATUSES:
                continue
            jobs.append(
                StudioProviderCheckpointActiveJob(
                    task_type=entry.task_type,
                    job_id=entry.job_id,
                    session_id=entry.session_id,
                    output_root=entry.output_root,
                    status=status,
                    current_step=current_step,
                )
            )

    if session_snapshot is not None:
        for task_type, job_id in (("rawprep", session_snapshot.rawprep_job_id), ("studio", session_snapshot.studio_job_id)):
            if not job_id:
                continue
            key = (task_type, job_id, session_snapshot.output_root)
            if key in seen:
                continue
            seen.add(key)
            jobs.append(
                StudioProviderCheckpointActiveJob(
                    task_type=task_type,
                    job_id=job_id,
                    session_id=session_snapshot.session_id,
                    output_root=session_snapshot.output_root,
                    status="queued",
                    current_step="checkpointed",
                )
            )
    return jobs


def _wait_for_worker_stop(output_roots: list[str], *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if not any(worker_control_status(output_root).running for output_root in output_roots):
            return
        time.sleep(0.5)


def create_provider_checkpoint(
    *,
    output_root: str = "outputs",
    output_roots: list[str] | None = None,
    reason: str | None = None,
    worker_mode: WorkerMode | None = None,
    poll_interval_seconds: float | None = None,
    session_snapshot: StudioProviderCheckpointSessionSnapshot | None = None,
) -> StudioProviderCheckpoint:
    roots = normalize_output_roots([output_root, *(output_roots or [])])
    if session_snapshot is not None:
        roots = normalize_output_roots([*roots, session_snapshot.output_root])
    if not roots:
        roots = external_worker_output_roots(output_root)
    checkpoint = StudioProviderCheckpoint(
        checkpoint_id=str(uuid4()),
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        reason=reason,
        pending_resume=True,
        output_roots=roots,
        worker_mode=_guess_checkpoint_worker_mode(roots, worker_mode),
        poll_interval_seconds=_guess_checkpoint_poll_interval_seconds(roots, poll_interval_seconds),
        session_snapshot=session_snapshot,
        active_jobs=_collect_checkpoint_active_jobs(roots, session_snapshot=session_snapshot),
    )
    return save_provider_checkpoint(checkpoint)


def pause_provider_lifecycle(
    *,
    output_root: str = "outputs",
    output_roots: list[str] | None = None,
    reason: str | None = None,
    worker_mode: WorkerMode | None = None,
    poll_interval_seconds: float | None = None,
    session_snapshot: StudioProviderCheckpointSessionSnapshot | None = None,
    drain_timeout_seconds: float = 12.0,
    stop_provider: bool = True,
) -> StudioProviderSummary:
    resolved_reason = reason or "provider lifecycle pause requested"
    checkpoint = create_provider_checkpoint(
        output_root=output_root,
        output_roots=output_roots,
        reason=resolved_reason,
        worker_mode=worker_mode,
        poll_interval_seconds=poll_interval_seconds,
        session_snapshot=session_snapshot,
    )
    request_worker_stop_many(
        checkpoint.output_roots,
        requested_by="provider_pause",
        reason=resolved_reason,
    )
    for root in checkpoint.output_roots:
        record_studio_event(
            output_root=root,
            source="ops",
            event_type="provider_checkpoint_saved",
            status="queued",
            session_id=checkpoint.session_snapshot.session_id if checkpoint.session_snapshot else None,
            detail=checkpoint.checkpoint_id,
            metadata={
                "worker_mode": checkpoint.worker_mode,
                "checkpoint_reason": checkpoint.reason,
                "active_jobs": [item.model_dump() for item in checkpoint.active_jobs],
            },
        )
    _wait_for_worker_stop(checkpoint.output_roots, timeout_seconds=drain_timeout_seconds)
    if stop_provider:
        stop_provider_pod()
        for root in checkpoint.output_roots:
            record_studio_event(
                output_root=root,
                source="ops",
                event_type="provider_stop_requested",
                status="queued",
                session_id=checkpoint.session_snapshot.session_id if checkpoint.session_snapshot else None,
                detail=resolved_reason,
                metadata={"checkpoint_id": checkpoint.checkpoint_id},
            )
    summary = provider_runtime_summary(output_root=checkpoint.output_roots[0] if checkpoint.output_roots else output_root)
    summary.control_state = "stopping" if stop_provider else summary.control_state
    summary.reason = "현재 스튜디오 세션을 상태 저장한 뒤 RunPod Pod 중지를 요청했습니다." if stop_provider else summary.reason
    return summary


def _normalize_checkpointed_studio_job(job: StudioProviderCheckpointActiveJob) -> None:
    record = load_studio_job_record(job.job_id, output_root=job.output_root)
    if record.status in TERMINAL_PROVIDER_JOB_STATUSES:
        return
    if record.status in {"submitted", "running"} or record.comfy_prompt_id:
        record.status = "queued"
        record.current_step = "provider_resume_pending"
        record.comfy_prompt_id = None
        record.error = None
        record.finished_at = None
        record.notes.append("Studio 작업은 provider 일시정지 중 상태 저장되었고, 재개 시 다시 제출됩니다.")
        save_studio_job_record(record)


def _normalize_checkpointed_rawprep_job(job: StudioProviderCheckpointActiveJob) -> None:
    record = load_rawprep_job_record(job.job_id, output_root=job.output_root)
    if record.status in TERMINAL_PROVIDER_JOB_STATUSES:
        return
    if record.status == "running":
        record.status = "queued"
        record.current_step = "provider_resume_pending"
        record.error = None
        record.finished_at = None
        record.notes.append("rawprep 작업은 provider 일시정지 중 상태 저장되었고, 재개 시 다시 시작됩니다.")
        save_rawprep_job_record(record)


def _resume_checkpoint_jobs(checkpoint: StudioProviderCheckpoint) -> None:
    for job in checkpoint.active_jobs:
        try:
            if job.task_type == "studio":
                _normalize_checkpointed_studio_job(job)
            else:
                _normalize_checkpointed_rawprep_job(job)
        except FileNotFoundError:
            continue


def _resume_roots(output_roots: list[str], *, worker_mode: WorkerMode, poll_interval_seconds: float) -> None:
    for output_root in output_roots:
        clear_worker_stop_request(output_root)
    if worker_mode == "external":
        launch_external_worker_processes(output_roots, poll_interval_seconds=max(0.25, poll_interval_seconds))
        return
    for output_root in output_roots:
        start_queue_worker(output_root)


def resume_provider_lifecycle(
    *,
    output_root: str = "outputs",
    output_roots: list[str] | None = None,
    worker_mode: WorkerMode | None = None,
    poll_interval_seconds: float | None = None,
    trigger: str = "manual",
) -> tuple[StudioProviderSummary, list[str]]:
    checkpoint = load_provider_checkpoint()
    resolved_roots = normalize_output_roots([output_root, *(output_roots or [])])
    if checkpoint is not None and checkpoint.pending_resume:
        if checkpoint.output_roots:
            resolved_roots = normalize_output_roots(checkpoint.output_roots)
        elif checkpoint.session_snapshot is not None:
            resolved_roots = normalize_output_roots([checkpoint.session_snapshot.output_root])
        _resume_checkpoint_jobs(checkpoint)
        _resume_roots(
            resolved_roots,
            worker_mode=checkpoint.worker_mode,
            poll_interval_seconds=checkpoint.poll_interval_seconds,
        )
        checkpoint.pending_resume = False
        checkpoint.last_resume_trigger = trigger
        checkpoint.last_resumed_at = utc_now_iso()
        save_provider_checkpoint(checkpoint)
        for root in resolved_roots:
            record_studio_event(
                output_root=root,
                source="ops",
                event_type="provider_resume_completed",
                status="done",
                session_id=checkpoint.session_snapshot.session_id if checkpoint.session_snapshot else None,
                detail=checkpoint.checkpoint_id,
                metadata={
                    "trigger": trigger,
                    "worker_mode": checkpoint.worker_mode,
                    "active_job_count": len(checkpoint.active_jobs),
                },
            )
        return provider_runtime_summary(output_root=resolved_roots[0]), resolved_roots

    if not resolved_roots:
        resolved_roots = external_worker_output_roots(output_root)
    resolved_mode = worker_mode or _guess_checkpoint_worker_mode(resolved_roots, None)
    resolved_poll_interval = _guess_checkpoint_poll_interval_seconds(resolved_roots, poll_interval_seconds)
    _resume_roots(
        resolved_roots,
        worker_mode=resolved_mode,
        poll_interval_seconds=resolved_poll_interval,
    )
    for root in resolved_roots:
        record_studio_event(
            output_root=root,
            source="ops",
            event_type="provider_resume_requested",
            status="done",
            detail=trigger,
            metadata={"worker_mode": resolved_mode},
        )
    return provider_runtime_summary(output_root=resolved_roots[0] if resolved_roots else output_root), resolved_roots


def resume_provider_lifecycle_on_boot() -> list[str]:
    try:
        _summary, resumed_roots = resume_provider_lifecycle(trigger="boot")
    except Exception:
        return []
    return resumed_roots
