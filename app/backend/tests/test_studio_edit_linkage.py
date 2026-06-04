from pathlib import Path

from PIL import Image

from app.core.studio_edit_linkage import (
    build_or_update_session_edit_linkage,
    load_session_edit_linkage,
)
from app.core.studio_job_service import StudioJobOutput, StudioJobRequest, build_job_record
from app.core.studio_selection_service import (
    StudioSelectionControls,
    apply_session_selection_state,
)


SEED_ROOT = Path(__file__).resolve().parents[3] / "seed_bundle"


def make_rgb_image(path: Path, color: tuple[int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 96), color).save(path)
    return str(path)


def make_mask_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (128, 96), 0)
    for x in range(20, 108):
        for y in range(18, 82):
            mask.putpixel((x, y), 220)
    mask.save(path)
    return str(path)


def test_build_edit_linkage_tracks_mask_and_generated_candidate(tmp_path):
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (182, 146, 126))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_cutout" / "subject__mask.png")
    selection_state = apply_session_selection_state(
        session_id,
        output_root=str(output_root),
        source_mask_path=source_mask_path,
        source_asset_path=source_asset_path,
        controls=StudioSelectionControls(threshold=118, expand_pixels=3, feather_radius=5),
    )

    record = build_job_record(
        StudioJobRequest(
            tool="replaceBg",
            session_id=session_id,
            output_root=str(output_root),
            source_path=source_asset_path,
            prompt="cozy evening studio background",
            seed_root=str(SEED_ROOT),
        )
    )
    candidate_path = make_rgb_image(Path(record.job_root) / "results" / "01_replace_bg_preview.png", (104, 136, 190))
    linked_mask_path = make_mask_image(Path(record.job_root) / "results" / "01_replace_bg_preview__mask.png")
    record.outputs = [
        StudioJobOutput(
            label="배경 교체 결과 1",
            path=candidate_path,
            origin=candidate_path,
            kind="generated_candidate",
            linked_mask_path=linked_mask_path,
            alpha_extracted=True,
        )
    ]

    state = build_or_update_session_edit_linkage(
        session_id,
        output_root=str(output_root),
        current_source_path=candidate_path,
        active_tool="replaceBg",
        studio_job_record=record,
        selection_state=selection_state,
        source_history=[source_asset_path, candidate_path],
        source_history_index=1,
    )

    assert Path(state.state_path).is_file()
    assert state.mask_ready is True
    assert state.dreamgen_ready is True
    assert state.current_source_matches_generated is True
    assert state.latest_generated_candidate_paths == [candidate_path]
    assert "생성 편집 결과" in (state.current_source_label or "")
    assert "선택 마스크" in state.summary

    restored = load_session_edit_linkage(session_id, output_root=str(output_root))
    assert restored.current_source_path == candidate_path
    assert restored.selection_current_mask_path == selection_state.current_mask_path
    assert restored.source_history_index == 1
