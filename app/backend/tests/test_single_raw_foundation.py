import json
from pathlib import Path

from PIL import Image, ImageChops
import numpy as np

from app.core.studio_intake import StudioIntakeRequest, build_studio_intake_plan
from app.raw_engine_v2.single_raw.planner import (
    build_single_raw_foundation_plan,
    materialize_single_raw_foundation_plan,
)
from app.raw_engine_v2.single_raw.runtime import (
    RAWPY_BACKEND_KEY,
    build_single_raw_runtime_health,
    materialize_single_raw_sensor_decode,
)


def _write_lens_stress_preview(path: Path) -> None:
    width, height = 160, 100
    y, x = np.indices((height, width), dtype=np.float32)
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    radius = np.sqrt(((x - center_x) / max(center_x, 1.0)) ** 2 + ((y - center_y) / max(center_y, 1.0)) ** 2)
    radius = np.clip(radius / np.sqrt(2.0), 0.0, 1.0)
    base = 152.0 - (radius**1.75 * 84.0)
    array = np.stack((base, base * 0.95, base * 0.9), axis=2)
    array[:, :14, 0] = np.clip(array[:, :14, 0] + 82.0, 0.0, 255.0)
    array[:, -14:, 2] = np.clip(array[:, -14:, 2] + 82.0, 0.0, 255.0)
    Image.fromarray(array.astype(np.uint8), mode="RGB").save(path)


def test_build_single_raw_foundation_plan_uses_shared_phase1_layers(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")

    plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_demo",
        metadata_payload={
            "Make": "Sony",
            "Model": "A7R V",
            "LensModel": "FE 24-70mm F2.8 GM II",
            "ISO": 640,
            "ExposureTime": "1/80",
            "FNumber": 2.8,
            "FocalLength": 35,
            "BlackLevel": [512, 512, 512, 512],
            "WhiteLevel": 16383,
            "CFAPattern": "RGGB",
        },
    )

    assert plan.engine_key == "dreamraw_one_v2"
    assert plan.status == "phase1_foundation"
    assert plan.metadata_source == "provided"
    assert plan.input_bundle_kind == "single_raw"
    assert plan.selected_frame_role == "single"
    assert plan.quality_preset == "balanced"
    assert plan.requested_mode == "fast"
    assert plan.resolved_mode == "fast"
    assert plan.mode_policy.resolved_mode == "fast"
    assert "Fast policy" in plan.mode_policy.summary
    assert plan.materialization_status == "planned"
    assert plan.decode["decoder_key"] == "raw_decode.cr3"
    assert plan.metadata["camera_key"] == "sony_a7r_v"
    assert plan.noise_profile["model_key"] == "phase1_deterministic_noise_profile"
    assert plan.lens_correction["distortion_model"] == "brown_conrady"
    assert plan.scene_linear["target_relative_path"] == "scene_linear.exr"
    artifact_map = {artifact.kind: artifact for artifact in plan.expected_artifacts}
    assert set(artifact_map) == {
        "preview",
        "scene_linear",
        "report",
        "diagnostics_manifest",
        "noise_map",
    }
    assert artifact_map["scene_linear"].path.endswith(str(Path("01_single_raw") / "frame_001" / "scene_linear.exr"))
    assert plan.report_path.endswith(str(Path("01_single_raw") / "frame_001" / "report.json"))
    assert plan.diagnostics_manifest_path.endswith(str(Path("01_single_raw") / "frame_001" / "diagnostics" / "manifest.json"))


