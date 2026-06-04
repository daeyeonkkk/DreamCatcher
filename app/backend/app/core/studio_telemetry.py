from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .studio_paths import resolve_output_root as shared_resolve_output_root


TelemetrySource = Literal["queue", "studio", "rawprep", "export", "ops", "quality_automation", "quality_tuning"]


class StudioTelemetryEvent(BaseModel):
    event_id: str
    occurred_at: str
    output_root: str
    source: TelemetrySource
    event_type: str
    task_type: str | None = None
    job_id: str | None = None
    session_id: str | None = None
    status: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

def resolve_output_root(output_root: str) -> Path:
    return shared_resolve_output_root(output_root)


def telemetry_log_path(output_root: str) -> Path:
    root = resolve_output_root(output_root)
    return root / "_ops" / "telemetry.jsonl"


def record_studio_event(
    *,
    output_root: str,
    source: TelemetrySource,
    event_type: str,
    task_type: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StudioTelemetryEvent:
    log_path = telemetry_log_path(output_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    event = StudioTelemetryEvent(
        event_id=str(uuid4()),
        occurred_at=datetime.now(timezone.utc).isoformat(),
        output_root=str(resolve_output_root(output_root)),
        source=source,
        event_type=event_type,
        task_type=task_type,
        job_id=job_id,
        session_id=session_id,
        status=status,
        detail=detail,
        metadata=metadata or {},
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
    return event


def _matches_query(event: StudioTelemetryEvent, query: str | None) -> bool:
    if not query:
        return True
    needle = query.casefold().strip()
    if not needle:
        return True
    haystacks = [
        event.event_type,
        event.source,
        event.task_type or "",
        event.job_id or "",
        event.session_id or "",
        event.status or "",
        event.detail or "",
        json.dumps(event.metadata, ensure_ascii=False),
    ]
    return any(needle in value.casefold() for value in haystacks if value)


def list_recent_events(
    output_root: str,
    *,
    limit: int = 20,
    source: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    session_id: str | None = None,
    query: str | None = None,
) -> list[StudioTelemetryEvent]:
    log_path = telemetry_log_path(output_root)
    if not log_path.exists() or not log_path.is_file():
        return []

    events: list[StudioTelemetryEvent] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            event = StudioTelemetryEvent(**payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if source and event.source != source:
            continue
        if status and event.status != status:
            continue
        if event_type and event.event_type != event_type:
            continue
        if session_id and event.session_id != session_id:
            continue
        if not _matches_query(event, query):
            continue
        events.append(event)

    events.sort(key=lambda item: item.occurred_at, reverse=True)
    return events[: max(1, limit)]
