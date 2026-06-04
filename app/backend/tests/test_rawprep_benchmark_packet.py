import json
from pathlib import Path

from app.core.rawprep_benchmark_local_ui_language_smoke import _UI_LANGUAGE_SURFACE_FILES
from app.core.rawprep_benchmark_packet import (
    RawPrepBenchmarkPacketRequest,
    load_rawprep_benchmark_packet,
    write_rawprep_benchmark_packet,
)


def _write_benchmark_foundation(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    foundation.mkdir(parents=True, exist_ok=True)
    (foundation / "BENCHMARK_CATALOG.json").write_text(
        json.dumps(
            {
                "catalog_version": "2026-04-08",
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


def _write_partially_populated_manifests(repo_root: Path) -> None:
    foundation = repo_root / "PROJECT_FOUNDATION"
    (foundation / "SINGLE_RAW_GOLD_SET_MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "2026-04-08",
                "status": "partially_populated",
                "samples": [
                    {
                        "sample_id": "single_packet",
                        "raw_path": "samples/single_packet/input.dng",
                        "benchmark_result_path": "outputs/_benchmark_results/single_packet.json",
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
                        "sample_id": "tri_packet",
                        "bucket_id": "static_hdr",
                        "source_paths": [
                            "samples/tri_packet/frame_01.dng",
                            "samples/tri_packet/frame_02.dng",
                            "samples/tri_packet/frame_03.dng",
                        ],
                        "benchmark_result_path": "outputs/_benchmark_results/tri_packet.json",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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
                    "sample_id": "single_packet",
                    "session_id": "local_e2e_single_raw_single_packet",
                    "session_root": "outputs/_benchmark_runs/local_e2e/single_raw/local_e2e_single_raw_single_packet",
                    "entry_mode": "direct_edit_raw",
                    "status": status,
                    "ready_for_edit_ui": status == "passed",
                    "issues": [],
                    "summary": "single raw local e2e",
                },
                "tri_raw": {
                    "sample_id": "tri_packet",
                    "session_id": "local_e2e_tri_raw_tri_packet",
                    "session_root": "outputs/_benchmark_runs/local_e2e/tri_raw/local_e2e_tri_raw_tri_packet",
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


def _write_single_raw_report(output_root: Path, sample_id: str, *, planner_total_ms: float = 566.0) -> Path:
    report_path = output_root / "session_demo" / "01_single_raw" / sample_id / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "resolved_mode": "fast",
                "runtime_profile": "sensor_fast_preview_v1",
                "status": "materialized",
                "timing_summary": f"Planner total: {planner_total_ms}ms",
                "timing_report": {
                    "planner_total_ms": planner_total_ms,
                    "total_ms": planner_total_ms + 44.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def test_write_rawprep_benchmark_packet_applies_batch_and_builds_review(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_partially_populated_manifests(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/packet_ready")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/packet_ready")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/packet_ready")

    packet = write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir="benchmarks/packet_ready",
            output_root="outputs",
            label="packet_ready",
            measurement_entries=[
                {
                    "sample_id": "single_packet",
                    "timing_ms": 820.0,
                    "metrics": {"noise_reduction": 0.91},
                },
                {
                    "sample_id": "tri_packet",
                    "timing_ms": 1310.0,
                    "metrics": {"hdr_gain": 0.84},
                    "fallback_mode": "guarded_merge",
                },
            ],
        )
    )

    assert packet.measurement_batch_applied is True
    assert packet.measurement_written_count == 2
    assert packet.measurement_skipped_count == 0
    assert packet.benchmark_status == "measured"
    assert packet.foundation_status == "measured_ready"
    assert packet.runpod_smoke_status == "passed"
    assert packet.local_e2e_smoke_status == "passed"
    assert packet.local_recovery_smoke_status == "passed"
    assert packet.local_ui_language_smoke_status == "passed"
    assert packet.release_gate_status == "ready_for_default_review"
    assert packet.release_review_status == "ready_for_human_review"
    assert packet.ready_for_default_review is True
    assert packet.ready_for_human_review is True
    assert packet.packet_path is not None and Path(packet.packet_path).exists()
    assert packet.benchmark_record_path is not None and Path(packet.benchmark_record_path).exists()
    assert packet.release_review_path is not None and Path(packet.release_review_path).exists()
    loaded = load_rawprep_benchmark_packet("benchmarks/packet_ready", output_root="outputs")
    assert loaded.packet_path == packet.packet_path
    assert loaded.ready_for_human_review is True


def test_write_rawprep_benchmark_packet_applies_single_raw_report_bridge_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_partially_populated_manifests(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/packet_report_bridge")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/packet_report_bridge")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/packet_report_bridge")

    report_path = _write_single_raw_report(tmp_path / "outputs", "single_packet", planner_total_ms=602.0)

    packet = write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir="benchmarks/packet_report_bridge",
            output_root="outputs",
            label="packet_report_bridge",
            measurement_report_entries=[
                {
                    "sample_id": "single_packet",
                    "report_path": str(report_path.relative_to(tmp_path)),
                    "notes": ["packet bridge"],
                }
            ],
            measurement_entries=[
                {
                    "sample_id": "tri_packet",
                    "timing_ms": 1310.0,
                    "metrics": {"hdr_gain": 0.84},
                    "fallback_mode": "guarded_merge",
                }
            ],
        )
    )

    assert packet.measurement_report_batch_applied is True
    assert packet.measurement_report_entry_count == 1
    assert packet.measurement_written_count == 2
    assert packet.measurement_skipped_count == 0
    assert packet.benchmark_status == "measured"
    assert packet.local_e2e_smoke_status == "passed"
    assert packet.local_recovery_smoke_status == "passed"
    assert packet.local_ui_language_smoke_status == "passed"
    assert packet.release_review_status == "ready_for_human_review"

    payload = json.loads((tmp_path / "outputs" / "_benchmark_results" / "single_packet.json").read_text(encoding="utf-8"))
    assert payload["timing_ms"] == 602.0
    assert payload["notes"][-1] == "packet bridge"


def test_write_rawprep_benchmark_packet_keeps_skipped_measurements_visible(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_partially_populated_manifests(tmp_path)

    packet = write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir="benchmarks/packet_incomplete",
            output_root="outputs",
            label="packet_incomplete",
            measurement_entries=[
                {
                    "sample_id": "single_packet",
                    "timing_ms": 820.0,
                    "metrics": {"noise_reduction": 0.91},
                },
                {
                    "sample_id": "tri_packet",
                    "timing_ms": 1310.0,
                    "metrics": {"hdr_gain": 0.84},
                },
                {
                    "sample_id": "missing_packet_sample",
                    "timing_ms": 999.0,
                },
            ],
        )
    )

    assert packet.measurement_batch_applied is True
    assert packet.measurement_written_count == 2
    assert packet.measurement_skipped_count == 1
    assert packet.measurement_issues[0].sample_id == "missing_packet_sample"
    assert packet.packet_path is not None and Path(packet.packet_path).exists()
    assert packet.benchmark_status == "measured"
    assert packet.release_review_status == "evidence_incomplete"
    assert packet.ready_for_human_review is False
    assert any("skipped batch measurement entries" in action for action in packet.recommended_actions)


def test_write_rawprep_benchmark_packet_can_auto_scaffold_single_raw_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_service.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_gate.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_runpod_smoke.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_measurement_report_scaffold.repo_root", lambda: tmp_path)
    _write_benchmark_foundation(tmp_path)
    _write_partially_populated_manifests(tmp_path)
    _write_runpod_smoke_evidence(tmp_path)
    _write_local_e2e_smoke_evidence(tmp_path, output_dir="benchmarks/packet_auto_scaffold")
    _write_local_recovery_smoke_evidence(tmp_path, output_dir="benchmarks/packet_auto_scaffold")
    _write_local_ui_language_smoke_evidence(tmp_path, output_dir="benchmarks/packet_auto_scaffold")

    _write_single_raw_report(tmp_path / "outputs", "single_packet", planner_total_ms=588.0)

    packet = write_rawprep_benchmark_packet(
        RawPrepBenchmarkPacketRequest(
            output_dir="benchmarks/packet_auto_scaffold",
            output_root="outputs",
            label="packet_auto_scaffold",
            measurement_report_scaffold_enabled=True,
            write_measurement_report_batch_input=True,
            measurement_report_batch_input_path="outputs/_benchmark_inputs/packet_auto_scaffold.jsonl",
            measurement_entries=[
                {
                    "sample_id": "tri_packet",
                    "timing_ms": 1310.0,
                    "metrics": {"hdr_gain": 0.84},
                    "fallback_mode": "guarded_merge",
                }
            ],
        )
    )

    assert packet.measurement_report_scaffold_applied is True
    assert packet.measurement_report_scaffold_entry_count == 1
    assert packet.measurement_report_entry_count == 1
    assert packet.measurement_report_batch_applied is True
    assert packet.measurement_report_scaffold_batch_input_path is not None
    assert Path(packet.measurement_report_scaffold_batch_input_path).exists()
    assert packet.measurement_written_count == 2
    assert packet.measurement_skipped_count == 0
    assert packet.local_e2e_smoke_status == "passed"
    assert packet.local_recovery_smoke_status == "passed"
    assert packet.local_ui_language_smoke_status == "passed"
    assert packet.ready_for_human_review is True

    batch_payload = json.loads(
        Path(packet.measurement_report_scaffold_batch_input_path).read_text(encoding="utf-8").strip()
    )
    assert batch_payload["sample_id"] == "single_packet"

    stored_payload = json.loads((tmp_path / "outputs" / "_benchmark_results" / "single_packet.json").read_text(encoding="utf-8"))
    assert stored_payload["timing_ms"] == 588.0
