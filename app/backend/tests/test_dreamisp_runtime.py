import json
from pathlib import Path

import numpy as np
from PIL import Image
import tifffile

from app.raw_engine_v2.isp.planner import (
    build_dreamisp_handoff_plan,
    materialize_dreamisp_handoff_plan,
)
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render


def _write_scene_linear(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = 64
    height = 40
    red = np.tile(np.linspace(2048, 12288, width, dtype=np.uint16), (height, 1))
    green = np.tile(np.linspace(4096, 14336, width, dtype=np.uint16), (height, 1))
    blue = np.tile(np.linspace(1024, 8192, width, dtype=np.uint16), (height, 1))
    scene_linear = np.stack([red, green, blue], axis=2)
    tifffile.imwrite(path, scene_linear)


def test_materialize_dreamisp_lite_render_writes_editable_preview_and_updates_plan(tmp_path):
    scene_linear_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "scene_linear.tiff"
    preview_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "preview.jpg"
    _write_scene_linear(scene_linear_path)
    Image.new("RGB", (64, 40), (120, 90, 70)).save(preview_path)

    plan = build_dreamisp_handoff_plan(
        session_root=tmp_path / "outputs" / "session_demo",
        source_stage="single_raw",
        source_item_key="capture_001",
        source_engine_key="dreamraw_one_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
        preview_path=str(preview_path),
    )
    materialized = materialize_dreamisp_handoff_plan(plan)
    rendered = materialize_dreamisp_lite_render(materialized)

    assert rendered.materialization_status == "preview_rendered"
    assert rendered.render_preview_path is not None
    assert Path(rendered.render_preview_path).is_file()
    assert rendered.render_preview_exists is True
    assert rendered.render_source_kind == "scene_linear"
    assert rendered.recommended_editable_source_path == rendered.render_preview_path
    assert rendered.render_backend == "dreamisp_lite_preview_v1"

    report_payload = json.loads(Path(rendered.report_path).read_text(encoding="utf-8"))
    render_state_payload = json.loads(Path(rendered.render_state_path).read_text(encoding="utf-8"))
    assert report_payload["status"] == "preview_rendered"
    assert report_payload["render_source_kind"] == "scene_linear"
    assert report_payload["render_preview_exists"] is True
    assert render_state_payload["output"]["editable_preview_path"] == rendered.render_preview_path


def test_dreamisp_lite_render_respects_render_state_adjustments(tmp_path):
    scene_linear_path = tmp_path / "outputs" / "session_demo" / "01_single_raw" / "capture_001" / "scene_linear.tiff"
    _write_scene_linear(scene_linear_path)

    base_plan = build_dreamisp_handoff_plan(
        session_root=tmp_path / "outputs" / "session_demo",
        source_stage="single_raw",
        source_item_key="capture_base",
        source_engine_key="dreamraw_one_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
    )
    base_plan = materialize_dreamisp_handoff_plan(base_plan)
    base_rendered = materialize_dreamisp_lite_render(base_plan)

    edited_plan = build_dreamisp_handoff_plan(
        session_root=tmp_path / "outputs" / "session_demo",
        source_stage="single_raw",
        source_item_key="capture_edit",
        source_engine_key="dreamraw_one_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
    )
    edited_plan.render_state["white_balance"]["temperature_delta"] = 45.0
    edited_plan.render_state["tone"]["exposure_ev"] = 0.8
    edited_plan.render_state["color"]["vibrance"] = 25.0
    edited_plan = materialize_dreamisp_handoff_plan(edited_plan)
    edited_rendered = materialize_dreamisp_lite_render(edited_plan)

    with Image.open(base_rendered.render_preview_path) as base_image:
        base_pixels = np.asarray(base_image.convert("RGB"), dtype=np.float32)
    with Image.open(edited_rendered.render_preview_path) as edited_image:
        edited_pixels = np.asarray(edited_image.convert("RGB"), dtype=np.float32)

    assert float(edited_pixels.mean()) > float(base_pixels.mean())
    assert float(edited_pixels[..., 0].mean()) > float(base_pixels[..., 0].mean())
