from pathlib import Path

from PIL import Image

from app.core.rawprep_catalog import list_engine_specs, rawprep_catalog_payload
from app.core.rawprep_contract import RawPrepBracketRequest, RawPrepJobRequest, build_job_plan
from app.core.rawprep_service import execute_rawprep_job, initialize_rawprep_job
from app.core.studio_intake import StudioIntakeRequest, build_studio_intake_plan, rawprep_result_preview_path


def test_rawprep_catalog_matches_phase0_engine_registry():
    specs = list_engine_specs()

    assert [spec.engine_stack for spec in specs] == [
        "dreamraw_one_v2",
        "dreamraw_tri_v2",
        "dreamisp_v2",
    ]
    assert all(spec.lifecycle == "phase0_scaffold" for spec in specs)
    assert all(spec.enabled is True for spec in specs)
    assert all(spec.artifact_schema_id == "dreamcatcher.raw_engine_v2.artifacts" for spec in specs)
    assert all(spec.required_tools == [] for spec in specs)

    payload = rawprep_catalog_payload()
    assert payload["status"] == "phase1_preview_runtime"
    assert payload["enabled"] is True
    assert len(payload["engine_stacks"]) == 3


def test_build_job_plan_uses_phase0_common_artifact_schema(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    plan = build_job_plan(
        RawPrepJobRequest(
            output_root="outputs",
            groups=[
                RawPrepBracketRequest(
                    bracket_id="bracket_demo",
                    raw_files=["a.dng", "b.dng", "c.dng"],
                )
            ],
        )
    )

    assert plan.engine.engine_stack == "dreamraw_tri_v2"
    assert plan.engine.engine_family == "tri_raw"
    assert plan.engine.status == "phase1_preview_runtime"
    assert plan.engine.artifact_schema_id == "dreamcatcher.raw_engine_v2.artifacts"
    assert plan.engine.artifact_schema_version == "2026-04-06"
    assert plan.restoration_goal == "truth_preserving"
    assert plan.engine.restoration_goal == "truth_preserving"

    artifacts = {artifact.kind: artifact for artifact in plan.expected_artifacts}
    assert set(artifacts) == {
        "preview",
        "scene_linear",
        "report",
        "diagnostics_manifest",
        "noise_map",
        "motion_map",
        "confidence_map",
    }
    assert artifacts["preview"].path.endswith(str(Path("01_rawprep") / "bracket_demo" / "preview.jpg"))
    assert artifacts["scene_linear"].path.endswith(str(Path("01_rawprep") / "bracket_demo" / "scene_linear.exr"))
    assert artifacts["report"].required is True
    assert artifacts["diagnostics_manifest"].required is True
    assert artifacts["motion_map"].required is False


def test_rawprep_result_preview_path_accepts_phase0_preview_artifact(tmp_path):
    preview_path = tmp_path / "outputs" / "session_demo" / "01_rawprep" / "bracket_demo" / "preview.jpg"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (180, 140, 120)).save(preview_path)

    payload = {
        "artifacts": [
            {
                "kind": "preview",
                "path": str(preview_path),
                "exists": True,
            }
        ]
    }

    assert rawprep_result_preview_path(payload) == str(preview_path)


def test_rawprep_result_preview_path_accepts_tri_raw_dreamisp_editable_preview(tmp_path):
    preview_path = tmp_path / "outputs" / "session_demo" / "02_manual" / "bracket_demo" / "editable_preview.jpg"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (164, 134, 116)).save(preview_path)

    payload = {
        "group_reports": [
            {
                "dreamisp_handoff": {
                    "render_preview_path": str(preview_path),
                    "render_preview_exists": True,
                }
            }
        ]
    }

    assert rawprep_result_preview_path(payload) == str(preview_path)


