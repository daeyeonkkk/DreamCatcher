import json
from pathlib import Path

from PIL import Image

from app.raw_engine_v2.isp.planner import (
    build_dreamisp_handoff_plan,
    materialize_dreamisp_handoff_plan,
)


def test_build_dreamisp_handoff_plan_prefers_preview_proxy_when_available(tmp_path):
    scene_linear_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "scene_linear.tiff"
    preview_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "preview.jpg"
    scene_linear_path.parent.mkdir(parents=True, exist_ok=True)
    scene_linear_path.write_bytes(b"tiff")
    Image.new("RGB", (96, 64), (120, 90, 70)).save(preview_path)

    plan = build_dreamisp_handoff_plan(
        session_root=tmp_path / "outputs" / "session_demo",
        source_stage="single_raw",
        source_item_key="capture_001",
        source_engine_key="dreamraw_one_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
        preview_path=str(preview_path),
        source_report_path=str(scene_linear_path.parent / "report.json"),
        source_diagnostics_manifest_path=str(scene_linear_path.parent / "diagnostics" / "manifest.json"),
    )

    assert plan.engine_key == "dreamisp_v2"
    assert plan.status == "phase1_foundation"
    assert plan.source_stage == "single_raw"
    assert plan.scene_linear_exists is True
    assert plan.preview_exists is True
    assert plan.recommended_editable_source_path == str(preview_path)
    assert plan.render_state["non_destructive"] is True
    assert plan.working_root.endswith(str(Path("02_manual") / "capture_001"))


def test_materialize_dreamisp_handoff_plan_writes_render_state_and_report(tmp_path):
    scene_linear_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "scene_linear.tiff"
    scene_linear_path.parent.mkdir(parents=True, exist_ok=True)
    scene_linear_path.write_bytes(b"tiff")

    plan = build_dreamisp_handoff_plan(
        session_root=tmp_path / "outputs" / "session_demo",
        source_stage="single_raw",
        source_item_key="capture_001",
        source_engine_key="dreamraw_one_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
    )
    materialized = materialize_dreamisp_handoff_plan(plan)

    assert materialized.materialization_status == "handoff_written"
    assert Path(materialized.plan_path).is_file()
    assert Path(materialized.render_state_path).is_file()
    assert Path(materialized.report_path).is_file()

    render_state_payload = json.loads(Path(materialized.render_state_path).read_text(encoding="utf-8"))
    report_payload = json.loads(Path(materialized.report_path).read_text(encoding="utf-8"))
    assert render_state_payload["source"]["scene_linear_path"] == str(scene_linear_path)
    assert render_state_payload["editable"] is True
    assert report_payload["status"] == "handoff_written"
    assert report_payload["handoff_ready"] is True
    assert report_payload["scene_linear_exists"] is True
