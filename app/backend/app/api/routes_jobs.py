from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..core.studio_job_service import (
    StudioJobRequest,
    assess_job_readiness,
    build_job_record,
    cancel_studio_job,
    dump_model,
    load_job_record,
    refresh_studio_job,
    retry_studio_job,
    save_job_record,
)
from ..core.studio_queue import clear_worker_stop_request, enqueue_job, start_queue_worker

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
def create_job(
    request: StudioJobRequest,
    execute: bool = False,
) -> Dict[str, Any]:
    try:
        record = build_job_record(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.source_path:
        if execute:
            record = assess_job_readiness(record, use_cache=False)
        if not record.execution_ready:
            record.status = "blocked"
            record.current_step = "backend_unavailable"
            record.error = record.availability_error or "ComfyUI is not ready for this tool."
            save_job_record(record)
            return dump_model(record)
        if execute:
            record.status = "queued"
            record.current_step = "queued"
            record.notes.append("Studio job was queued for background execution.")
            save_job_record(record)
            enqueue_job(
                task_type="studio",
                job_id=record.job_id,
                session_id=record.session_id,
                output_root=record.output_root,
            )
            clear_worker_stop_request(record.output_root)
            start_queue_worker(record.output_root)
        else:
            save_job_record(record)
        return dump_model(record)

    payload = dump_model(record)
    payload["job_id"] = record.job_id
    return payload


@router.get("/{job_id}")
def get_job(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = load_job_record(job_id, output_root=output_root)
        if record.status == "queued":
            start_queue_worker(record.output_root)
        record = refresh_studio_job(record)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return dump_model(record)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = cancel_studio_job(job_id, output_root=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return dump_model(record)


@router.post("/{job_id}/retry")
def retry_job(job_id: str, output_root: str = "outputs") -> Dict[str, Any]:
    try:
        record = retry_studio_job(job_id, output_root=output_root)
        if not record.execution_ready:
            record.status = "blocked"
            record.current_step = "backend_unavailable"
            record.error = record.availability_error or "ComfyUI is not ready for this tool."
            save_job_record(record)
            return dump_model(record)

        if not record.source_path:
            record.status = "blocked"
            record.current_step = "waiting_for_source"
            record.error = "Studio AI execution requires a source raster file."
            save_job_record(record)
            return dump_model(record)

        record.status = "queued"
        record.current_step = "queued"
        record.notes.append("Studio job was re-queued for background execution.")
        save_job_record(record)
        enqueue_job(
            task_type="studio",
            job_id=record.job_id,
            session_id=record.session_id,
            output_root=record.output_root,
        )
        clear_worker_stop_request(record.output_root)
        start_queue_worker(record.output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return dump_model(record)
