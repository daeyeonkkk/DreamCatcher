import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

from app.api.main import app
from app.core.rawprep_benchmark_local_ui_language_smoke import _UI_LANGUAGE_SURFACE_FILES
from app.core.studio_compare_memory import record_compare_decision


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-07",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "spec_only",
                        "sample_count": 0,
                        "evaluation_axes": ["noise_reduction", "detail_preservation"],
                    }
                },
                "tri_raw": {
                    "bucket_definitions": [
                        {
                            "bucket_id": "static_hdr",
                            "label": "Static HDR",
                            "status": "spec_only",
                            "sample_count": 0,
                            "hard_case": False,
                            "traits": ["static_scene"],
                            "required_report_sections": ["hdr_gain"],
                        }
                    ],
                    "hard_case_bucket": {
                        "defined": True,
                        "member_bucket_ids": [],
                    },
                },
                "report_template": {
                    "defined": True,
                    "sections": ["dataset_overview", "bucket_findings", "open_risks"],
                },
                "product_metrics": {
                    "compare_decision_logging": {
                        "defined": True,
                        "storage": [
                            "04_compare/decisions/compare_decision_*.json",
                            "_compare_learning/compare_decisions.jsonl",
                        ],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_compare_decision_fixture(output_root: Path) -> None:
    session_root = output_root / "session_demo" / "02_manual"
    session_root.mkdir(parents=True, exist_ok=True)
    select_path = session_root / "select.png"
    candidate_path = session_root / "candidate.png"
    Image.new("RGB", (24, 24), (96, 100, 110)).save(select_path)
    Image.new("RGB", (24, 24), (142, 134, 126)).save(candidate_path)
    record_compare_decision(
        session_id="session_demo",
        output_root=str(output_root),
        tool="compare",
        select_path=str(select_path),
        candidate_path=str(candidate_path),
        winner_path=str(candidate_path),
        action="accept_candidate",
    )


def _write_measured_benchmark_manifests_and_results(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "single_001.json").write_text(
        json.dumps(
            {
                "sample_id": "single_001",
                "status": "measured",
                "timing_ms": 910.0,
                "metrics": {"noise_reduction": 0.9},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "tri_001.json").write_text(
        json.dumps(
            {
                "sample_id": "tri_001",
                "status": "measured",
                "timing_ms": 1420.0,
                "metrics": {"hdr_gain": 0.82},
                "fallback_mode": "guarded_merge",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "measured",
                "samples": [
                    {
                        "sample_id": "single_001",
                        "raw_path": "samples/single_001/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_001.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "measured",
                "samples": [
                    {
                        "sample_id": "tri_001",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_001/frame_01.dng",
                            "samples/tri_001/frame_02.dng",
                            "samples/tri_001/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_001.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_pending_benchmark_manifests_and_results(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    results_root = repo_root / "outputs" / "_benchmark_results"
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "single_001.json").write_text(
        json.dumps(
            {
                "sample_id": "single_001",
                "status": "pending_measurement",
                "timing_ms": None,
                "metrics": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (results_root / "tri_001.json").write_text(
        json.dumps(
            {
                "sample_id": "tri_001",
                "status": "pending_measurement",
                "timing_ms": None,
                "metrics": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "single_001",
                        "raw_path": "samples/single_001/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_001.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "tri_001",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_001/frame_01.dng",
                            "samples/tri_001/frame_02.dng",
                            "samples/tri_001/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_001.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_single_raw_report(output_root: Path, sample_id: str, *, planner_total_ms: float = 533.0) -> Path:
    report_path = output_root / "session_demo" / "01_single_raw" / sample_id / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "resolved_mode": "fast",
                "runtime_profile": "sensor_fast_preview_v1",
                "status": "materialized",
                "timing_summary": f"Planner total: {planner_total_ms}ms",
                "noise_report": {
                    "suppression_ratio": 0.41,
                },
                "artifact_suppression": {
                    "texture_suppression_ratio": 0.14,
                    "saturation_suppression_ratio": 0.09,
                },
                "recovery_report": {
                    "lowlight_detail_gain_ratio": 0.36,
                },
                "fallback_decision": {
                    "reason_key": "fast_runtime_direct_preview",
                },
                "timing_report": {
                    "planner_total_ms": planner_total_ms,
                    "total_ms": planner_total_ms + 77.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def _write_scaffold_source_tree(repo_root: Path) -> Path:
    source_root = repo_root / "benchmark_sources" / "tri_raw"
    sample_root = source_root / "static_hdr" / "tripod_room"
    sample_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        (sample_root / f"frame_0{index}.dng").write_bytes(b"raw")
    return source_root


def _write_release_bundle_manifest(repo_root: Path) -> None:
    runpod_root = repo_root / "runpod"
    runpod_root.mkdir(parents=True, exist_ok=True)
    (runpod_root / "release_bundle_manifest.json").write_text(
        json.dumps({"official_artifact_name": "DreamCatcher.zip"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_release_bundle_zip(repo_root: Path) -> None:
    with ZipFile(repo_root / "DreamCatcher.zip", "w") as archive:
        archive.writestr("DreamCatcher/README.txt", "bundle")


def _write_runpod_smoke_evidence(repo_root: Path) -> None:
    runtime_root = repo_root / "app" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    rawprep_payload = {
        "ok": False,
        "message": "dreamcatcher-raw-engine-v2 is still scaffolded.",
    }
    single_raw_payload = {
        "ok": True,
        "preferred_backend": "rawpy",
        "sample_raw_path": "/workspace/sample_raw/input.CR3",
        "sample_decode_ok": True,
        "sample_result": {
            "preview_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/preview.jpg",
            "scene_linear_path": "/workspace/DreamCatcher/outputs/_single_raw_healthcheck/scene_linear.tiff",
        },
    }
    bootstrap_payload = {
        "checks": {
            "comfy_ready": True,
            "backend_ready": True,
            "runtime_workflows_present": True,
            "rawprep_healthcheck_present": True,
            "single_raw_runtime_ready": True,
            "single_raw_healthcheck_present": True,
        },
        "rawprep_healthcheck": rawprep_payload,
        "single_raw_healthcheck": single_raw_payload,
    }
    (runtime_root / "rawprep_healthcheck.json").write_text(json.dumps(rawprep_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "single_raw_healthcheck.json").write_text(json.dumps(single_raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (runtime_root / "bootstrap_summary.json").write_text(json.dumps(bootstrap_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_local_e2e_smoke_evidence(repo_root: Path, *, output_dir: str, status: str = "passed") -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_e2e_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-09T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "run_root": str(repo_root / "outputs" / "_benchmark_runs" / "local_e2e"),
                "status": status,
                "ok": status == "passed",
                "single_raw": {
                    "sample_id": "route_single_demo",
                    "session_id": "local_e2e_single_raw_route_single_demo",
                    "session_root": "outputs/_benchmark_runs/local_e2e/single_raw/local_e2e_single_raw_route_single_demo",
                    "entry_mode": "direct_edit_raw",
                    "status": status,
                    "ready_for_edit_ui": status == "passed",
                    "issues": [],
                    "summary": "single raw local e2e",
                },
                "tri_raw": {
                    "sample_id": "static_hdr__route_tri_demo",
                    "session_id": "local_e2e_tri_raw_route_tri_demo",
                    "session_root": "outputs/_benchmark_runs/local_e2e/tri_raw/local_e2e_tri_raw_route_tri_demo",
                    "entry_mode": "rawprep_bracket",
                    "status": status,
                    "ready_for_edit_ui": status == "passed",
                    "issues": [],
                    "summary": "tri raw local e2e",
                },
                "recommended_actions": [],
                "summary": "Local end-to-end smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_local_recovery_smoke_evidence(repo_root: Path, *, output_dir: str, status: str = "passed") -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_recovery_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-09T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "run_root": str(repo_root / "outputs" / "_benchmark_runs" / "local_recovery"),
                "session_id": "local_recovery_demo",
                "status": status,
                "ok": status == "passed",
                "blocked_without_package": {
                    "session_id": "local_recovery_demo",
                    "session_root": "outputs/_benchmark_runs/local_recovery/local_recovery_demo",
                    "status": status,
                    "packet_path": "outputs/_benchmark_runs/local_recovery/local_recovery_demo/04_export/recovery/session_recovery_packet.json",
                    "metadata_snapshot_path": "outputs/_benchmark_runs/local_recovery/local_recovery_demo/04_export/recovery/session_recovery_metadata.json",
                    "package_archive_path": None,
                    "package_file_count": 0,
                    "compare_decision_count": 1,
                    "ready_for_result_retrieval": False,
                    "ready_for_metadata_retrieval": True,
                    "ready_for_provider_pause": False,
                    "issues": [],
                    "summary": "blocked recovery smoke",
                },
                "ready_with_package": {
                    "session_id": "local_recovery_demo",
                    "session_root": "outputs/_benchmark_runs/local_recovery/local_recovery_demo",
                    "status": status,
                    "packet_path": "outputs/_benchmark_runs/local_recovery/local_recovery_demo/04_export/recovery/session_recovery_packet.json",
                    "metadata_snapshot_path": "outputs/_benchmark_runs/local_recovery/local_recovery_demo/04_export/recovery/session_recovery_metadata.json",
                    "package_archive_path": "outputs/_benchmark_runs/local_recovery/local_recovery_demo/04_export/local_recovery_demo_master_archive_recovery.zip",
                    "package_file_count": 4,
                    "compare_decision_count": 1,
                    "ready_for_result_retrieval": status == "passed",
                    "ready_for_metadata_retrieval": True,
                    "ready_for_provider_pause": status == "passed",
                    "issues": [],
                    "summary": "ready recovery smoke",
                },
                "recommended_actions": [],
                "summary": "Local recovery smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_local_ui_language_smoke_evidence(repo_root: Path, *, output_dir: str, status: str = "passed") -> None:
    smoke_path = repo_root / "outputs" / output_dir / "rawprep_local_ui_language_smoke.json"
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.write_text(
        json.dumps(
            {
                "output_dir": output_dir,
                "output_root": "outputs",
                "generated_at": "2026-04-13T00:00:00+00:00",
                "smoke_path": str(smoke_path),
                "status": status,
                "ok": status == "passed",
                "scanned_files": list(_UI_LANGUAGE_SURFACE_FILES),
                "scanned_file_count": len(_UI_LANGUAGE_SURFACE_FILES),
                "scanned_literal_count": 42,
                "allowed_token_hints": ["DreamCatcher", "DreamISP", "SingleRaw", "TriRaw", "RunPod", "RAW", "HDR"],
                "missing_files": [],
                "findings": [],
                "recommended_actions": [],
                "summary": "Local UI language smoke fixture.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_local_ui_surface_tree(repo_root: Path, *, english_surface: str | None = None) -> None:
    for relative_path in _UI_LANGUAGE_SURFACE_FILES:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            [
                "export const title = '현재 작업 공간';",
                "export const label = 'DreamCatcher 작업실';",
                "export const description = 'DreamISP 연결 상태를 확인합니다.';",
                "export function summary() {",
                "  return 'SingleRaw 비교 보기';",
                "}",
            ]
        )
        if english_surface is not None and relative_path == english_surface:
            text = "\n".join(
                [
                    "export const title = 'Workflow Rail';",
                    "export const description = '현재 작업 흐름을 정리합니다.';",
                ]
            )
        path.write_text(text, encoding="utf-8")


def _write_textured_preview(path: Path) -> None:
    width, height = 88, 64
    y, x = np.indices((height, width), dtype=np.float32)
    base = ((x / max(width - 1, 1)) * 88.0) + ((y / max(height - 1, 1)) * 44.0) + 52.0
    ripple = ((np.sin(x / 3.5) + 1.0) * 16.0) + ((np.cos(y / 4.5) + 1.0) * 10.0)
    red = np.clip(base + ripple, 0.0, 255.0)
    green = np.clip(base * 0.9 + ripple * 0.72, 0.0, 255.0)
    blue = np.clip(base * 0.82 + ripple * 0.55, 0.0, 255.0)
    Image.fromarray(np.stack((red, green, blue), axis=2).astype(np.uint8), mode="RGB").save(path)


def test_rawprep_benchmark_routes_return_record_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_compare_decision_fixture(tmp_path / "outputs")

    client = TestClient(app)

    response = client.post(
        "/api/rawprep/benchmark",
        json={
            "output_dir": "benchmarks/route_case",
            "output_root": "outputs",
            "label": "route_case",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "foundation_ready"
    assert payload["report_status"] == "foundation_ready"

    record_response = client.get("/api/rawprep/benchmark", params={"output_dir": "benchmarks/route_case", "output_root": "outputs"})
    assert record_response.status_code == 200
    assert record_response.json()["compare_decision_count"] == 1

    report_response = client.get(
        "/api/rawprep/benchmark/report",
        params={"output_dir": "benchmarks/route_case", "output_root": "outputs"},
    )
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["status"] == "foundation_ready"
    assert report_payload["dataset_overview"]["single_raw_sample_count"] == 0
    assert report_payload["fallback_behavior"]["compare_decision_summary"]["winner_role_counts"] == {"candidate": 1}

    health_response = client.get("/api/rawprep/benchmark/foundation", params={"output_root": "outputs"})
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["ok"] is True
    assert health_payload["status"] == "foundation_ready"
    assert health_payload["issue_counts"] == {"error": 0, "warning": 0}


def test_rawprep_benchmark_routes_surface_measured_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_benchmark_manifests_and_results(tmp_path)

    client = TestClient(app)

    response = client.post(
        "/api/rawprep/benchmark",
        json={
            "output_dir": "benchmarks/route_measured",
            "output_root": "outputs",
            "label": "route_measured",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "measured"
    assert payload["single_raw_measured_sample_count"] == 1
    assert payload["tri_raw_measured_sample_count"] == 1

    report_response = client.get(
        "/api/rawprep/benchmark/report",
        params={"output_dir": "benchmarks/route_measured", "output_root": "outputs"},
    )
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["status"] == "measured"
    assert report_payload["timing"]["status"] == "measured"
    assert report_payload["fallback_behavior"]["fallback_mode_counts"] == {"guarded_merge": 1}

    health_response = client.get("/api/rawprep/benchmark/foundation", params={"output_root": "outputs"})
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["ok"] is True
    assert health_payload["status"] == "measured_ready"


def test_rawprep_benchmark_scaffold_route_returns_preview(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    source_root = _write_scaffold_source_tree(tmp_path)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/scaffold",
        json={
            "mode": "tri_raw",
            "source_root": str(source_root),
            "output_root": "outputs",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_count"] == 1
    assert payload["bucket_ids"] == ["static_hdr"]
    assert payload["populated_bucket_ids"] == ["static_hdr"]
    assert payload["missing_bucket_ids"] == []


def test_rawprep_benchmark_scaffold_route_can_merge_preserving_existing_manifest_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_scaffold.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    manifest_path = tmp_path / "PROJECT_FOUNDATION" / "SINGLE_RAW_GOLD_SET_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "carry_forward",
                        "raw_path": "samples/manual/input.dng",
                        "benchmark_result_path": "outputs/manual/carry_forward.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    source_root = tmp_path / "benchmark_sources" / "single_raw"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "fresh_scene.CR3").write_bytes(b"raw")

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/scaffold",
        json={
            "mode": "single_raw",
            "source_root": str(source_root),
            "output_root": "outputs",
            "manifest_merge_mode": "merge_preserve_existing",
            "write_manifest": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest_merge_mode"] == "merge_preserve_existing"
    assert payload["preserved_existing_sample_count"] == 1
    assert payload["added_sample_count"] == 1

    merged_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample_ids = [entry["sample_id"] for entry in merged_manifest["samples"]]
    assert sample_ids == ["fresh_scene", "carry_forward"]


def test_rawprep_benchmark_foundation_route_keeps_pending_measurements_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_pending_benchmark_manifests_and_results(tmp_path)

    client = TestClient(app)
    response = client.get("/api/rawprep/benchmark/foundation", params={"output_root": "outputs"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "measurement_incomplete"
    assert payload["single_raw_measured_sample_count"] == 0
    assert payload["tri_raw_measured_sample_count"] == 0


def test_rawprep_benchmark_gate_route_returns_release_gate(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_benchmark_manifests_and_results(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/route_gate")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/route_gate")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/route_gate")

    client = TestClient(app)
    create_response = client.post(
        "/api/rawprep/benchmark",
        json={
            "output_dir": "benchmarks/route_gate",
            "output_root": "outputs",
            "label": "route_gate",
        },
    )
    assert create_response.status_code == 200

    gate_response = client.get(
        "/api/rawprep/benchmark/gate",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert gate_response.status_code == 200
    payload = gate_response.json()
    assert payload["ready_for_default_review"] is True
    assert payload["status"] == "ready_for_default_review"
    assert payload["runpod_smoke_status"] == "passed"

    smoke_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert smoke_response.status_code == 200
    smoke_payload = smoke_response.json()
    assert smoke_payload["status"] == "passed"

    create_smoke_response = client.post(
        "/api/rawprep/benchmark/runpod-smoke",
        json={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert create_smoke_response.status_code == 200
    create_smoke_payload = create_smoke_response.json()
    assert create_smoke_payload["smoke_path"].endswith("rawprep_runpod_smoke.json")

    smoke_artifact_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke/artifact",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert smoke_artifact_response.status_code == 200
    smoke_artifact_payload = smoke_artifact_response.json()
    assert smoke_artifact_payload["status"] == "passed"

    create_gate_response = client.post(
        "/api/rawprep/benchmark/gate",
        json={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert create_gate_response.status_code == 200
    create_gate_payload = create_gate_response.json()
    assert create_gate_payload["gate_path"].endswith("rawprep_release_gate.json")

    artifact_response = client.get(
        "/api/rawprep/benchmark/gate/artifact",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "ready_for_default_review"

    review_response = client.get(
        "/api/rawprep/benchmark/review",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["status"] == "ready_for_human_review"
    assert review_payload["ready_for_human_review"] is True
    assert review_payload["artifact_presence"]["runpod_smoke"] is True
    assert review_payload["artifact_presence"]["local_e2e_smoke"] is True
    assert review_payload["artifact_presence"]["local_recovery_smoke"] is True
    assert review_payload["artifact_presence"]["local_ui_language_smoke"] is True
    assert review_payload["local_e2e_smoke_status"] == "passed"
    assert review_payload["local_recovery_smoke_status"] == "passed"
    assert review_payload["local_ui_language_smoke_status"] == "passed"

    create_review_response = client.post(
        "/api/rawprep/benchmark/review",
        json={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert create_review_response.status_code == 200
    create_review_payload = create_review_response.json()
    assert create_review_payload["review_path"].endswith("rawprep_release_review.json")

    review_artifact_response = client.get(
        "/api/rawprep/benchmark/review/artifact",
        params={"output_dir": "benchmarks/route_gate", "output_root": "outputs"},
    )
    assert review_artifact_response.status_code == 200
    review_artifact_payload = review_artifact_response.json()
    assert review_artifact_payload["status"] == "ready_for_human_review"
    assert review_artifact_payload["local_e2e_smoke_status"] == "passed"
    assert review_artifact_payload["local_recovery_smoke_status"] == "passed"
    assert review_artifact_payload["local_ui_language_smoke_status"] == "passed"


def test_rawprep_benchmark_runpod_smoke_plan_routes_materialize_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    sample_root = tmp_path / "benchmark" / "samples" / "single_raw" / "route_sample"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "input.CR3").write_bytes(b"raw")
    (tmp_path / "benchmark" / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_sample",
                        "raw_path": "benchmark/samples/single_raw/route_sample/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/route_sample.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)

    preview_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-plan",
        params={"output_dir": "benchmarks/runpod_plan", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "ready"
    assert preview_payload["selected_sample_id"] == "route_sample"
    assert preview_payload["runpod_sample_raw_path"] == "/workspace/DreamCatcher/benchmark/samples/single_raw/route_sample/input.CR3"

    create_response = client.post(
        "/api/rawprep/benchmark/runpod-smoke-plan",
        json={"output_dir": "benchmarks/runpod_plan", "output_root": "outputs"},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["plan_path"].endswith("rawprep_runpod_smoke_plan.json")

    artifact_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-plan/artifact",
        params={"output_dir": "benchmarks/runpod_plan", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "ready"
    assert "--sample-raw /workspace/DreamCatcher/benchmark/samples/single_raw/route_sample/input.CR3" in artifact_payload["command_preview"]


def test_rawprep_benchmark_runpod_smoke_stage_routes_materialize_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    sample_root = tmp_path / "benchmark" / "samples" / "single_raw" / "route_sample"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "input.CR3").write_bytes(b"raw")
    (tmp_path / "benchmark" / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_sample",
                        "raw_path": "benchmark/samples/single_raw/route_sample/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/route_sample.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)

    preview_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-stage",
        params={"output_dir": "benchmarks/runpod_stage", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "ready"
    assert preview_payload["archive_created"] is False
    assert preview_payload["bundle_relative_paths"] == ["benchmark/samples/single_raw/route_sample/input.CR3"]

    create_response = client.post(
        "/api/rawprep/benchmark/runpod-smoke-stage",
        json={"output_dir": "benchmarks/runpod_stage", "output_root": "outputs"},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["archive_created"] is True
    assert create_payload["stage_record_path"].endswith("rawprep_runpod_smoke_stage.json")
    assert create_payload["archive_path"].endswith("rawprep_runpod_smoke_sample_bundle.zip")

    artifact_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-stage/artifact",
        params={"output_dir": "benchmarks/runpod_stage", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["archive_created"] is True
    assert "zipfile.ZipFile" in artifact_payload["runpod_extract_command"]
    assert "/workspace/rawprep_runpod_smoke_sample_bundle.zip" in artifact_payload["runpod_extract_command"]
    assert "/workspace/DreamCatcher" in artifact_payload["runpod_extract_command"]


def test_rawprep_benchmark_runpod_smoke_handoff_routes_materialize_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_plan.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_stage.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke_handoff.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_release_bundle_manifest(tmp_path)
    sample_root = tmp_path / "benchmark" / "samples" / "single_raw" / "route_sample"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "input.CR3").write_bytes(b"raw")
    _write_release_bundle_zip(tmp_path)
    (tmp_path / "benchmark" / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_sample",
                        "raw_path": "benchmark/samples/single_raw/route_sample/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/route_sample.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)

    preview_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-handoff",
        params={"output_dir": "benchmarks/runpod_handoff", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "missing_smoke_bundle"
    assert preview_payload["official_app_bundle_exists"] is True
    assert preview_payload["smoke_bundle_exists"] is False

    create_response = client.post(
        "/api/rawprep/benchmark/runpod-smoke-handoff",
        json={"output_dir": "benchmarks/runpod_handoff", "output_root": "outputs"},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["status"] == "ready_for_upload"
    assert create_payload["smoke_bundle_exists"] is True
    assert create_payload["handoff_path"].endswith("rawprep_runpod_smoke_handoff.json")
    assert create_payload["runbook_markdown_path"].endswith("rawprep_runpod_smoke_handoff.md")
    assert create_payload["runbook_script_path"].endswith("rawprep_runpod_smoke_handoff.sh")

    artifact_response = client.get(
        "/api/rawprep/benchmark/runpod-smoke-handoff/artifact",
        params={"output_dir": "benchmarks/runpod_handoff", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["official_app_bundle_name"] == "DreamCatcher.zip"
    assert artifact_payload["embedded_smoke_bundle_exists"] is True
    assert [item["runpod_path"] for item in artifact_payload["uploads"]] == ["/workspace/DreamCatcher.zip"]


def test_rawprep_benchmark_local_recovery_smoke_routes_materialize_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_recovery_smoke.repo_root", lambda: tmp_path)

    client = TestClient(app)

    preview_response = client.get(
        "/api/rawprep/benchmark/local-recovery-smoke",
        params={"output_dir": "benchmarks/route_local_recovery", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "passed"
    assert preview_payload["blocked_without_package"]["ready_for_provider_pause"] is False
    assert preview_payload["ready_with_package"]["ready_for_provider_pause"] is True

    create_response = client.post(
        "/api/rawprep/benchmark/local-recovery-smoke",
        json={"output_dir": "benchmarks/route_local_recovery", "output_root": "outputs"},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["smoke_path"].endswith("rawprep_local_recovery_smoke.json")
    assert create_payload["status"] == "passed"

    artifact_response = client.get(
        "/api/rawprep/benchmark/local-recovery-smoke/artifact",
        params={"output_dir": "benchmarks/route_local_recovery", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "passed"
    assert artifact_payload["ready_with_package"]["package_archive_path"].endswith(".zip")


def test_rawprep_benchmark_local_ui_language_smoke_routes_materialize_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_local_ui_language_smoke.repo_root", lambda: tmp_path)
    _write_local_ui_surface_tree(tmp_path)

    client = TestClient(app)

    preview_response = client.get(
        "/api/rawprep/benchmark/local-ui-language-smoke",
        params={"output_dir": "benchmarks/route_local_ui_language", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "passed"
    assert preview_payload["missing_files"] == []
    assert preview_payload["findings"] == []

    create_response = client.post(
        "/api/rawprep/benchmark/local-ui-language-smoke",
        json={"output_dir": "benchmarks/route_local_ui_language", "output_root": "outputs"},
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["smoke_path"].endswith("rawprep_local_ui_language_smoke.json")
    assert create_payload["status"] == "passed"

    artifact_response = client.get(
        "/api/rawprep/benchmark/local-ui-language-smoke/artifact",
        params={"output_dir": "benchmarks/route_local_ui_language", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "passed"
    assert artifact_payload["scanned_file_count"] == len(_UI_LANGUAGE_SURFACE_FILES)


def test_rawprep_benchmark_default_decision_route_surfaces_hold_status(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_measured_benchmark_manifests_and_results(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/route_default_decision")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/route_default_decision")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/route_default_decision")

    client = TestClient(app)

    create_response = client.post(
        "/api/rawprep/benchmark/default-decision",
        json={
            "output_dir": "benchmarks/route_default_decision",
            "output_root": "outputs",
            "label": "route_default_decision",
        },
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["benchmark_evidence_ready"] is True
    assert create_payload["release_promotion_ready"] is False
    assert create_payload["status"] == "hold_runpod_smoke_pending"
    assert create_payload["local_ui_language_smoke_status"] == "passed"
    assert create_payload["decision_path"].endswith("rawprep_default_engine_decision.json")

    preview_response = client.get(
        "/api/rawprep/benchmark/default-decision",
        params={"output_dir": "benchmarks/route_default_decision", "output_root": "outputs"},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["status"] == "hold_runpod_smoke_pending"
    assert preview_payload["benchmark_evidence_ready"] is True

    artifact_response = client.get(
        "/api/rawprep/benchmark/default-decision/artifact",
        params={"output_dir": "benchmarks/route_default_decision", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["status"] == "hold_runpod_smoke_pending"
    assert artifact_payload["local_ui_language_smoke_status"] == "passed"


def test_rawprep_benchmark_measurement_route_writes_official_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-07",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_single",
                        "raw_path": "samples/route/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/route_single.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-07", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    client = TestClient(app)

    read_before = client.get(
        "/api/rawprep/benchmark/measurement",
        params={"sample_id": "route_single", "output_root": "outputs"},
    )
    assert read_before.status_code == 200
    assert read_before.json()["measurement_exists"] is False

    write_response = client.post(
        "/api/rawprep/benchmark/measurement",
        json={
            "sample_id": "route_single",
            "output_root": "outputs",
            "timing_ms": 902.0,
            "metrics": {"noise_reduction": 0.9},
            "notes": ["route write"],
        },
    )
    assert write_response.status_code == 200
    write_payload = write_response.json()
    assert write_payload["measurement_exists"] is True
    assert write_payload["measurement_status"] == "measured"
    assert write_payload["scope"] == "single_raw"

    measurement_path = tmp_path / "outputs" / "_benchmark_results" / "route_single.json"
    stored_payload = json.loads(measurement_path.read_text(encoding="utf-8"))
    assert stored_payload["sample_id"] == "route_single"
    assert stored_payload["metrics"]["noise_reduction"] == 0.9

    read_after = client.get(
        "/api/rawprep/benchmark/measurement",
        params={"sample_id": "route_single", "output_root": "outputs"},
    )
    assert read_after.status_code == 200
    assert read_after.json()["measurement_exists"] is True


def test_rawprep_benchmark_measurement_route_derives_result_from_single_raw_report(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_single_report",
                        "raw_path": "samples/route_single_report/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/route_single_report.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = _write_single_raw_report(tmp_path / "outputs", "route_single_report", planner_total_ms=618.0)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/measurement/from-single-raw-report",
        json={
            "sample_id": "route_single_report",
            "report_path": str(report_path.relative_to(tmp_path)),
            "output_root": "outputs",
            "notes": ["route derived"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_exists"] is True
    assert payload["measurement_status"] == "measured"
    assert payload["timing_ms"] == 618.0
    assert payload["metrics"] == {
        "noise_reduction": 0.41,
        "detail_preservation": 0.61,
        "color_stability": 0.91,
    }
    assert payload["fallback_mode"] == "fast_runtime_direct_preview"
    assert payload["summary"] == "Official benchmark measurement evidence was derived from a SingleRaw report timing artifact."

    measurement_path = tmp_path / "outputs" / "_benchmark_results" / "route_single_report.json"
    stored_payload = json.loads(measurement_path.read_text(encoding="utf-8"))
    assert stored_payload["timing_ms"] == 618.0
    assert stored_payload["metrics"]["noise_reduction"] == 0.41
    assert any(note.startswith("Derived from SingleRaw report:") for note in stored_payload["notes"])
    assert "Resolved mode: fast" in stored_payload["notes"]
    assert stored_payload["notes"][-1] == "route derived"


def test_rawprep_benchmark_measurement_batch_route_derives_results_from_single_raw_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_batch_report",
                        "raw_path": "samples/route_batch_report/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/route_batch_report.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_path = _write_single_raw_report(tmp_path / "outputs", "route_batch_report", planner_total_ms=640.0)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/measurement/batch/from-single-raw-report",
        json={
            "output_root": "outputs",
            "entries": [
                {
                    "sample_id": "route_batch_report",
                    "report_path": str(report_path.relative_to(tmp_path)),
                    "notes": ["batch bridge"],
                },
                {
                    "sample_id": "missing_batch_report",
                    "report_path": "outputs/missing/report.json",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entry_count"] == 2
    assert payload["written_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["success_sample_ids"] == ["route_batch_report"]
    assert payload["issues"][0]["code"] == "measurement_report_bridge_failed"

    stored_payload = json.loads(
        (tmp_path / "outputs" / "_benchmark_results" / "route_batch_report.json").read_text(encoding="utf-8")
    )
    assert stored_payload["timing_ms"] == 640.0
    assert stored_payload["notes"][-1] == "batch bridge"


def test_rawprep_benchmark_single_raw_run_route_materializes_local_sample(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_single_raw_run.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    benchmark_root = tmp_path / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "BENCHMARK_CATALOG.json").write_text(
        (foundation / "BENCHMARK_CATALOG.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sample_root = tmp_path / "benchmark" / "samples" / "single_raw" / "route_runner"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "IMG_1001.CR3").write_bytes(b"raw")
    _write_textured_preview(sample_root / "IMG_1001.JPG")

    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_runner",
                        "raw_path": "benchmark/samples/single_raw/route_runner/IMG_1001.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results_staging/single_raw/route_runner.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (benchmark_root / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/single-raw/run",
        json={
            "output_root": "outputs",
            "run_root": "_benchmark_runs/single_raw",
            "mode_preference": "fast",
            "benchmark_output_dir": "benchmarks/route_runner_single_raw",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_count"] == 1
    assert payload["measured_count"] == 1
    assert payload["benchmark_status"] == "partially_populated"
    assert payload["samples"][0]["sample_id"] == "route_runner"
    assert payload["samples"][0]["measurement_status"] == "measured"
    assert payload["samples"][0]["metrics"]["noise_reduction"] >= 0

    measurement_payload = json.loads(
        (tmp_path / "outputs" / "_benchmark_results_staging" / "single_raw" / "route_runner.json").read_text(encoding="utf-8")
    )
    assert measurement_payload["status"] == "measured"
    assert measurement_payload["metrics"]["detail_preservation"] > 0
    assert measurement_payload["metrics"]["color_stability"] > 0


def test_rawprep_benchmark_tri_raw_run_route_materializes_local_sample(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_tri_raw_run.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    benchmark_root = tmp_path / "benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-09",
                "single_raw": {
                    "gold_set": {
                        "defined": True,
                        "status": "partially_populated",
                        "sample_count": 0,
                        "evaluation_axes": ["noise_reduction", "detail_preservation", "processing_time"],
                    }
                },
                "tri_raw": {
                    "bucket_definitions": [
                        {
                            "bucket_id": "static_hdr",
                            "label": "Static HDR",
                            "status": "partially_populated",
                            "sample_count": 1,
                            "hard_case": False,
                            "traits": ["static_scene"],
                            "required_report_sections": ["hdr_gain", "deghost", "timing"],
                        }
                    ],
                    "hard_case_bucket": {
                        "defined": True,
                        "member_bucket_ids": [],
                    },
                },
                "report_template": {
                    "defined": True,
                    "sections": ["dataset_overview", "bucket_findings", "open_risks"],
                },
                "product_metrics": {
                    "compare_decision_logging": {
                        "defined": True,
                        "storage": [
                            "04_compare/decisions/compare_decision_*.json",
                            "_compare_learning/compare_decisions.jsonl",
                        ],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        (benchmark_root / "BENCHMARK_CATALOG.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    sample_root = tmp_path / "benchmark" / "samples" / "tri_raw" / "static_hdr" / "route_tri_runner"
    sample_root.mkdir(parents=True, exist_ok=True)
    source_paths: list[str] = []
    for index, name in enumerate(("IMG_2001", "IMG_2002", "IMG_2003"), start=1):
        raw_path = sample_root / f"{name}.CR3"
        raw_path.write_bytes(f"raw-{index}".encode("utf-8"))
        _write_textured_preview(sample_root / f"{name}.JPG")
        source_paths.append(f"benchmark/samples/tri_raw/static_hdr/route_tri_runner/{raw_path.name}")

    (benchmark_root / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "partially_populated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (benchmark_root / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "static_hdr__route_tri_runner",
                        "bucket_id": "static_hdr",
                        "source_paths": source_paths,
                        "benchmark_result_path": "outputs/_benchmark_results_staging/tri_raw/static_hdr/static_hdr__route_tri_runner.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/tri-raw/run",
        json={
            "output_root": "outputs",
            "run_root": "_benchmark_runs/tri_raw",
            "requested_reference_policy": "auto",
            "benchmark_output_dir": "benchmarks/route_runner_tri_raw",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed_count"] == 1
    assert payload["measured_count"] == 1
    assert payload["benchmark_status"] == "partially_populated"
    assert payload["samples"][0]["sample_id"] == "static_hdr__route_tri_runner"
    assert payload["samples"][0]["measurement_status"] == "measured"
    assert payload["samples"][0]["metrics"]["hdr_gain_coverage"] >= 0
    assert payload["samples"][0]["metrics"]["mean_confidence"] >= 0

    measurement_payload = json.loads(
        (
            tmp_path
            / "outputs"
            / "_benchmark_results_staging"
            / "tri_raw"
            / "static_hdr"
            / "static_hdr__route_tri_runner.json"
        ).read_text(encoding="utf-8")
    )
    assert measurement_payload["status"] == "measured"
    assert measurement_payload["metrics"]["alignment_pressure_score"] >= 0


def test_rawprep_benchmark_measurement_report_scaffold_route_builds_batch_input(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_measurement_report_scaffold.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "route_report_scaffold",
                        "raw_path": "samples/route_report_scaffold/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/route_report_scaffold.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-09", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _write_single_raw_report(tmp_path / "outputs", "route_report_scaffold", planner_total_ms=501.0)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/measurement/report-scaffold",
        json={
            "output_root": "outputs",
            "write_batch_input": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest_sample_count"] == 1
    assert payload["entry_count"] == 1
    assert payload["wrote_batch_input"] is True
    assert payload["entries"][0]["sample_id"] == "route_report_scaffold"

    batch_path = Path(payload["batch_input_path"])
    assert batch_path.exists()
    batch_payload = json.loads(batch_path.read_text(encoding="utf-8").strip())
    assert batch_payload["sample_id"] == "route_report_scaffold"
    assert batch_payload["report_path"].endswith("route_report_scaffold/report.json")


def test_rawprep_benchmark_measurement_batch_route_reports_successes_and_failures(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-08",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "batch_single",
                        "raw_path": "samples/batch/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/batch_single.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps({"manifest_version": "2026-04-08", "status": "unpopulated", "samples": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/measurement/batch",
        json={
            "output_root": "outputs",
            "entries": [
                {
                    "sample_id": "batch_single",
                    "timing_ms": 845.0,
                    "metrics": {"noise_reduction": 0.89},
                },
                {
                    "sample_id": "missing_batch_sample",
                    "timing_ms": 999.0,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entry_count"] == 2
    assert payload["written_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["success_sample_ids"] == ["batch_single"]
    assert payload["issues"][0]["sample_id"] == "missing_batch_sample"


def test_rawprep_benchmark_packet_route_assembles_release_packet(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet")

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-08",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "packet_single",
                        "raw_path": "samples/packet/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/packet_single.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-08",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "packet_tri",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/packet_tri/frame_01.dng",
                            "samples/packet_tri/frame_02.dng",
                            "samples/packet_tri/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/packet_tri.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report_path = _write_single_raw_report(tmp_path / "outputs", "packet_single", planner_total_ms=611.0)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/packet",
        json={
            "output_dir": "benchmarks/route_packet",
            "output_root": "outputs",
            "label": "route_packet",
            "measurement_report_entries": [
                {
                    "sample_id": "packet_single",
                    "report_path": str(report_path.relative_to(tmp_path)),
                    "notes": ["route packet bridge"],
                }
            ],
            "measurement_entries": [
                {
                    "sample_id": "packet_tri",
                    "timing_ms": 1335.0,
                    "metrics": {"hdr_gain": 0.83},
                    "fallback_mode": "guarded_merge",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_batch_applied"] is True
    assert payload["measurement_report_batch_applied"] is True
    assert payload["measurement_report_entry_count"] == 1
    assert payload["measurement_written_count"] == 2
    assert payload["benchmark_status"] == "measured"
    assert payload["runpod_smoke_status"] == "passed"
    assert payload["local_e2e_smoke_status"] == "passed"
    assert payload["local_recovery_smoke_status"] == "passed"
    assert payload["local_ui_language_smoke_status"] == "passed"
    assert payload["release_gate_status"] == "ready_for_default_review"
    assert payload["release_review_status"] == "ready_for_human_review"
    assert payload["ready_for_human_review"] is True
    assert payload["packet_path"].endswith("rawprep_release_packet.json")
    assert payload["release_review_path"].endswith("rawprep_release_review.json")

    artifact_response = client.get(
        "/api/rawprep/benchmark/packet/artifact",
        params={"output_dir": "benchmarks/route_packet", "output_root": "outputs"},
    )
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["packet_path"].endswith("rawprep_release_packet.json")
    assert artifact_payload["ready_for_human_review"] is True
    assert artifact_payload["local_e2e_smoke_status"] == "passed"
    assert artifact_payload["local_recovery_smoke_status"] == "passed"
    assert artifact_payload["local_ui_language_smoke_status"] == "passed"

    stored_single_payload = json.loads(
        (tmp_path / "outputs" / "_benchmark_results" / "packet_single.json").read_text(encoding="utf-8")
    )
    assert stored_single_payload["timing_ms"] == 611.0
    assert stored_single_payload["notes"][-1] == "route packet bridge"


def test_rawprep_benchmark_packet_route_can_auto_scaffold_single_raw_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_measurement_report_scaffold.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet_auto")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet_auto")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/route_packet_auto")

    foundation = tmp_path / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "packet_auto_single",
                        "raw_path": "samples/packet_auto_single/input.CR3",
                        "benchmark_result_path": "outputs/_benchmark_results/packet_auto_single.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (foundation / "TRI_RAW_BUCKET_SAMPLE_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-09",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "packet_auto_tri",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/packet_auto_tri/frame_01.dng",
                            "samples/packet_auto_tri/frame_02.dng",
                            "samples/packet_auto_tri/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/packet_auto_tri.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_single_raw_report(tmp_path / "outputs", "packet_auto_single", planner_total_ms=590.0)

    client = TestClient(app)
    response = client.post(
        "/api/rawprep/benchmark/packet",
        json={
            "output_dir": "benchmarks/route_packet_auto",
            "output_root": "outputs",
            "label": "route_packet_auto",
            "measurement_report_scaffold_enabled": True,
            "write_measurement_report_batch_input": True,
            "measurement_report_batch_input_path": "outputs/_benchmark_inputs/route_packet_auto.jsonl",
            "measurement_entries": [
                {
                    "sample_id": "packet_auto_tri",
                    "timing_ms": 1335.0,
                    "metrics": {"hdr_gain": 0.83},
                    "fallback_mode": "guarded_merge",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_report_scaffold_applied"] is True
    assert payload["measurement_report_scaffold_entry_count"] == 1
    assert payload["measurement_report_entry_count"] == 1
    assert payload["measurement_report_batch_applied"] is True
    assert payload["measurement_report_scaffold_batch_input_path"].endswith("route_packet_auto.jsonl")
    assert payload["measurement_written_count"] == 2
    assert payload["local_e2e_smoke_status"] == "passed"
    assert payload["local_recovery_smoke_status"] == "passed"
    assert payload["local_ui_language_smoke_status"] == "passed"
    assert payload["ready_for_human_review"] is True

    batch_path = Path(payload["measurement_report_scaffold_batch_input_path"])
    assert batch_path.exists()
    batch_payload = json.loads(batch_path.read_text(encoding="utf-8").strip())
    assert batch_payload["sample_id"] == "packet_auto_single"