def test_initialize_rawprep_job_materializes_tri_raw_foundation_reports(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    plan = build_job_plan(
        RawPrepJobRequest(
            output_root="outputs",
            groups=[
                RawPrepBracketRequest(
                    bracket_id="bracket_demo",
                    raw_files=[
                        str(tmp_path / "frame_001.dng"),
                        str(tmp_path / "frame_002.dng"),
                        str(tmp_path / "frame_003.dng"),
                    ],
                )
            ],
        )
    )
    for raw_path in plan.groups[0].raw_files:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"raw")

    record = initialize_rawprep_job(plan, tool_status={})

    tri_raw_plan_path = Path(plan.layout.rawprep_dir) / "bracket_demo" / "tri_raw_plan.json"
    report_path = Path(plan.layout.rawprep_dir) / "bracket_demo" / "report.json"
    diagnostics_path = Path(plan.layout.rawprep_dir) / "bracket_demo" / "diagnostics" / "manifest.json"
    dreamisp_plan_path = Path(plan.layout.manual_dir) / "bracket_demo" / "dreamisp_plan.json"
    dreamisp_render_state_path = Path(plan.layout.manual_dir) / "bracket_demo" / "editable_render_state.json"
    dreamisp_report_path = Path(plan.layout.manual_dir) / "bracket_demo" / "report.json"
    assert tri_raw_plan_path.is_file()
    assert report_path.is_file()
    assert diagnostics_path.is_file()
    assert dreamisp_plan_path.is_file()
    assert dreamisp_render_state_path.is_file()
    assert dreamisp_report_path.is_file()
    assert record.group_reports
    assert record.group_reports[0]["bracket_id"] == "bracket_demo"
    assert record.group_reports[0]["dreamisp_handoff"]["source_stage"] == "tri_raw"
    assert record.group_reports[0]["dreamisp_handoff"]["plan_path"] == str(dreamisp_plan_path)
    assert record.group_reports[0]["dreamisp_handoff"]["materialization_status"] == "handoff_written"
    assert record.status == "ready"
    assert any("TriRaw foundation plan/report/diagnostics" in note for note in record.notes)
    assert any("DreamISP handoff/render-state files" in note for note in record.notes)


def test_initialize_rawprep_job_renders_tri_raw_dreamisp_preview_when_preview_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    plan = build_job_plan(
        RawPrepJobRequest(
            session_id="session_demo",
            output_root="outputs",
            groups=[
                RawPrepBracketRequest(
                    bracket_id="bracket_demo",
                    raw_files=[
                        str(tmp_path / "frame_001.dng"),
                        str(tmp_path / "frame_002.dng"),
                        str(tmp_path / "frame_003.dng"),
                    ],
                )
            ],
        )
    )
    for raw_path in plan.groups[0].raw_files:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"raw")

    preview_path = Path(plan.layout.rawprep_dir) / "bracket_demo" / "preview.jpg"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 80), (122, 96, 84)).save(preview_path)

    record = initialize_rawprep_job(plan, tool_status={})

    handoff = record.group_reports[0]["dreamisp_handoff"]
    editable_preview_path = Path(handoff["render_preview_path"])
    assert handoff["materialization_status"] == "preview_rendered"
    assert editable_preview_path.is_file()
    assert handoff["recommended_editable_source_path"] == str(editable_preview_path)


def test_studio_intake_three_raw_bracket_creates_rawprep_request(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    raw_paths = []
    for index in range(3):
        raw_path = tmp_path / "inputs" / f"capture_{index + 1:03d}.dng"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(b"raw")
        raw_paths.append(str(raw_path))

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=raw_paths,
            restoration_goal="aggressive_restore",
        )
    )

    assert plan.entry_mode == "rawprep_bracket"
    assert plan.rawprep_request is not None
    assert plan.rawprep_request["restoration_goal"] == "aggressive_restore"
    assert plan.rawprep_request["groups"][0]["raw_files"] == [asset.staged_path for asset in plan.staged_assets]
    assert "direct_edit_raw" in plan.alternate_modes