def test_materialize_single_raw_foundation_plan_writes_structured_preview_and_reports(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")
    source_preview = tmp_path / "frame_001.jpg"
    _write_lens_stress_preview(source_preview)

    plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_demo",
        metadata_payload={
            "Make": "Sony",
            "Model": "A7R V",
            "LensModel": "FE 24-70mm F2.8 GM II",
            "ISO": 640,
            "ExposureTime": "1/80",
            "FNumber": 2.8,
            "FocalLength": 24,
            "BlackLevel": [512, 512, 512, 512],
            "WhiteLevel": 16383,
            "CFAPattern": "RGGB",
        },
    )
    materialized = materialize_single_raw_foundation_plan(plan, source_preview_path=str(source_preview))

    assert materialized.materialization_status == "preview_bootstrapped"
    assert materialized.preview_source_path == str(source_preview.resolve())
    assert materialized.materialized_input_preview_path is not None
    assert materialized.materialized_recovery_baseline_path is None
    assert materialized.materialized_preview_path is not None
    assert materialized.materialized_noise_map_path is not None
    assert materialized.materialized_lowlight_map_path is not None
    assert Path(materialized.materialized_input_preview_path).is_file()
    assert Path(materialized.materialized_preview_path).is_file()
    assert Path(materialized.materialized_lowlight_map_path).is_file()
    assert Path(materialized.report_path).is_file()
    assert Path(materialized.diagnostics_manifest_path).is_file()
    assert Path(materialized.manifest_path).is_file()
    manifest_payload = json.loads(Path(materialized.manifest_path).read_text(encoding="utf-8"))
    report_payload = json.loads(Path(materialized.report_path).read_text(encoding="utf-8"))
    diagnostics_payload = json.loads(Path(materialized.diagnostics_manifest_path).read_text(encoding="utf-8"))
    artifact_map = {artifact["kind"]: artifact for artifact in manifest_payload["expected_artifacts"]}
    assert manifest_payload["scene_linear"]["target_relative_path"] == "scene_linear.tiff"
    assert manifest_payload["scene_linear"]["materialized_format"] == "tiff"
    assert manifest_payload["materialized_input_preview_path"] is not None
    assert manifest_payload["materialized_noise_map_path"] is not None
    assert manifest_payload["materialized_lowlight_map_path"] is not None
    assert manifest_payload["materialized_timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert manifest_payload["resolved_mode"] == "fast"
    assert manifest_payload["decode"]["artifact_suppression"]["strategy_key"] == "single_raw_artifact_suppression_v1"
    assert manifest_payload["decode"]["lens_correction_report"]["diagnostic_key"] == "single_raw_lens_correction_report_v1"
    assert manifest_payload["decode"]["lens_correction_report"]["crop_applied"] is True
    assert manifest_payload["decode"]["lens_correction_report"]["preview_vignette_gain_peak"] > 0
    assert manifest_payload["decode"]["lens_correction_report"]["preview_lateral_ca_suppression_ratio"] > 0
    assert manifest_payload["decode"]["noise_report"]["diagnostic_key"] == "single_raw_noise_report_v1"
    assert manifest_payload["decode"]["recovery_report"]["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert manifest_payload["decode"]["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert manifest_payload["decode"]["timing_report"]["materialization_source"] == "preview_bootstrap"
    assert manifest_payload["decode"]["timing_report"]["total_ms"] >= 0
    assert "FAST" in manifest_payload["decode"]["timing_summary"]
    assert manifest_payload["decode"]["recovery_report"]["map_path"] == manifest_payload["materialized_lowlight_map_path"]
    assert "잔여 노이즈 평균" in manifest_payload["decode"]["noise_report_summary"]
    assert manifest_payload["decode"]["artifact_guardrail"]["guardrail_key"] == "fast_preview_direct_v1"
    assert "Fast" in manifest_payload["decode"]["artifact_suppression_summary"]
    assert "Fast" in manifest_payload["decode"]["recovery_report_summary"]
    assert manifest_payload["decode"]["fallback_decision"]["fallback_triggered"] is False
    assert Path(manifest_payload["scene_linear"]["materialized_path"]).is_file()
    assert artifact_map["scene_linear"]["path"].endswith(str(Path("01_single_raw") / "frame_001" / "scene_linear.tiff"))
    assert artifact_map["noise_map"]["path"].endswith(str(Path("01_single_raw") / "frame_001" / "diagnostics" / "noise_map.png"))
    assert report_payload["materialized_scene_linear_format"] == "tiff"
    assert report_payload["resolved_mode"] == "fast"
    assert Path(report_payload["materialized_input_preview_path"]).is_file()
    assert report_payload["noise_report"]["diagnostic_key"] == "single_raw_noise_report_v1"
    assert report_payload["lens_correction_report"]["diagnostic_key"] == "single_raw_lens_correction_report_v1"
    assert "비네팅 보정" in report_payload["lens_correction_summary"]
    assert report_payload["recovery_report"]["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert report_payload["artifact_suppression"]["strategy_key"] == "single_raw_artifact_suppression_v1"
    assert report_payload["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert report_payload["timing_report"]["materialization_source"] == "preview_bootstrap"
    assert "planner total" in report_payload["timing_summary"]
    assert report_payload["fallback_decision"]["fallback_triggered"] is False
    assert "고속 미리보기" in report_payload["artifact_guardrail_summary"]
    assert Path(report_payload["materialized_scene_linear_path"]).is_file()
    assert Path(report_payload["materialized_noise_map_path"]).is_file()
    assert Path(report_payload["materialized_lowlight_map_path"]).is_file()
    assert diagnostics_payload["noise_report"]["diagnostic_key"] == "single_raw_noise_report_v1"
    assert diagnostics_payload["lens_correction_report"]["diagnostic_key"] == "single_raw_lens_correction_report_v1"
    assert diagnostics_payload["recovery_report"]["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert diagnostics_payload["artifact_suppression"]["strategy_key"] == "single_raw_artifact_suppression_v1"
    assert diagnostics_payload["artifact_guardrail"]["guardrail_key"] == "fast_preview_direct_v1"
    assert diagnostics_payload["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert any(item["key"] == "scene_linear" and item["exists"] for item in diagnostics_payload["required_artifacts"])
    assert any(item["key"] == "noise_map" and item["exists"] for item in diagnostics_payload["diagnostics"])
    assert any(item["key"] == "lowlight_recovery_map" and item["exists"] for item in diagnostics_payload["diagnostics"])
    with Image.open(source_preview) as original_image, Image.open(materialized.materialized_input_preview_path) as corrected_image:
        original = np.asarray(original_image.convert("RGB"), dtype=np.float32)
        corrected = np.asarray(corrected_image.convert("RGB"), dtype=np.float32)
        assert corrected.shape[1] < original.shape[1]
        assert corrected.shape[0] < original.shape[0]
        assert float(corrected[:12, :12].mean()) > float(original[:12, :12].mean())
        original_edge_chroma = float(np.mean(np.ptp(original[:, :12, :], axis=2)) + np.mean(np.ptp(original[:, -12:, :], axis=2)))
        corrected_edge_chroma = float(np.mean(np.ptp(corrected[:, :12, :], axis=2)) + np.mean(np.ptp(corrected[:, -12:, :], axis=2)))
        assert corrected_edge_chroma < original_edge_chroma


def test_single_raw_sensor_runtime_materializes_structured_artifacts(tmp_path, monkeypatch):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")

    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.resolve_sensor_decode_backend",
        lambda: RAWPY_BACKEND_KEY,
    )

    def fake_decode(_: str, *, execution_mode: str = "fast"):
        scene_linear = np.full((48, 64, 3), 4096, dtype=np.uint16)
        scene_linear[:, :, 1] = 8192
        assert execution_mode == "fast"
        return scene_linear, {"white_level": 16383.0, "sizes": {"width": 64, "height": 48}}

    monkeypatch.setattr("app.raw_engine_v2.single_raw.runtime._decode_with_rawpy", fake_decode)

    result = materialize_single_raw_sensor_decode(
        str(raw_path),
        working_root=tmp_path / "outputs" / "session_demo" / "01_single_raw" / "frame_001",
        crop_margin_ratio=0.1,
        lens_correction={
            "camera_key": "sony_a7r_v",
            "lens_key": "fe_24_70_gm_ii",
            "apply_distortion": True,
            "apply_vignette": True,
            "apply_lateral_ca": True,
            "distortion_model": "brown_conrady",
            "crop_margin_ratio": 0.1,
            "vignette_strength": 0.2,
            "chroma_strength": 0.25,
            "notes": [],
        },
    )

    assert result is not None
    assert result.backend == RAWPY_BACKEND_KEY
    assert result.execution_mode == "fast"
    assert result.runtime_profile == "sensor_fast_preview_v1"
    assert Path(result.input_preview_path).is_file()
    assert result.details["runtime_profile"]["profile_key"] == "sensor_fast_preview_v1"
    assert result.noise_report["diagnostic_key"] == "single_raw_noise_report_v1"
    assert result.lens_correction_report["diagnostic_key"] == "single_raw_lens_correction_report_v1"
    assert result.lens_correction_report["crop_applied"] is True
    assert result.lens_correction_report["scene_linear_vignette_gain_peak"] > 0
    assert result.recovery_report["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert result.artifact_guardrail["guardrail_key"] == "fast_preview_direct_v1"
    assert result.artifact_suppression["strategy_key"] == "single_raw_artifact_suppression_v1"
    assert result.fallback_decision["fallback_triggered"] is False
    assert result.timing_report["diagnostic_key"] == "single_raw_timing_report_v1"
    assert result.timing_report["materialization_source"] == "sensor_decode"
    assert result.timing_report["total_ms"] >= 0
    assert result.scene_linear_format == "tiff"
    assert Path(result.preview_path).is_file()
    assert Path(result.scene_linear_path).is_file()
    assert Path(result.noise_map_path).is_file()
    assert Path(result.lowlight_map_path).is_file()
    assert result.width < 64
    assert result.height < 48


def test_materialize_single_raw_foundation_plan_prefers_sensor_runtime_when_available(tmp_path, monkeypatch):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")

    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.resolve_sensor_decode_backend",
        lambda: RAWPY_BACKEND_KEY,
    )

    def fake_decode(_: str, *, execution_mode: str = "fast"):
        scene_linear = np.zeros((40, 60, 3), dtype=np.uint16)
        scene_linear[:, :, 0] = 2048
        scene_linear[:, :, 1] = 4096
        scene_linear[:, :, 2] = 1024
        assert execution_mode == "fast"
        return scene_linear, {"white_level": 16383.0, "sizes": {"width": 60, "height": 40}}

    monkeypatch.setattr("app.raw_engine_v2.single_raw.runtime._decode_with_rawpy", fake_decode)

    plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_demo",
        metadata_payload={
            "Make": "Sony",
            "Model": "A7R V",
            "LensModel": "FE 24-70mm F2.8 GM II",
            "ISO": 640,
            "ExposureTime": "1/80",
            "FNumber": 2.8,
            "FocalLength": 24,
            "BlackLevel": [512, 512, 512, 512],
            "WhiteLevel": 16383,
            "CFAPattern": "RGGB",
        },
    )

    materialized = materialize_single_raw_foundation_plan(plan)

    assert materialized.materialization_status == "sensor_decoded"
    assert materialized.preview_source_path is None
    assert materialized.materialized_input_preview_path is not None
    assert materialized.materialized_recovery_baseline_path is None
    assert materialized.materialized_preview_path is not None
    assert Path(materialized.materialized_input_preview_path).is_file()
    assert Path(materialized.materialized_preview_path).is_file()
    manifest_payload = json.loads(Path(materialized.manifest_path).read_text(encoding="utf-8"))
    report_payload = json.loads(Path(materialized.report_path).read_text(encoding="utf-8"))
    diagnostics_payload = json.loads(Path(materialized.diagnostics_manifest_path).read_text(encoding="utf-8"))
    assert manifest_payload["decode"]["runtime_backend"] == RAWPY_BACKEND_KEY
    assert manifest_payload["decode"]["runtime_sensor_decode"] is True
    assert manifest_payload["decode"]["runtime_profile"] == "sensor_fast_preview_v1"
    assert manifest_payload["decode"]["lens_correction_report"]["diagnostic_key"] == "single_raw_lens_correction_report_v1"
    assert manifest_payload["decode"]["artifact_suppression"]["strategy_key"] == "single_raw_artifact_suppression_v1"
    assert manifest_payload["decode"]["recovery_report"]["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert manifest_payload["decode"]["fallback_decision"]["fallback_triggered"] is False
    assert manifest_payload["decode"]["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert manifest_payload["decode"]["timing_report"]["materialization_source"] == "sensor_decode"
    assert Path(manifest_payload["materialized_input_preview_path"]).is_file()
    assert manifest_payload["scene_linear"]["materialization_source"] == "sensor_decode_tiff"
    assert manifest_payload["materialized_noise_map_path"] is not None
    assert manifest_payload["materialized_lowlight_map_path"] is not None
    assert report_payload["runtime_backend"] == RAWPY_BACKEND_KEY
    assert report_payload["runtime_profile"] == "sensor_fast_preview_v1"
    assert report_payload["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert diagnostics_payload["runtime_backend"] == RAWPY_BACKEND_KEY
    assert diagnostics_payload["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert any("sensor decode backend" in note for note in manifest_payload["notes"])


def test_build_single_raw_foundation_plan_maps_safe_preset_to_safe_mode(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")

    plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_demo",
        quality_preset="safe",
    )

    assert plan.quality_preset == "safe"
    assert plan.requested_mode == "safe"
    assert plan.resolved_mode == "safe"
    assert plan.mode_policy.requested_quality_preset == "safe"
    assert plan.mode_policy.resolved_mode == "safe"
    assert "Safe policy" in plan.mode_policy.summary


def test_build_single_raw_foundation_plan_supports_hq_mode_preference(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")

    plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_demo",
        quality_preset="balanced",
        mode_preference="hq",
    )

    assert plan.quality_preset == "balanced"
    assert plan.mode_preference == "hq"
    assert plan.requested_mode == "hq"
    assert plan.resolved_mode == "hq"
    assert plan.mode_policy.resolved_mode == "hq"
    assert "HQ policy" in plan.mode_policy.summary


def test_hq_preview_bootstrap_uses_recovery_profile(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")
    source_preview = tmp_path / "frame_001.jpg"
    preview = Image.new("RGB", (160, 100), (20, 18, 18))
    for x in range(0, 80):
        for y in range(0, 100):
            if (x // 8 + y // 8) % 2 == 0:
                preview.putpixel((x, y), (26, 24, 23))
            else:
                preview.putpixel((x, y), (12, 11, 10))
    for x in range(80, 160):
        for y in range(0, 100):
            preview.putpixel((x, y), (242, 234, 226))
    preview.save(source_preview)

    fast_plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_fast",
        quality_preset="balanced",
        mode_preference="fast",
    )
    hq_plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_hq",
        quality_preset="balanced",
        mode_preference="hq",
    )

    fast_materialized = materialize_single_raw_foundation_plan(fast_plan, source_preview_path=str(source_preview))
    hq_materialized = materialize_single_raw_foundation_plan(hq_plan, source_preview_path=str(source_preview))

    fast_manifest = json.loads(Path(fast_materialized.manifest_path).read_text(encoding="utf-8"))
    hq_manifest = json.loads(Path(hq_materialized.manifest_path).read_text(encoding="utf-8"))
    hq_report = json.loads(Path(hq_materialized.report_path).read_text(encoding="utf-8"))

    assert hq_manifest["decode"]["runtime_profile"] == "sensor_hq_recovery_v1"
    assert hq_manifest["decode"]["recovery_report"]["diagnostic_key"] == "single_raw_recovery_report_v1"
    assert hq_manifest["materialized_recovery_baseline_path"] is not None
    assert Path(hq_manifest["materialized_recovery_baseline_path"]).is_file()
    assert hq_manifest["decode"]["recovery_report"]["baseline_path"] == hq_manifest["materialized_recovery_baseline_path"]
    assert hq_report["materialized_recovery_baseline_path"] == hq_manifest["materialized_recovery_baseline_path"]
    assert hq_manifest["decode"]["recovery_report"]["shadow_lift_ratio"] > fast_manifest["decode"]["recovery_report"]["shadow_lift_ratio"]
    assert hq_manifest["decode"]["recovery_report"]["highlight_rolloff_ratio"] >= fast_manifest["decode"]["recovery_report"]["highlight_rolloff_ratio"]
    assert hq_manifest["decode"]["recovery_report"]["lowlight_detail_gain_ratio"] > fast_manifest["decode"]["recovery_report"]["lowlight_detail_gain_ratio"]
    assert hq_manifest["decode"]["fallback_decision"]["selected_variant"] == "recovery_preview"
    assert Path(hq_manifest["materialized_lowlight_map_path"]).is_file()
    assert hq_manifest["decode"]["recovery_report"]["map_path"] == hq_manifest["materialized_lowlight_map_path"]
    assert "HQ" in hq_report["recovery_report_summary"]


def test_safe_preview_bootstrap_uses_guarded_profile(tmp_path):
    raw_path = tmp_path / "frame_001.CR3"
    raw_path.write_bytes(b"raw")
    source_preview = tmp_path / "frame_001.jpg"
    Image.new("RGB", (160, 100), (180, 120, 90)).save(source_preview)

    fast_plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_fast",
        quality_preset="balanced",
    )
    safe_plan = build_single_raw_foundation_plan(
        str(raw_path),
        session_root=tmp_path / "outputs" / "session_safe",
        quality_preset="safe",
    )

    fast_materialized = materialize_single_raw_foundation_plan(fast_plan, source_preview_path=str(source_preview))
    safe_materialized = materialize_single_raw_foundation_plan(safe_plan, source_preview_path=str(source_preview))

    fast_manifest = json.loads(Path(fast_materialized.manifest_path).read_text(encoding="utf-8"))
    safe_manifest = json.loads(Path(safe_materialized.manifest_path).read_text(encoding="utf-8"))
    safe_report = json.loads(Path(safe_materialized.report_path).read_text(encoding="utf-8"))

    assert fast_manifest["decode"]["runtime_profile"] == "sensor_fast_preview_v1"
    assert safe_manifest["decode"]["runtime_profile"] == "sensor_safe_guarded_v1"
    assert safe_report["runtime_profile"] == "sensor_safe_guarded_v1"
    assert "Safe 경로" in safe_report["artifact_suppression_summary"]
    assert safe_report["fallback_decision"]["fallback_triggered"] is True
    assert safe_manifest["resolved_mode"] == "safe"
    assert safe_manifest["decode"]["artifact_guardrail"]["guardrail_key"] == "safe_preview_soften_v1"
    assert safe_manifest["decode"]["artifact_guardrail"]["delta_luma"]["mean_luma"] > fast_manifest["decode"]["artifact_guardrail"]["delta_luma"]["mean_luma"]
    assert safe_manifest["decode"]["noise_report"]["suppression_ratio"] >= fast_manifest["decode"]["noise_report"]["suppression_ratio"]
    assert safe_manifest["decode"]["artifact_suppression"]["texture_suppression_ratio"] >= fast_manifest["decode"]["artifact_suppression"]["texture_suppression_ratio"]
    assert safe_manifest["decode"]["artifact_suppression"]["saturation_suppression_ratio"] >= fast_manifest["decode"]["artifact_suppression"]["saturation_suppression_ratio"]
    assert "Safe 경로" in safe_manifest["decode"]["artifact_suppression"]["summary"]
    assert safe_manifest["decode"]["fallback_decision"]["selected_variant"] == "preview_holdout"
    assert safe_manifest["decode"]["fallback_decision"]["fallback_triggered"] is True
    assert "보수적으로 억제" in safe_report["artifact_guardrail_summary"]

    with Image.open(fast_materialized.materialized_preview_path) as fast_image, Image.open(safe_materialized.materialized_preview_path) as safe_image:
        difference = ImageChops.difference(fast_image.convert("RGB"), safe_image.convert("RGB"))
        assert difference.getbbox() is not None


def test_single_raw_runtime_health_reports_missing_backend(monkeypatch):
    monkeypatch.setattr("app.raw_engine_v2.single_raw.runtime.resolve_sensor_decode_backend", lambda: None)
    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.find_spec",
        lambda name: None if name == "rawpy" else object(),
    )

    payload = build_single_raw_runtime_health()

    assert payload["ok"] is False
    assert payload["preferred_backend"] is None
    assert payload["required_modules"]["rawpy"] is False
    assert payload["sample_decode_ok"] is None


def test_single_raw_runtime_health_can_run_sample_decode(monkeypatch, tmp_path):
    sample_raw = tmp_path / "sample.CR3"
    sample_raw.write_bytes(b"raw")

    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.resolve_sensor_decode_backend",
        lambda: RAWPY_BACKEND_KEY,
    )
    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.find_spec",
        lambda _name: object(),
    )

    def fake_materialize(*_args, **_kwargs):
        output_root = tmp_path / "health"
        preview_path = output_root / "preview.jpg"
        scene_linear_path = output_root / "scene_linear.tiff"
        noise_map_path = output_root / "diagnostics" / "noise_map.png"
        lowlight_map_path = output_root / "diagnostics" / "lowlight_recovery_map.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        noise_map_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16), (120, 80, 40)).save(preview_path)
        scene_linear_path.write_bytes(b"tiff")
        noise_map_path.write_bytes(b"png")
        lowlight_map_path.write_bytes(b"png")
        from app.raw_engine_v2.single_raw.runtime import SingleRawSensorDecodeResult

        return SingleRawSensorDecodeResult(
            backend=RAWPY_BACKEND_KEY,
            execution_mode="fast",
            runtime_profile="sensor_fast_preview_v1",
            input_preview_path=str(preview_path),
            recovery_baseline_path=None,
            preview_path=str(preview_path),
            scene_linear_path=str(scene_linear_path),
            scene_linear_format="tiff",
            noise_map_path=str(noise_map_path),
            lowlight_map_path=str(lowlight_map_path),
            width=16,
            height=16,
            channels=3,
            dtype="uint16",
            timing_report={
                "diagnostic_key": "single_raw_timing_report_v1",
                "execution_mode": "fast",
                "materialization_source": "sensor_decode",
                "decode_ms": 4.2,
                "preview_pipeline_ms": 0.0,
                "artifact_write_ms": 2.1,
                "planner_overhead_ms": 0.0,
                "total_ms": 6.3,
                "summary": "FAST 경로 6.3ms (decode 4.2ms, preview 0.0ms, artifact 2.1ms).",
            },
            details={"white_level": 16383.0},
            notes=("ok",),
        )

    monkeypatch.setattr(
        "app.raw_engine_v2.single_raw.runtime.materialize_single_raw_sensor_decode",
        fake_materialize,
    )

    payload = build_single_raw_runtime_health(
        sample_raw_path=str(sample_raw),
        sample_working_root=tmp_path / "health",
    )

    assert payload["ok"] is True
    assert payload["preferred_backend"] == RAWPY_BACKEND_KEY
    assert payload["sample_decode_ok"] is True
    assert payload["sample_result"]["backend"] == RAWPY_BACKEND_KEY
    assert Path(payload["sample_result"]["input_preview_path"]).is_file()
    assert payload["sample_result"]["noise_report"] == {}
    assert payload["sample_result"]["artifact_guardrail"] == {}
    assert payload["sample_result"]["artifact_suppression"] == {}
    assert payload["sample_result"]["fallback_decision"] == {}
    assert payload["sample_result"]["timing_report"]["diagnostic_key"] == "single_raw_timing_report_v1"
    assert Path(payload["sample_result"]["preview_path"]).is_file()
    assert Path(payload["sample_result"]["lowlight_map_path"]).is_file()


def test_studio_intake_direct_raw_embeds_single_raw_foundation_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path)],
        )
    )

    assert plan.entry_mode == "direct_edit_raw"
    assert plan.single_raw_plan is not None
    assert plan.single_raw_plan["engine_key"] == "dreamraw_one_v2"
    assert plan.single_raw_plan["status"] == "phase1_foundation"
    assert plan.single_raw_plan["metadata_source"] == "default"
    assert plan.single_raw_plan["quality_preset"] == "balanced"
    assert plan.single_raw_plan["resolved_mode"] == "fast"
    assert plan.dreamisp_plan is None
    assert Path(plan.single_raw_plan["manifest_path"]).is_file()
    assert any("SingleRaw v2 기본 계획" in note for note in plan.notes)


