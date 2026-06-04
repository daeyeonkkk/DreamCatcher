from pathlib import Path

from PIL import Image

from app.core.studio_selection_service import (
    StudioSelectionControls,
    apply_session_selection_state,
    load_session_selection_state,
)


def make_rgb_image(path: Path, color: tuple[int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 96), color).save(path)
    return str(path)


def make_mask_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (128, 96), 0)
    for x in range(26, 102):
        for y in range(20, 78):
            mask.putpixel((x, y), 220)
    mask.save(path)
    return str(path)


def test_apply_session_selection_state_creates_artifacts(tmp_path):
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (172, 126, 110))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_01" / "subject__mask.png")

    state = apply_session_selection_state(
        session_id,
        output_root=str(output_root),
        source_mask_path=source_mask_path,
        source_asset_path=source_asset_path,
        controls=StudioSelectionControls(threshold=120, expand_pixels=4, feather_radius=3),
    )

    assert state.ready is True
    assert Path(state.state_path).is_file()
    assert Path(state.current_mask_path).is_file()
    assert Path(state.preview_path).is_file()
    assert state.coverage_ratio > 0.10
    assert state.width == 128
    assert state.height == 96
    assert state.bounding_box is not None
    assert "임계값 120" in state.summary

    restored = load_session_selection_state(session_id, output_root=str(output_root))
    assert restored.current_mask_path == state.current_mask_path
    assert restored.preview_path == state.preview_path
    assert restored.controls.expand_pixels == 4


def test_apply_session_selection_state_rejects_empty_selection(tmp_path):
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (172, 126, 110))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_01" / "subject__mask.png")

    try:
        apply_session_selection_state(
            session_id,
            output_root=str(output_root),
            source_mask_path=source_mask_path,
            source_asset_path=source_asset_path,
            controls=StudioSelectionControls(threshold=255, expand_pixels=-32, feather_radius=0),
        )
    except ValueError as exc:
        assert "선택 범위가 너무 작습니다" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected selection service to reject an empty mask.")
