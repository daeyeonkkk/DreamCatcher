from pathlib import Path

from PIL import Image

from app.core.studio_intake import StudioIntakeRequest, build_studio_intake_plan


def _write_preview(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (96, 72), color).save(path)


def test_build_studio_intake_plan_auto_discovers_sibling_companions_for_tri_raw(tmp_path):
    sample_root = tmp_path / "samples" / "tri_raw"
    sample_root.mkdir(parents=True, exist_ok=True)
    raw_paths: list[str] = []
    for index, color in enumerate(((116, 108, 98), (144, 132, 120), (170, 156, 142)), start=1):
        raw_path = sample_root / f"IMG_300{index}.CR3"
        raw_path.write_bytes(b"raw")
        _write_preview(sample_root / f"IMG_300{index}.JPG", color)
        raw_paths.append(str(raw_path))

    plan = build_studio_intake_plan(
        StudioIntakeRequest(
            session_id="tri_raw_companion_auto",
            output_root=str(tmp_path / "outputs"),
            asset_paths=raw_paths,
            entry_preference="rawprep",
        )
    )

    assert plan.entry_mode == "rawprep_bracket"
    staged_dir = Path(plan.session_root) / "00_input" / "bracket_01"
    assert staged_dir.is_dir()
    assert (staged_dir / "IMG_3001.CR3").is_file()
    assert (staged_dir / "IMG_3001.JPG").is_file()
    assert (staged_dir / "IMG_3002.JPG").is_file()
    assert (staged_dir / "IMG_3003.JPG").is_file()
    assert any("sibling preview" in note for note in plan.notes)
