from importlib import import_module

from app.raw_engine_v2.shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA
from app.raw_engine_v2.shared.engine_registry import PHASE0_ENGINE_REGISTRY


def test_phase0_artifact_schema_locks_required_outputs():
    assert PHASE0_ARTIFACT_SCHEMA.schema_id == "dreamcatcher.raw_engine_v2.artifacts"
    assert PHASE0_ARTIFACT_SCHEMA.schema_version == "2026-04-06"
    assert PHASE0_ARTIFACT_SCHEMA.slot_keys() == [
        "preview",
        "scene_linear",
        "report",
        "diagnostics_manifest",
    ]
    assert PHASE0_ARTIFACT_SCHEMA.expected_paths() == {
        "preview": "preview.jpg",
        "scene_linear": "scene_linear.exr",
        "report": "report.json",
        "diagnostics_manifest": "diagnostics/manifest.json",
    }
    assert PHASE0_ARTIFACT_SCHEMA.expected_paths("tiff")["scene_linear"] == "scene_linear.tiff"


def test_phase0_engine_registry_references_shared_artifact_schema():
    assert PHASE0_ENGINE_REGISTRY.registry_id == "dreamcatcher.raw_engine_v2.registry"
    assert PHASE0_ENGINE_REGISTRY.registry_version == "2026-04-06"
    assert PHASE0_ENGINE_REGISTRY.keys() == [
        "dreamraw_one_v2",
        "dreamraw_tri_v2",
        "dreamisp_v2",
    ]

    for engine in PHASE0_ENGINE_REGISTRY.engines:
        assert engine.version == "2.0.0-phase0"
        assert engine.artifact_schema_id == PHASE0_ARTIFACT_SCHEMA.schema_id
        assert engine.artifact_schema_version == PHASE0_ARTIFACT_SCHEMA.schema_version
        assert engine.supported_modes


def test_phase0_scaffold_modules_exist_for_next_phase_work():
    expected_modules = {
        "app.raw_engine_v2.single_raw": "phase0_scaffold",
        "app.raw_engine_v2.single_raw.planner": "phase1_foundation",
        "app.raw_engine_v2.single_raw.runtime": "phase1_runtime_wiring",
        "app.raw_engine_v2.tri_raw": "phase0_scaffold",
        "app.raw_engine_v2.tri_raw.planner": "phase1_foundation",
        "app.raw_engine_v2.tri_raw.runtime": "phase1_runtime_wiring",
        "app.raw_engine_v2.isp": "phase0_scaffold",
        "app.raw_engine_v2.isp.planner": "phase1_foundation",
        "app.raw_engine_v2.isp.runtime": "phase1_runtime_wiring",
        "app.raw_engine_v2.comfy_adapter": "phase0_scaffold",
        "app.raw_engine_v2.shared.raw_io": "phase1_foundation",
        "app.raw_engine_v2.shared.metadata": "phase1_foundation",
        "app.raw_engine_v2.shared.noise_model": "phase1_foundation",
        "app.raw_engine_v2.shared.lens_correction": "phase1_applied_module",
        "app.raw_engine_v2.shared.scene_linear": "phase1_foundation",
    }

    for module_name, expected_status in expected_modules.items():
        module = import_module(module_name)
        assert getattr(module, "MODULE_STATUS") == expected_status