def test_execute_rawprep_job_materializes_preview_runtime_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    plan = build_job_plan(
        RawPrepJobRequest(
            session_id="session_demo",
            output_root="outputs",
            restoration_goal="aggressive_restore",
            groups=[
                RawPrepBracketRequest(
                    bracket_id="bracket_demo",
                    raw_files=[
                        str(tmp_path / "frame_001.dng"),
                        str(tmp_path / "frame_002.dng"),
                        str(tmp_path / "frame_003.dng"),
                    ],
                )
            ],
        )
    )
    for index, raw_path in enumerate(plan.groups[0].raw_files):
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"raw")
        Image.new("RGB", (140, 96), (112 + (index * 10), 90 + (index * 8), 78 + (index * 6))).save(path.with_suffix(".jpg"))

    initialize_rawprep_job(plan, tool_status={})
    record = execute_rawprep_job(plan, tool_status={})

    assert record.status == "done"
    preview_artifact = next(artifact for artifact in record.artifacts if artifact.kind == "preview")
    scene_linear_artifact = next(artifact for artifact in record.artifacts if artifact.kind == "scene_linear")
    motion_artifact = next(artifact for artifact in record.artifacts if artifact.kind == "motion_map")
    diagnostics_manifest_artifact = next(artifact for artifact in record.artifacts if artifact.kind == "diagnostics_manifest")
    assert Path(preview_artifact.path).is_file()
    assert Path(scene_linear_artifact.path).is_file()
    assert scene_linear_artifact.path.endswith("scene_linear.tiff")
    assert Path(motion_artifact.path).is_file()
    assert record.group_reports[0]["status"] == "preview_fused"
    assert record.group_reports[0]["merge_backend"] == "tri_raw_baseline_v1"
    assert record.group_reports[0]["restoration_goal"] == "aggressive_restore"
    assert record.group_reports[0]["restoration_goal_policy"]["approval_required"] is True
    assert record.group_reports[0]["restoration_goal_policy"]["delivery_default"] is False
    assert record.group_reports[0]["frontier_contract"]["contract_id"] == "tri_raw_frontier_v1"
    assert record.group_reports[0]["frontier_contract"]["accepted_frame_counts"] == [3, 9]
    assert record.group_reports[0]["frontier_contract"]["restoration_goal"] == "aggressive_restore"
    assert Path(record.group_reports[0]["merged_hdr_path"]).is_file()
    assert Path(record.group_reports[0]["denoised_result_path"]).is_file()
    assert Path(record.group_reports[0]["aggressive_restore_candidate_path"]).is_file()
    aggressive_candidate = next(
        entry for entry in record.group_reports[0]["candidate_scores"] if entry["label"] == "aggressive_restore"
    )
    assert aggressive_candidate["requires_review"] is True
    assert aggressive_candidate["delivery_default"] is False
    assert record.group_reports[0]["recommended_artifact"]
    assert record.group_reports[0]["fallback_strategy"]["selected_action"] in {
        "reference_frame_holdout",
        "guarded_fusion_holdout",
        "exposure_fusion_merge",
    }
    assert record.group_reports[0]["alignment_summary"]["backend"] == "phase_correlation_piecewise_preview_offsets_v2"
    assert record.group_reports[0]["confidence_summary"]["mean_confidence"] >= 0.0
    assert record.group_reports[0]["joint_denoise_summary"]["strategy"] == "preview_noise_aware_joint_denoise_v1"
    assert record.group_reports[0]["deghost_summary"]["strategy"] in {
        "reference_holdout_masked_fusion",
        "low_motion_guided_merge",
    }
    assert record.group_reports[0]["hdr_summary"]["strategy"] == "preview_exposure_fusion_bridge"
    assert Path(record.group_reports[0]["confidence_map_path"]).is_file()
    assert Path(record.group_reports[0]["confidence_preview_path"]).is_file()
    assert Path(record.group_reports[0]["ghost_risk_map_path"]).is_file()
    assert Path(record.group_reports[0]["highlight_map_path"]).is_file()
    assert Path(record.group_reports[0]["shadow_map_path"]).is_file()
    assert Path(record.group_reports[0]["deghost_mask_path"]).is_file()
    assert Path(record.group_reports[0]["hdr_gain_map_path"]).is_file()
    assert Path(record.group_reports[0]["noise_suppression_map_path"]).is_file()
    assert Path(record.group_reports[0]["alignment_offset_map_path"]).is_file()
    assert Path(record.group_reports[0]["alignment_residual_map_path"]).is_file()
    assert Path(record.group_reports[0]["alignment_vector_field_path"]).is_file()
    assert record.group_reports[0]["alignment_vector_summary"]["frame_count"] == 3
    assert record.group_reports[0]["dreamisp_handoff"]["materialization_status"] == "preview_rendered"
    diagnostics_payload = Path(diagnostics_manifest_artifact.path).read_text(encoding="utf-8")
    assert '"key": "confidence_preview"' in diagnostics_payload
    assert '"key": "ghost_risk_map"' in diagnostics_payload
    assert '"key": "deghost_mask"' in diagnostics_payload
    assert '"key": "hdr_gain_map"' in diagnostics_payload
    assert '"key": "noise_suppression_map"' in diagnostics_payload
    assert '"key": "alignment_offset_map"' in diagnostics_payload
    assert '"key": "alignment_residual_map"' in diagnostics_payload
    assert '"key": "alignment_vector_field"' in diagnostics_payload
    assert '"key": "aggressive_restore_candidate"' in diagnostics_payload


def test_build_job_plan_accepts_nine_raw_frontier_burst(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    raw_paths = []
    for index in range(9):
        raw_path = tmp_path / f"burst_{index + 1:02d}.dng"
        raw_path.write_bytes(b"raw")
        raw_paths.append(str(raw_path))

    plan = build_job_plan(
        RawPrepJobRequest(
            output_root="outputs",
            groups=[
                RawPrepBracketRequest(
                    bracket_id="frontier_burst",
                    raw_files=raw_paths,
                )
            ],
        )
    )

    assert plan.groups[0].raw_files == raw_paths
    assert plan.engine.engine_stack == "dreamraw_tri_v2"