def test_studio_intake_materializes_structured_single_raw_preview_when_companion_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    companion_path = tmp_path / "inputs" / "capture_001.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")
    Image.new("RGB", (180, 120), (140, 110, 90)).save(companion_path)

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path), str(companion_path)],
        )
    )

    assert plan.single_raw_plan is not None
    assert plan.single_raw_plan["materialization_status"] == "preview_bootstrapped"
    assert plan.single_raw_plan["materialized_noise_map_path"] is not None
    assert plan.dreamisp_plan is not None
    assert plan.dreamisp_plan["materialization_status"] == "preview_rendered"
    assert plan.editable_asset_path == plan.dreamisp_plan["render_preview_path"]
    assert plan.editable_asset_path is not None
    assert Path(plan.editable_asset_path).is_file()
    assert Path(plan.single_raw_plan["report_path"]).is_file()
    assert Path(plan.single_raw_plan["diagnostics_manifest_path"]).is_file()
    assert Path(plan.dreamisp_plan["plan_path"]).is_file()
    assert Path(plan.dreamisp_plan["render_state_path"]).is_file()
    assert Path(plan.dreamisp_plan["report_path"]).is_file()
    assert Path(plan.dreamisp_plan["render_preview_path"]).is_file()
    assert plan.dreamisp_plan["recommended_editable_source_path"] == plan.editable_asset_path
    assert plan.dreamisp_plan["render_preview_exists"] is True
    assert plan.dreamisp_plan["render_source_kind"] == "scene_linear"
    assert plan.dreamisp_plan["scene_linear_exists"] is True
    assert plan.dreamisp_plan["source_stage"] == "single_raw"
    assert any("DreamISP handoff plan" in note for note in plan.notes)
    assert any("편집용 미리보기" in note for note in plan.notes)
    assert any("구조화된 SingleRaw 미리보기" in note for note in plan.notes)


