import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.runpod_provider import (
    StudioProviderCheckpoint,
    StudioProviderCheckpointActiveJob,
    StudioProviderCheckpointSavedVersion,
    StudioProviderCheckpointSessionSnapshot,
    load_runpod_provider_config,
    pause_provider_lifecycle,
    provider_runtime_summary,
    resume_provider_lifecycle,
    save_provider_checkpoint,
)
from app.core.studio_recovery import StudioRecoveryPacket
from app.core.studio_job_service import StudioJobRecord, load_job_record as load_studio_job_record
from app.core.studio_job_service import save_job_record as save_studio_job_record
from app.core.studio_queue import enqueue_job, read_worker_stop_request


def utc_fixture() -> str:
    return "2026-03-19T00:00:00+00:00"


def fake_runpod_request_factory(calls: list[tuple[str, str]]):
    class Response:
        def __init__(self, status_code: int, payload: dict | None = None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = json.dumps(self._payload)
            self.reason = "OK"
            self.content = self.text.encode("utf-8")

        def json(self) -> dict:
            return self._payload

    def fake_request(method: str, url: str, **_kwargs):
        calls.append((method, url))
        if method == "GET" and url.endswith("/pods/pod_demo"):
            return Response(
                200,
                {
                    "id": "pod_demo",
                    "desiredStatus": "RUNNING",
                    "lastStatusChange": "Started",
                    "publicIp": "100.64.0.1",
                    "hostId": "host_demo",
                    "machineId": "machine_demo",
                    "allocationState": "allocated",
                    "migrationState": "stable",
                    "uptimeSeconds": 321,
                    "gpuCount": 1,
                    "interruptible": True,
                    "portMappings": {"8000": 32123, "5173": 32124},
                    "ports": ["8000/http", "5173/http"],
                },
            )
        if method == "POST" and url.endswith("/pods/pod_demo/stop"):
            return Response(200, {"ok": True})
        if method == "POST" and url.endswith("/pods/pod_demo/start"):
            return Response(200, {"ok": True})
        raise AssertionError(f"Unexpected RunPod request: {method} {url}")

    return fake_request


def build_studio_record(output_root: Path, *, status: str = "submitted", comfy_prompt_id: str | None = "prompt_demo") -> StudioJobRecord:
    session_root = output_root / "session_demo"
    session_root.mkdir(parents=True, exist_ok=True)
    (session_root / "studio_intake.json").write_text(
        json.dumps({"session_id": "session_demo", "session_root": str(session_root)}),
        encoding="utf-8",
    )
    job_root = session_root / "03_ai" / "jobs" / "job_demo"
    record = StudioJobRecord(
        job_id="job_demo",
        session_id="session_demo",
        tool="retouch",
        output_root=str(output_root),
        session_root=str(session_root),
        job_root=str(job_root),
        workflow_source="seed_bundle",
        workflow_path=str(job_root / "workflow.json"),
        workflow_exists=True,
        execution_ready=True,
        status=status,
        current_step="waiting_for_history",
        created_at=utc_fixture(),
        updated_at=utc_fixture(),
        started_at=utc_fixture(),
        finished_at=None,
        error=None,
        prompt="clean product edges",
        source_path=str(session_root / "02_edit" / "source.tif"),
        prepared_input_path=None,
        prepared_workflow_path=None,
        comfy_prompt_id=comfy_prompt_id,
        notes=[],
        outputs=[],
        warm_models=[],
        cold_models=[],
    )
    save_studio_job_record(record)
    return record


def test_provider_runtime_summary_reports_checkpoint_and_public_urls(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_TOKEN", "token_demo")
    monkeypatch.setenv("RUNPOD_POD_ID", "pod_demo")
    monkeypatch.setenv("RUNPOD_BACKEND_INTERNAL_PORT", "8000")
    monkeypatch.setenv("RUNPOD_FRONTEND_INTERNAL_PORT", "5173")
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)

    checkpoint = StudioProviderCheckpoint(
        checkpoint_id="checkpoint_demo",
        created_at=utc_fixture(),
        updated_at=utc_fixture(),
        reason="checkpoint before pod stop",
        pending_resume=True,
        output_roots=[str(tmp_path / "outputs")],
        worker_mode="external",
        poll_interval_seconds=2.0,
        session_snapshot=StudioProviderCheckpointSessionSnapshot(
            session_id="session_demo",
            output_root=str(tmp_path / "outputs"),
            studio_job_id="job_demo",
            rawprep_job_id=None,
            direct_path=None,
            compare_primary=None,
            compare_candidate=None,
            source_history=[],
            source_history_index=-1,
            saved_versions=[
                StudioProviderCheckpointSavedVersion(
                    id="version_1",
                    label="V01",
                    path=str(tmp_path / "outputs" / "session_demo" / "03_ai" / "result.jpg"),
                    created_at=utc_fixture(),
                )
            ],
        ),
        active_jobs=[
            StudioProviderCheckpointActiveJob(
                task_type="studio",
                job_id="job_demo",
                session_id="session_demo",
                output_root=str(tmp_path / "outputs"),
                status="submitted",
                current_step="waiting_for_history",
            )
        ],
    )
    save_provider_checkpoint(checkpoint)

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr("app.core.runpod_provider.requests.request", fake_runpod_request_factory(calls))

    summary = provider_runtime_summary(output_root=str(tmp_path / "outputs"))

    assert summary.configured is True
    assert summary.control_state == "running"
    assert summary.backend_url == "http://100.64.0.1:32123"
    assert summary.frontend_url == "http://100.64.0.1:32124"
    assert summary.host_id == "host_demo"
    assert summary.machine_id == "machine_demo"
    assert summary.allocation_state == "allocated"
    assert summary.migration_state == "stable"
    assert summary.pod_uptime_seconds == 321
    assert summary.gpu_count == 1
    assert "interruptible" in summary.lifecycle_hints
    assert summary.checkpoint_pending_resume is True
    assert summary.checkpoint_session_id == "session_demo"
    assert summary.reason == "Provider 체크포인트가 대기 중이며, 스튜디오 처리 대기열을 자동으로 다시 이어서 실행합니다."
    assert calls == [("GET", "https://rest.runpod.io/v1/pods/pod_demo")]


def test_load_runpod_provider_config_uses_tracked_private_config(tmp_path, monkeypatch):
    runtime_root = tmp_path / "app" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "private_config.json").write_text(
        json.dumps(
            {
                "RUNPOD_API_TOKEN": "token_from_file",
                "RUNPOD_POD_ID": "pod_from_file",
                "RUNPOD_BACKEND_INTERNAL_PORT": 8000,
                "RUNPOD_FRONTEND_INTERNAL_PORT": 5173,
                "RUNPOD_BACKEND_HEALTH_PATH": "/healthz",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)
    monkeypatch.delenv("RUNPOD_API_TOKEN", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_POD_ID", raising=False)
    monkeypatch.delenv("RUNPOD_BACKEND_INTERNAL_PORT", raising=False)
    monkeypatch.delenv("RUNPOD_FRONTEND_INTERNAL_PORT", raising=False)
    monkeypatch.delenv("RUNPOD_BACKEND_HEALTH_PATH", raising=False)

    config = load_runpod_provider_config()

    assert config.api_token == "token_from_file"
    assert config.pod_id == "pod_from_file"
    assert config.backend_internal_port == 8000
    assert config.frontend_internal_port == 5173
    assert config.backend_health_path == "/healthz"


def test_pause_and_resume_provider_lifecycle_requeues_checkpointed_studio_job(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("RUNPOD_API_TOKEN", "token_demo")
    monkeypatch.setenv("RUNPOD_POD_ID", "pod_demo")
    monkeypatch.setenv("RUNPOD_BACKEND_INTERNAL_PORT", "8000")
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)

    record = build_studio_record(output_root)
    enqueue_job(task_type="studio", job_id=record.job_id, session_id=record.session_id, output_root=str(output_root))

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr("app.core.runpod_provider.requests.request", fake_runpod_request_factory(calls))

    paused_summary = pause_provider_lifecycle(
        output_root=str(output_root),
        session_snapshot=StudioProviderCheckpointSessionSnapshot(
            session_id="session_demo",
            output_root=str(output_root),
            rawprep_job_id=None,
            studio_job_id="job_demo",
            direct_path=str(output_root / "session_demo" / "02_edit" / "source.tif"),
            compare_primary=None,
            compare_candidate=None,
            source_history=[],
            source_history_index=-1,
            saved_versions=[],
        ),
        stop_provider=True,
    )

    assert paused_summary.control_state == "stopping"
    assert read_worker_stop_request(str(output_root)) is not None

    launched: list[tuple[list[str], float]] = []

    def fake_launch(output_roots, *, poll_interval_seconds: float = 2.0):
        roots = list(output_roots)
        launched.append((roots, poll_interval_seconds))
        return []

    monkeypatch.setattr("app.core.runpod_provider.launch_external_worker_processes", fake_launch)

    resumed_summary, resumed_roots = resume_provider_lifecycle(output_root=str(output_root), trigger="test")
    resumed_record = load_studio_job_record("job_demo", output_root=str(output_root))

    assert resumed_summary.checkpoint_pending_resume is False
    assert resumed_roots == [str(output_root)]
    assert resumed_record.status == "queued"
    assert resumed_record.current_step == "provider_resume_pending"
    assert resumed_record.comfy_prompt_id is None
    assert launched == [([str(output_root)], 2.0)]
    assert ("POST", "https://rest.runpod.io/v1/pods/pod_demo/stop") in calls


def test_provider_pause_and_resume_routes_accept_session_snapshot(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.api.routes_studio.pause_provider_lifecycle", lambda **_kwargs: provider_runtime_summary(output_root=str(output_root)))
    monkeypatch.setattr("app.api.routes_studio.resume_provider_lifecycle", lambda **_kwargs: (provider_runtime_summary(output_root=str(output_root)), [str(output_root)]))

    pause_response = client.post(
        "/api/studio/ops/provider/pause",
        json={
            "output_root": str(output_root),
            "reason": "checkpoint before stop",
            "worker_mode": "external",
            "session_snapshot": {
                "session_id": "session_demo",
                "output_root": str(output_root),
                "studio_job_id": "job_demo",
                "rawprep_job_id": None,
                "direct_path": str(output_root / "session_demo" / "02_edit" / "source.tif"),
                "compare_primary": None,
                "compare_candidate": None,
                "source_history": [],
                "source_history_index": -1,
                "saved_versions": [],
            },
        },
    )
    resume_response = client.post(
        "/api/studio/ops/provider/resume",
        json={"output_root": str(output_root), "worker_mode": "external"},
    )

    assert pause_response.status_code == 200
    assert resume_response.status_code == 200
    assert pause_response.json()["provider"] == "runpod"
    assert resume_response.json()["provider"] == "runpod"


def test_provider_pause_route_requires_recovery_session_when_guard_enabled(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)

    response = client.post(
        "/api/studio/ops/provider/pause",
        json={
            "output_root": str(output_root),
            "require_recovery_ready": True,
        },
    )

    assert response.status_code == 400
    assert "recovery_session_id" in response.json()["detail"]


def test_provider_pause_route_includes_recovery_packet_when_guard_passes(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    monkeypatch.setattr("app.core.runpod_provider.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.api.routes_studio.pause_provider_lifecycle", lambda **_kwargs: provider_runtime_summary(output_root=str(output_root)))
    monkeypatch.setattr(
        "app.api.routes_studio.build_session_recovery_packet",
        lambda **_kwargs: StudioRecoveryPacket(
            session_id="session_demo",
            output_root=str(output_root),
            created_at=utc_fixture(),
            preset="master_archive",
            package_archive_path=str(output_root / "session_demo" / "04_export" / "bundle.zip"),
            package_file_name="bundle.zip",
            package_file_count=3,
            metadata_snapshot_path=str(output_root / "session_demo" / "04_export" / "recovery" / "session_recovery_metadata.json"),
            ready_for_result_retrieval=True,
            ready_for_metadata_retrieval=True,
            ready_for_provider_pause=True,
        ),
    )

    response = client.post(
        "/api/studio/ops/provider/pause",
        json={
            "output_root": str(output_root),
            "recovery_session_id": "session_demo",
            "recovery_preset": "master_archive",
            "require_recovery_ready": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "runpod"
    assert response.json()["recovery_packet"]["session_id"] == "session_demo"
    assert response.json()["recovery_packet"]["ready_for_provider_pause"] is True


def test_session_recovery_packet_routes_round_trip(tmp_path, monkeypatch):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    packet = StudioRecoveryPacket(
        session_id="session_demo",
        output_root=str(output_root),
        created_at=utc_fixture(),
        preset="master_archive",
        package_archive_path=str(output_root / "session_demo" / "04_export" / "bundle.zip"),
        package_file_name="bundle.zip",
        package_file_count=2,
        metadata_snapshot_path=str(output_root / "session_demo" / "04_export" / "recovery" / "session_recovery_metadata.json"),
        ready_for_result_retrieval=True,
        ready_for_metadata_retrieval=True,
        ready_for_provider_pause=True,
    )
    monkeypatch.setattr("app.api.routes_studio.build_session_recovery_packet", lambda **_kwargs: packet)
    monkeypatch.setattr("app.api.routes_studio.load_session_recovery_packet", lambda *_args, **_kwargs: packet)

    post_response = client.post(
        "/api/studio/export/recovery",
        json={
            "session_id": "session_demo",
            "output_root": str(output_root),
            "preset": "master_archive",
            "create_package": True,
        },
    )
    get_response = client.get(
        "/api/studio/export/recovery",
        params={"session_id": "session_demo", "output_root": str(output_root)},
    )

    assert post_response.status_code == 200
    assert get_response.status_code == 200
    assert post_response.json()["package_file_name"] == "bundle.zip"
    assert get_response.json()["ready_for_provider_pause"] is True
