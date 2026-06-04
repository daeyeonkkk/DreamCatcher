import json
from pathlib import Path

import numpy as np
import tifffile

from app.core.rawprep_benchmark_dreamisp_consistency import (
    RawPrepDreamISPConsistencyRequest,
    build_rawprep_dreamisp_consistency,
    load_rawprep_dreamisp_consistency,
    write_rawprep_dreamisp_consistency,
)
from app.raw_engine_v2.isp.planner import build_dreamisp_handoff_plan, materialize_dreamisp_handoff_plan
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render


def _write_scene_linear(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = 48
    height = 32
    red = np.tile(np.linspace(2048, 12288, width, dtype=np.uint16), (height, 1))
    green = np.tile(np.linspace(4096, 14336, width, dtype=np.uint16), (height, 1))
    blue = np.tile(np.linspace(1024, 8192, width, dtype=np.uint16), (height, 1))
    scene_linear = np.stack([red, green, blue], axis=2)
    tifffile.imwrite(path, scene_linear)


def _materialize_flow(tmp_path: Path, *, source_stage: str, item_key: str) -> dict:
    session_root = tmp_path / "outputs" / f"session_{source_stage}_{item_key}"
    scene_linear_path = session_root / "01_source" / item_key / "scene_linear.tiff"
    preview_path = session_root / "01_source" / item_key / "preview.jpg"
    _write_scene_linear(scene_linear_path)

    plan = build_dreamisp_handoff_plan(
        session_root=session_root,
        source_stage=source_stage,
        source_item_key=item_key,
        source_engine_key="dreamraw_one_v2" if source_stage == "single_raw" else "dreamraw_tri_v2",
        source_engine_version="2.0.0-phase0",
        scene_linear_path=str(scene_linear_path),
        preview_path=str(preview_path),
    )
    plan = materialize_dreamisp_handoff_plan(plan)
    rendered = materialize_dreamisp_lite_render(plan)
    assert rendered is not None

    return {
        "status": "passed",
        "dreamisp_render_preview_path": rendered.render_preview_path,
        "dreamisp_render_state_path": plan.render_state_path,
    }


def _write_local_e2e_smoke(path: Path, single_raw: dict, tri_raw: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "status": "passed",
                "single_raw": single_raw,
                "tri_raw": tri_raw,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_dreamisp_consistency_reports_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_dreamisp_consistency.repo_root", lambda: tmp_path)
    single_raw = _materialize_flow(tmp_path, source_stage="single_raw", item_key="img_001")
    tri_raw = _materialize_flow(tmp_path, source_stage="tri_raw", item_key="bracket_01")
    smoke_path = tmp_path / "outputs" / "benchmarks" / "measured" / "rawprep_local_e2e_smoke.json"
    _write_local_e2e_smoke(smoke_path, single_raw, tri_raw)

    artifact = build_rawprep_dreamisp_consistency(
        RawPrepDreamISPConsistencyRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is True
    assert artifact.status == "ready_for_consistent_tone"
    assert artifact.single_raw.pixel_match is True
    assert artifact.tri_raw.pixel_match is True


def test_build_dreamisp_consistency_reports_missing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_dreamisp_consistency.repo_root", lambda: tmp_path)

    artifact = build_rawprep_dreamisp_consistency(
        RawPrepDreamISPConsistencyRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )

    assert artifact.ok is False
    assert artifact.status == "missing_evidence"
    assert artifact.blockers


def test_write_dreamisp_consistency_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("app.core.rawprep_benchmark_dreamisp_consistency.repo_root", lambda: tmp_path)
    single_raw = _materialize_flow(tmp_path, source_stage="single_raw", item_key="img_001")
    tri_raw = _materialize_flow(tmp_path, source_stage="tri_raw", item_key="bracket_01")
    smoke_path = tmp_path / "outputs" / "benchmarks" / "measured" / "rawprep_local_e2e_smoke.json"
    _write_local_e2e_smoke(smoke_path, single_raw, tri_raw)

    artifact = write_rawprep_dreamisp_consistency(
        RawPrepDreamISPConsistencyRequest(
            output_dir="benchmarks/measured",
            output_root="outputs",
        )
    )
    loaded = load_rawprep_dreamisp_consistency("benchmarks/measured", output_root="outputs")

    assert Path(artifact.artifact_path).exists()
    assert loaded.status == "ready_for_consistent_tone"
    assert loaded.checks["shared_backend_consistent"] is True
