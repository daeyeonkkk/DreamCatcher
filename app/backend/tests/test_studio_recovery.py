import json
from pathlib import Path

from PIL import Image

from app.core.studio_compare_memory import record_compare_decision
from app.core.studio_recovery import (
    build_session_recovery_packet,
    load_session_recovery_packet,
)


def _write_session_fixture(output_root: Path, *, session_id: str = "session_demo") -> Path:
    session_root = output_root / session_id
    staged_dir = session_root / "00_input"
    staged_dir.mkdir(parents=True, exist_ok=True)

    primary_path = staged_dir / "frame_a.jpg"
    candidate_path = staged_dir / "frame_b.jpg"
    Image.new("RGB", (12, 12), color=(200, 80, 40)).save(primary_path)
    Image.new("RGB", (12, 12), color=(40, 120, 200)).save(candidate_path)

    intake_payload = {
        "session_id": session_id,
        "session_root": str(session_root),
        "manifest_path": str(session_root / "studio_intake.json"),
        "entry_mode": "direct_edit_image",
        "entry_preference": "auto",
        "rawprep_optional": True,
        "alternate_modes": [],
        "staged_assets": [
            {
                "source_path": str(primary_path),
                "staged_path": str(primary_path),
                "file_name": primary_path.name,
                "suffix": primary_path.suffix,
                "kind": "image",
            },
            {
                "source_path": str(candidate_path),
                "staged_path": str(candidate_path),
                "file_name": candidate_path.name,
                "suffix": candidate_path.suffix,
                "kind": "image",
            },
        ],
        "editable_asset_path": str(primary_path),
        "single_raw_plan": None,
        "dreamisp_plan": None,
        "rawprep_request": None,
        "notes": [],
    }
    (session_root / "studio_intake.json").write_text(json.dumps(intake_payload), encoding="utf-8")
    (session_root / "session_catalog.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "output_root": str(output_root),
                "rating": 5,
                "pick_status": "selected",
                "review_status": "proofing",
                "keywords": ["hero"],
                "updated_at": "2026-04-08T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (session_root / "rawprep_job.json").write_text(
        json.dumps(
            {
                "job_id": "rawprep_demo",
                "session_id": session_id,
                "status": "done",
                "group_reports": [],
            }
        ),
        encoding="utf-8",
    )
    studio_job_root = session_root / "03_ai" / "jobs" / "job_demo"
    studio_job_root.mkdir(parents=True, exist_ok=True)
    (studio_job_root / "studio_job.json").write_text(
        json.dumps(
            {
                "job_id": "job_demo",
                "session_id": session_id,
                "status": "done",
                "tool": "retouch",
                "outputs": [{"path": str(primary_path), "label": "retouch_result"}],
            }
        ),
        encoding="utf-8",
    )

    record_compare_decision(
        session_id=session_id,
        output_root=str(output_root),
        tool="compare",
        select_path=str(primary_path),
        candidate_path=str(candidate_path),
        winner_path=str(primary_path),
        action="keep_select",
        note="keep the cleaner frame",
    )
    return session_root


def test_build_session_recovery_packet_materializes_package_and_metadata(tmp_path):
    output_root = tmp_path / "outputs"
    _write_session_fixture(output_root)

    packet = build_session_recovery_packet(
        session_id="session_demo",
        output_root=str(output_root),
        preset="master_archive",
        create_package=True,
    )

    assert packet.ready_for_result_retrieval is True
    assert packet.ready_for_metadata_retrieval is True
    assert packet.ready_for_provider_pause is True
    assert packet.compare_decision_count == 1
    assert packet.package_archive_path is not None
    assert Path(packet.package_archive_path).exists()
    assert Path(packet.metadata_snapshot_path).exists()

    metadata_payload = json.loads(Path(packet.metadata_snapshot_path).read_text(encoding="utf-8"))
    assert metadata_payload["session_id"] == "session_demo"
    assert metadata_payload["compare_decisions"]["count"] == 1
    assert metadata_payload["catalog"]["pick_status"] == "selected"

    loaded = load_session_recovery_packet("session_demo", output_root=str(output_root))
    assert loaded.session_id == "session_demo"
    assert loaded.package_archive_path == packet.package_archive_path