def test_studio_intake_safe_preset_records_safe_single_raw_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path)],
            quality_preset="safe",
        )
    )

    assert plan.single_raw_plan is not None
    assert plan.single_raw_plan["quality_preset"] == "safe"
    assert plan.single_raw_plan["resolved_mode"] == "safe"
    assert plan.single_raw_plan["decode"]["runtime_profile"] == "sensor_safe_guarded_v1"
    assert any("SingleRaw safe 모드 정책" in note for note in plan.notes)


def test_studio_intake_direct_raw_can_request_hq_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.raw_engine_v2.single_raw.planner.resolve_exiftool_binary", lambda: None)

    raw_path = tmp_path / "inputs" / "capture_001.dng"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            output_root="outputs",
            asset_paths=[str(raw_path)],
            quality_preset="balanced",
            single_raw_mode_preference="hq",
        )
    )

    assert plan.single_raw_plan is not None
    assert plan.single_raw_plan["quality_preset"] == "balanced"
    assert plan.single_raw_plan["mode_preference"] == "hq"
    assert plan.single_raw_plan["resolved_mode"] == "hq"
    assert plan.single_raw_plan["decode"]["runtime_profile"] == "sensor_hq_recovery_v1"
    assert any("모드 선택 'hq'" in note for note in plan.notes)
