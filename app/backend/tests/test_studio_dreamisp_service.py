import json
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.studio_dreamisp_service import apply_dreamisp_workspace_profile
from app.core.studio_intake import StudioIntakeRequest, build_studio_intake_plan


def test_apply_dreamisp_workspace_profile_updates_intake_manifest_and_render_state(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    companion_path = tmp_path / "inputs" / "capture_001.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")
    Image.new("RGB", (180, 120), (120, 95, 80)).save(companion_path)

    intake_plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path), str(companion_path)],
        )
    )

    dreamisp_payload = intake_plan.dreamisp_plan or {}
    original_preview_path = Path(str(dreamisp_payload.get("render_preview_path")))
    assert original_preview_path.is_file()
    original_bytes = original_preview_path.read_bytes()

    updated_plan = apply_dreamisp_workspace_profile(
        intake_plan.session_id,
        output_root="outputs",
        strength=82,
        realism=68,
        preserve_texture=91,
    )

    assert updated_plan.dreamisp_plan is not None
    assert updated_plan.editable_asset_path is not None
    updated_payload = updated_plan.dreamisp_plan
    assert updated_payload["materialization_status"] == "preview_rendered"
    assert updated_payload["render_preview_exists"] is True
    assert updated_payload["recommended_editable_source_path"] == updated_plan.editable_asset_path

    render_state_path = Path(updated_payload["render_state_path"])
    manifest_path = Path(updated_plan.manifest_path)
    assert render_state_path.is_file()
    assert manifest_path.is_file()

    render_state_payload = json.loads(render_state_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert render_state_payload["workspace_sliders"]["strength"] == 82
    assert render_state_payload["workspace_sliders"]["realism"] == 68
    assert render_state_payload["workspace_sliders"]["preserve_texture"] == 91
    assert manifest_payload["editable_asset_path"] == updated_plan.editable_asset_path

    updated_preview_path = Path(updated_payload["render_preview_path"])
    assert updated_preview_path.is_file()
    assert updated_preview_path.read_bytes() != original_bytes


def test_apply_dreamisp_workspace_profile_changes_render_luminance(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    companion_path = tmp_path / "inputs" / "capture_001.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")
    Image.new("RGB", (180, 120), (105, 92, 88)).save(companion_path)

    intake_plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path), str(companion_path)],
        )
    )

    base_preview_path = Path(str((intake_plan.dreamisp_plan or {}).get("render_preview_path")))
    with Image.open(base_preview_path) as base_image:
        base_pixels = np.asarray(base_image.convert("RGB"), dtype=np.float32)

    updated_plan = apply_dreamisp_workspace_profile(
        intake_plan.session_id,
        output_root="outputs",
        strength=88,
        realism=76,
        preserve_texture=94,
    )

    updated_preview_path = Path(str((updated_plan.dreamisp_plan or {}).get("render_preview_path")))
    with Image.open(updated_preview_path) as updated_image:
        updated_pixels = np.asarray(updated_image.convert("RGB"), dtype=np.float32)

    assert float(updated_pixels.mean()) > float(base_pixels.mean())


def test_apply_dreamisp_workspace_profile_overrides_manual_controls(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    companion_path = tmp_path / "inputs" / "capture_001.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")
    Image.new("RGB", (180, 120), (118, 96, 84)).save(companion_path)

    intake_plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path), str(companion_path)],
        )
    )

    updated_plan = apply_dreamisp_workspace_profile(
        intake_plan.session_id,
        output_root="outputs",
        strength=70,
        realism=62,
        preserve_texture=88,
        temperature_delta=24.0,
        tint_delta=-11.0,
        exposure_ev=1.2,
        contrast=18.0,
        clarity=26.0,
    )

    render_state_path = Path(str((updated_plan.dreamisp_plan or {}).get("render_state_path")))
    render_state_payload = json.loads(render_state_path.read_text(encoding="utf-8"))
    assert render_state_payload["white_balance"]["mode"] == "manual_ui_v1"
    assert render_state_payload["white_balance"]["temperature_delta"] == 24.0
    assert render_state_payload["white_balance"]["tint_delta"] == -11.0
    assert render_state_payload["tone"]["exposure_ev"] == 1.2
    assert render_state_payload["tone"]["contrast"] == 18.0
    assert render_state_payload["detail"]["clarity"] == 26.0
    assert render_state_payload["manual_controls"]["control_profile"] == "manual_ui_v1"
