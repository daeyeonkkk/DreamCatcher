import json
from pathlib import Path

from app.raw_engine_v2.tri_raw.planner import (
    build_tri_raw_foundation_plan,
    materialize_tri_raw_foundation_plan,
)


def test_build_tri_raw_foundation_plan_uses_shared_phase1_layers(tmp_path):
    raw_paths = []
    for index in range(3):
        raw_path = tmp_path / f"frame_{index + 1:03d}.dng"
        raw_path.write_bytes(b"raw")
        raw_paths.append(str(raw_path))

    plan = build_tri_raw_foundation_plan(
        raw_paths,
        bracket_id="bracket_demo",
        session_root=tmp_path / "outputs" / "session_demo",
        metadata_payloads=[
            {
                "Make": "Sony",
                "Model": "A7R V",
                "LensModel": "FE 24-70mm F2.8 GM II",
                "ISO": 400,
                "ExposureTime": "1/40",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": [512, 512, 512, 512],
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
            {
                "Make": "Sony",
                "Model": "A7R V",
                "LensModel": "FE 24-70mm F2.8 GM II",
                "ISO": 400,
                "ExposureTime": "1/20",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": [512, 512, 512, 512],
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
            {
                "Make": "Sony",
                "Model": "A7R V",
                "LensModel": "FE 24-70mm F2.8 GM II",
                "ISO": 400,
                "ExposureTime": "1/10",
                "FNumber": 4.0,
                "FocalLength": 24,
                "BlackLevel": [512, 512, 512, 512],
                "WhiteLevel": 16383,
                "CFAPattern": "RGGB",
            },
        ],
    )

    assert plan.engine_key == "dreamraw_tri_v2"
    assert plan.status == "phase1_foundation"
    assert plan.input_bundle_kind == "raw_bracket"
    assert plan.reference_frame_index == 1
    assert plan.reference_frame_role == "middle"
    assert plan.metadata_source == "provided"
    assert plan.bracket_metadata["exposure_order"] == "ascending"
    assert plan.noise_summary["quietest_frame_index"] in {0, 1, 2}
    assert plan.lens_correction["distortion_model"] == "brown_conrady"
    assert plan.scene_linear["target_relative_path"] == "scene_linear.exr"
    artifact_map = {artifact.kind: artifact for artifact in plan.expected_artifacts}
    assert set(artifact_map) == {
        "preview",
        "scene_linear",
        "report",
        "diagnostics_manifest",
        "noise_map",
        "motion_map",
        "confidence_map",
    }
    assert artifact_map["scene_linear"].path.endswith(str(Path("01_rawprep") / "bracket_demo" / "scene_linear.exr"))


def test_materialize_tri_raw_foundation_plan_writes_report_and_diagnostics(tmp_path):
    raw_paths = []
    for index in range(3):
        raw_path = tmp_path / f"frame_{index + 1:03d}.dng"
        raw_path.write_bytes(b"raw")
        raw_paths.append(str(raw_path))

    plan = build_tri_raw_foundation_plan(
        raw_paths,
        bracket_id="bracket_demo",
        session_root=tmp_path / "outputs" / "session_demo",
    )
    materialized = materialize_tri_raw_foundation_plan(plan)

    assert materialized.materialization_status == "foundation_written"
    assert Path(materialized.plan_path).is_file()
    assert Path(materialized.report_path).is_file()
    assert Path(materialized.diagnostics_manifest_path).is_file()

    report_payload = json.loads(Path(materialized.report_path).read_text(encoding="utf-8"))
    diagnostics_payload = json.loads(Path(materialized.diagnostics_manifest_path).read_text(encoding="utf-8"))
    assert report_payload["status"] == "foundation_written"
    assert report_payload["bracket_id"] == "bracket_demo"
    assert report_payload["reference_frame_role"] == "middle"
    assert report_payload["recommended_artifact"].endswith(str(Path("01_rawprep") / "bracket_demo" / "scene_linear.exr"))
    assert any(item["key"] == "report" and item["exists"] for item in diagnostics_payload["required_artifacts"])
    assert any(item["key"] == "diagnostics_manifest" for item in diagnostics_payload["required_artifacts"])
