import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app
from app.core.studio_queue import (
    QueueProcessingResult,
    enqueue_job,
    process_pending_queue,
    request_worker_stop,
    run_external_worker_loop,
    run_external_worker_service,
    start_queue_worker,
)
from app.core.studio_job_service import (
    StudioJobRequest,
    build_job_record,
    clear_comfy_readiness_cache,
    collect_job_outputs,
    save_job_record,
)
from app.core.studio_telemetry import list_recent_events

SEED_ROOT = Path(__file__).resolve().parents[3] / "seed_bundle"


@pytest.fixture(autouse=True)
def reset_comfy_readiness_cache():
    clear_comfy_readiness_cache()
    yield
    clear_comfy_readiness_cache()


def make_session_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 96), (180, 140, 120)).save(path)
    return str(path)


def test_create_job_plan_supports_frontend_tool_keys(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"

    response = client.post(
        "/api/jobs",
        json={
            "tool": "removeBg",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "removeBg"
    assert payload["workflow_exists"] is True
    assert payload["workflow_path"].endswith("cutout_birefnet.json")
    assert payload["execution_ready"] is False


def test_create_job_plan_supports_expand_canvas_tool(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"

    response = client.post(
        "/api/jobs",
        json={
            "tool": "expandCanvas",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "expandCanvas"
    assert payload["workflow_exists"] is True
    assert payload["workflow_path"].endswith("flux_fill_replace.api.json")
    assert payload["execution_ready"] is False


def test_create_job_plan_handles_non_executable_tools_gracefully(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"

    response = client.post(
        "/api/jobs",
        json={
            "tool": "compare",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "compare"
    assert payload["workflow_exists"] is False
    assert payload["execution_ready"] is False


def test_create_job_plan_reports_comfy_unavailable(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"

    response = client.post(
        "/api/jobs",
        json={
            "tool": "retouch",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_ready"] is False
    assert "AI 백엔드가 아직 준비되지 않았습니다" in payload["availability_error"]


def test_create_job_plan_reuses_cached_comfy_readiness(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    calls: list[str] = []

    monkeypatch.setenv("DREAMCATCHER_COMFY_READINESS_TTL_SECONDS", "60")
    clear_comfy_readiness_cache()

    def fake_system_stats(self):
        calls.append("stats")
        return {"devices": []}

    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.system_stats", fake_system_stats)

    first_response = client.post(
        "/api/jobs",
        json={
            "tool": "removeBg",
            "session_id": "session_one",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )
    second_response = client.post(
        "/api/jobs",
        json={
            "tool": "removeBg",
            "session_id": "session_two",
            "output_root": str(output_root),
            "seed_root": str(SEED_ROOT),
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["execution_ready"] is True
    assert second_response.json()["execution_ready"] is True
    assert calls == ["stats"]


def test_create_job_execute_queues_background_execution(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")

    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.system_stats", lambda self: {"devices": []})
    monkeypatch.setattr("app.api.routes_jobs.start_queue_worker", lambda _output_root: None)

    response = client.post(
        "/api/jobs?execute=true",
        json={
            "tool": "removeBg",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "source_path": source_path,
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    queue_path = output_root / "_queue" / "pending" / f"studio_{payload['job_id']}.json"
    assert queue_path.exists()


def test_create_job_execute_clears_manual_stop_request(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")

    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.system_stats", lambda self: {"devices": []})
    monkeypatch.setattr("app.api.routes_jobs.start_queue_worker", lambda _output_root: None)
    request_worker_stop(str(output_root), requested_by="test", reason="pause queue")

    response = client.post(
        "/api/jobs?execute=true",
        json={
            "tool": "removeBg",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "source_path": source_path,
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    assert not (output_root / "_queue" / "worker_stop.json").exists()


def test_create_job_execute_blocks_when_comfy_is_unavailable(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")

    response = client.post(
        "/api/jobs?execute=true",
        json={
            "tool": "retouch",
            "session_id": "session_demo",
            "output_root": str(output_root),
            "source_path": source_path,
            "seed_root": str(SEED_ROOT),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["current_step"] == "backend_unavailable"
    assert "AI 백엔드가 아직 준비되지 않았습니다" in payload["error"]


def test_get_job_refreshes_saved_record(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "submitted"
    record.current_step = "submitted"
    record.comfy_prompt_id = "prompt-demo"
    save_job_record(record)

    def fake_refresh(saved_record):
        saved_record.status = "done"
        saved_record.current_step = "done"
        saved_record.outputs = []
        save_job_record(saved_record)
        return saved_record

    monkeypatch.setattr("app.api.routes_jobs.refresh_studio_job", fake_refresh)

    response = client.get(f"/api/jobs/{record.job_id}", params={"output_root": str(output_root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == record.job_id
    assert payload["status"] == "done"


def test_collect_job_outputs_uses_korean_default_labels(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "remove_bg_preview.png"
    make_session_image(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].label == "배경 제거 결과 1"
    assert Path(outputs[0].path).exists()
    assert Path(outputs[0].origin) == rendered_path.resolve()


def test_process_pending_queue_keeps_submitted_job_pending_until_terminal_state(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "submitted"
    record.current_step = "submitted"
    record.comfy_prompt_id = "prompt-demo"
    save_job_record(record)
    enqueue_job(
        task_type="studio",
        job_id=record.job_id,
        session_id=record.session_id,
        output_root=record.output_root,
    )

    refresh_count = 0

    def fake_refresh(saved_record):
        nonlocal refresh_count
        refresh_count += 1
        if refresh_count == 1:
            saved_record.status = "running"
            saved_record.current_step = "waiting_for_outputs"
            save_job_record(saved_record)
            return saved_record
        saved_record.status = "done"
        saved_record.current_step = "done"
        saved_record.finished_at = "2026-03-19T00:02:00+00:00"
        save_job_record(saved_record)
        return saved_record

    monkeypatch.setattr("app.core.studio_queue.refresh_studio_job", fake_refresh)

    process_pending_queue(str(output_root), poll_interval_seconds=0.25)

    pending_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    assert pending_path.exists()
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["status"] == "queued"
    assert pending_payload["attempts"] == 0

    pending_payload["next_attempt_at"] = None
    pending_path.write_text(json.dumps(pending_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    process_pending_queue(str(output_root), poll_interval_seconds=0.25)

    history_dir = output_root / "_queue" / "history"
    assert not pending_path.exists()
    assert any(path.name.startswith(f"studio_{record.job_id}") for path in history_dir.glob("*.json"))


def test_cancel_job_marks_saved_record_cancelled(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "submitted"
    record.current_step = "submitted"
    record.comfy_prompt_id = "prompt-demo"
    save_job_record(record)

    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.manage_queue", lambda self, **kwargs: {"deleted": ["prompt-demo"]})
    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.interrupt", lambda self, prompt_id=None: {})

    response = client.post(f"/api/jobs/{record.job_id}/cancel", params={"output_root": str(output_root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["current_step"] == "cancelled"


def test_cancel_job_removes_pending_queue_entry_before_execution(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "queued"
    record.current_step = "queued"
    save_job_record(record)
    enqueue_job(
        task_type="studio",
        job_id=record.job_id,
        session_id=record.session_id,
        output_root=record.output_root,
    )

    response = client.post(f"/api/jobs/{record.job_id}/cancel", params={"output_root": str(output_root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    pending_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    history_dir = output_root / "_queue" / "history"
    assert not pending_path.exists()
    assert any(path.name.startswith(f"studio_{record.job_id}") for path in history_dir.glob("*.json"))


def test_retry_job_requeues_saved_record(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    monkeypatch.setattr("app.core.studio_job_service.ComfyClient.system_stats", lambda self: {"devices": []})
    monkeypatch.setattr("app.api.routes_jobs.start_queue_worker", lambda _output_root: None)
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "error"
    record.current_step = "comfy_failed"
    record.error = "previous failure"
    save_job_record(record)

    response = client.post(f"/api/jobs/{record.job_id}/retry", params={"output_root": str(output_root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["current_step"] == "queued"
    assert payload["error"] is None
    queue_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    assert queue_path.exists()


def test_external_queue_worker_processes_pending_studio_job(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "queued"
    record.current_step = "queued"
    save_job_record(record)
    enqueue_job(
        task_type="studio",
        job_id=record.job_id,
        session_id=record.session_id,
        output_root=record.output_root,
    )

    monkeypatch.setattr("app.core.studio_queue._process_studio_entry", lambda _entry: QueueProcessingResult(status="done"))

    run_external_worker_loop(str(output_root), poll_interval_seconds=0.25, once=True)

    pending_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    history_dir = output_root / "_queue" / "history"
    heartbeat_path = output_root / "_queue" / "worker_heartbeat.json"

    assert not pending_path.exists()
    assert any(path.name.startswith(f"studio_{record.job_id}") for path in history_dir.glob("*.json"))
    assert not heartbeat_path.exists()


def test_queue_schedules_retry_with_backoff_for_retryable_studio_failure(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "queued"
    record.current_step = "queued"
    save_job_record(record)
    enqueue_job(
        task_type="studio",
        job_id=record.job_id,
        session_id=record.session_id,
        output_root=record.output_root,
    )

    monkeypatch.setattr(
        "app.core.studio_queue._process_studio_entry",
        lambda _entry: QueueProcessingResult(status="failed", detail="temporary upstream error", retryable=True),
    )

    process_pending_queue(str(output_root))

    pending_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    payload = json.loads(pending_path.read_text(encoding="utf-8"))

    assert payload["status"] == "queued"
    assert payload["attempts"] == 1
    assert payload["next_attempt_at"] is not None
    assert payload["last_error"] == "temporary upstream error"


def test_start_queue_worker_respects_manual_stop_request(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    record.status = "queued"
    record.current_step = "queued"
    save_job_record(record)
    enqueue_job(
        task_type="studio",
        job_id=record.job_id,
        session_id=record.session_id,
        output_root=record.output_root,
    )
    request_worker_stop(str(output_root), requested_by="test", reason="pause queue")

    called = False

    def fake_process(_output_root: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.core.studio_queue.process_pending_queue", fake_process)

    start_queue_worker(str(output_root))

    assert called is False
    pending_path = output_root / "_queue" / "pending" / f"studio_{record.job_id}.json"
    assert pending_path.exists()


def test_request_worker_stop_records_korean_default_detail(tmp_path):
    output_root = tmp_path / "outputs"

    request_worker_stop(str(output_root), requested_by="test")

    events = list_recent_events(str(output_root), limit=5)

    assert events
    assert events[0].event_type == "worker_stop_requested"
    assert events[0].detail == "처리 대기열 일시정지 요청"


def test_external_queue_worker_service_handles_multiple_output_roots(tmp_path, monkeypatch):
    first_root = tmp_path / "outputs_a"
    second_root = tmp_path / "outputs_b"
    for output_root, session_id in [(first_root, "session_a"), (second_root, "session_b")]:
        session_root = output_root / session_id
        source_path = make_session_image(session_root / "02_manual" / "source.png")
        record = build_job_record(
            StudioJobRequest(
                tool="removeBg",
                session_id=session_id,
                output_root=str(output_root),
                source_path=source_path,
                seed_root=str(SEED_ROOT),
            )
        )
        record.status = "queued"
        record.current_step = "queued"
        save_job_record(record)
        enqueue_job(
            task_type="studio",
            job_id=record.job_id,
            session_id=record.session_id,
            output_root=record.output_root,
        )

    monkeypatch.setattr("app.core.studio_queue._process_studio_entry", lambda _entry: QueueProcessingResult(status="done"))

    run_external_worker_service([str(first_root), str(second_root)], poll_interval_seconds=0.25, once=True)

    assert not list((first_root / "_queue" / "pending").glob("*.json"))
    assert not list((second_root / "_queue" / "pending").glob("*.json"))
    assert not (first_root / "_queue" / "worker_heartbeat.json").exists()
    assert not (second_root / "_queue" / "worker_heartbeat.json").exists()


def test_external_queue_worker_service_stops_after_idle_timeout(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("DREAMCATCHER_QUEUE_IDLE_SHUTDOWN_SECONDS", "0.1")

    run_external_worker_service([str(output_root)], poll_interval_seconds=0.05, once=False)

    events = list_recent_events(str(output_root), limit=10)
    assert any(event.event_type == "worker_idle_shutdown" for event in events)
    assert not (output_root / "_queue" / "worker_heartbeat.json").exists()
