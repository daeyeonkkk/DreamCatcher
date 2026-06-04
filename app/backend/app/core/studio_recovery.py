from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .rawprep_contract import build_directory_layout
from .studio_catalog import load_session_catalog
from .studio_compare_memory import collect_compare_decisions
from .studio_files import DeliveryPresetKey, build_delivery_preset_package
from .studio_intake import dump_model, latest_studio_job_payload, load_studio_intake_plan, try_read_json
from .studio_paths import resolve_output_root


class StudioRecoverySourceFile(BaseModel):
    label: str
    path: str
    exists: bool
    required: bool = False


class StudioRecoveryPacket(BaseModel):
    session_id: str
    output_root: str
    created_at: str
    preset: DeliveryPresetKey
    package_archive_path: str | None = None
    package_file_name: str | None = None
    package_file_count: int = 0
    metadata_snapshot_path: str
    metadata_source_files: list[StudioRecoverySourceFile] = Field(default_factory=list)
    compare_decision_count: int = 0
    compare_tool_counts: dict[str, int] = Field(default_factory=dict)
    ready_for_result_retrieval: bool = False
    ready_for_metadata_retrieval: bool = False
    ready_for_provider_pause: bool = False
    issues: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def recovery_directory(session_id: str, *, output_root: str) -> Path:
    layout = build_directory_layout(output_root, session_id)
    directory = Path(layout.export_dir) / "recovery"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def session_recovery_packet_path(session_id: str, *, output_root: str) -> Path:
    return recovery_directory(session_id, output_root=output_root) / "session_recovery_packet.json"


def session_recovery_metadata_path(session_id: str, *, output_root: str) -> Path:
    return recovery_directory(session_id, output_root=output_root) / "session_recovery_metadata.json"


def load_session_recovery_packet(session_id: str, *, output_root: str = "outputs") -> StudioRecoveryPacket:
    path = session_recovery_packet_path(session_id, output_root=output_root)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Session recovery packet was not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StudioRecoveryPacket(**payload)


def _latest_export_archive(export_dir: Path) -> Path | None:
    archives = [
        path
        for path in export_dir.glob("*.zip")
        if path.is_file()
    ]
    if not archives:
        return None
    archives.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
    return archives[0]


def build_session_recovery_packet(
    *,
    session_id: str,
    output_root: str = "outputs",
    preset: DeliveryPresetKey = "master_archive",
    create_package: bool = True,
) -> StudioRecoveryPacket:
    resolved_output_root = str(resolve_output_root(output_root))
    plan = load_studio_intake_plan(session_id, output_root=output_root)
    layout = build_directory_layout(output_root, session_id)
    session_root = Path(layout.session_root)
    export_dir = Path(layout.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    package_payload: dict[str, Any] | None = None
    package_archive_path: Path | None = None
    if create_package:
        package_payload = build_delivery_preset_package(
            session_id=session_id,
            output_root=output_root,
            preset=preset,
            label=f"{preset}_recovery",
            metadata={"recovery_bundle": True},
        )
        archive_path = package_payload.get("archive_path")
        if isinstance(archive_path, str) and archive_path.strip():
            package_archive_path = Path(archive_path)
    else:
        package_archive_path = _latest_export_archive(export_dir)

    rawprep_job_path = session_root / "rawprep_job.json"
    rawprep_payload = try_read_json(rawprep_job_path)
    studio_payload, studio_job_path = latest_studio_job_payload(session_root)
    catalog_payload = load_session_catalog(session_id, output_root=output_root).model_dump()
    compare_root = session_root / "04_compare" / "decisions"
    compare_items, compare_summary = collect_compare_decisions([compare_root])

    metadata_source_files = [
        StudioRecoverySourceFile(
            label="studio_intake_manifest",
            path=str(session_root / "studio_intake.json"),
            exists=(session_root / "studio_intake.json").exists(),
            required=True,
        ),
        StudioRecoverySourceFile(
            label="session_catalog",
            path=str(session_root / "session_catalog.json"),
            exists=(session_root / "session_catalog.json").exists(),
            required=False,
        ),
        StudioRecoverySourceFile(
            label="rawprep_job",
            path=str(rawprep_job_path),
            exists=rawprep_job_path.exists(),
            required=False,
        ),
        StudioRecoverySourceFile(
            label="latest_studio_job",
            path=str(studio_job_path) if studio_job_path is not None else str(session_root / "03_ai" / "jobs"),
            exists=studio_job_path is not None and studio_job_path.exists(),
            required=False,
        ),
        StudioRecoverySourceFile(
            label="compare_decisions",
            path=str(compare_root),
            exists=compare_root.exists(),
            required=False,
        ),
    ]

    metadata_payload = {
        "session_id": session_id,
        "output_root": resolved_output_root,
        "created_at": utc_now_iso(),
        "preset": preset,
        "session_root": str(session_root),
        "package_archive_path": str(package_archive_path) if package_archive_path else None,
        "package_file_count": int(package_payload.get("file_count", 0)) if isinstance(package_payload, dict) else 0,
        "intake_plan": dump_model(plan),
        "catalog": catalog_payload,
        "rawprep_job": rawprep_payload,
        "rawprep_job_path": str(rawprep_job_path) if rawprep_job_path.exists() else None,
        "latest_studio_job": studio_payload,
        "latest_studio_job_path": str(studio_job_path) if studio_job_path is not None else None,
        "compare_decisions": {
            "count": len(compare_items),
            "summary": compare_summary,
            "latest_items": [item.model_dump() for item in compare_items[:16]],
        },
        "available_export_archives": [
            str(path)
            for path in sorted(export_dir.glob("*.zip"), key=lambda item: item.stat().st_mtime_ns, reverse=True)
            if path.is_file()
        ],
        "metadata_source_files": [item.model_dump() for item in metadata_source_files],
    }
    metadata_path = session_recovery_metadata_path(session_id, output_root=output_root)
    metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    issues: list[str] = []
    recommended_actions: list[str] = []
    ready_for_result_retrieval = package_archive_path is not None and package_archive_path.exists()
    ready_for_metadata_retrieval = metadata_path.exists()

    if not ready_for_result_retrieval:
        issues.append("Session recovery package is missing.")
        recommended_actions.append("Build a recovery delivery package before pausing or removing the provider pod.")
    if not ready_for_metadata_retrieval:
        issues.append("Session recovery metadata snapshot is missing.")
        recommended_actions.append("Write the canonical recovery metadata snapshot before pausing the provider pod.")

    packet = StudioRecoveryPacket(
        session_id=session_id,
        output_root=resolved_output_root,
        created_at=utc_now_iso(),
        preset=preset,
        package_archive_path=str(package_archive_path) if package_archive_path else None,
        package_file_name=package_archive_path.name if package_archive_path else None,
        package_file_count=int(package_payload.get("file_count", 0)) if isinstance(package_payload, dict) else 0,
        metadata_snapshot_path=str(metadata_path),
        metadata_source_files=metadata_source_files,
        compare_decision_count=len(compare_items),
        compare_tool_counts=dict(compare_summary.get("tool_counts") or {}),
        ready_for_result_retrieval=ready_for_result_retrieval,
        ready_for_metadata_retrieval=ready_for_metadata_retrieval,
        ready_for_provider_pause=ready_for_result_retrieval and ready_for_metadata_retrieval,
        issues=issues,
        recommended_actions=recommended_actions,
    )
    packet_path = session_recovery_packet_path(session_id, output_root=output_root)
    packet_path.write_text(json.dumps(packet.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return packet
