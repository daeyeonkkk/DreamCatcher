from pathlib import Path

from PIL import Image

from app.raw_engine_v2.tri_raw.learned_adapter import materialize_tri_raw_learned_adapter
from app.raw_engine_v2.tri_raw.planner import build_tri_raw_foundation_plan, materialize_tri_raw_foundation_plan


def _plan(tmp_path: Path, *, frame_count: int = 9):
    raw_paths: list[str] = []
    for index in range(frame_count):
        raw_path = tmp_path / f"frame_{index:02d}.dng"
        raw_path.write_bytes(b"raw")
        Image.new("L", (32, 32), 32 + index).save(raw_path.with_suffix(".tif"))
        raw_paths.append(str(raw_path))
    return materialize_tri_raw_foundation_plan(
        build_tri_raw_foundation_plan(
            raw_paths,
            bracket_id="learned_adapter_demo",
            session_root=tmp_path / "outputs" / "session_demo",
        )
    )


def test_tri_raw_learned_adapter_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DC_TRIRAW_LEARNED_ADAPTER", raising=False)

    result = materialize_tri_raw_learned_adapter(
        _plan(tmp_path),
        output_path=tmp_path / "out.tiff",
        preview_path=tmp_path / "out.jpg",
    )

    assert result.status == "disabled"
    assert result.reason == "set_DC_TRIRAW_LEARNED_ADAPTER_rawfusion_to_enable"


def test_tri_raw_learned_adapter_reports_missing_rawfusion_checkpoint(tmp_path, monkeypatch):
    repo = tmp_path / "RawFusion"
    (repo / "models").mkdir(parents=True)
    (repo / "models" / "Model_0_unet.py").write_text("class UNet: pass\n", encoding="utf-8")
    monkeypatch.setenv("DC_TRIRAW_LEARNED_ADAPTER", "rawfusion")
    monkeypatch.setenv("DC_RAWFUSION_REPO", str(repo))
    monkeypatch.delenv("DC_RAWFUSION_CKPT", raising=False)

    result = materialize_tri_raw_learned_adapter(
        _plan(tmp_path),
        output_path=tmp_path / "out.tiff",
        preview_path=tmp_path / "out.jpg",
    )

    assert result.status == "unavailable"
    assert result.reason == "rawfusion_checkpoint_missing"
    assert result.evidence["checkpoint_path"].endswith(str(Path("model_zoo") / "Ckpt_0_Organizer_team.pth"))


def test_tri_raw_learned_adapter_requires_nine_frames(tmp_path, monkeypatch):
    repo = tmp_path / "RawFusion"
    (repo / "models").mkdir(parents=True)
    (repo / "models" / "Model_0_unet.py").write_text("class UNet: pass\n", encoding="utf-8")
    ckpt = tmp_path / "checkpoint.pth"
    ckpt.write_bytes(b"placeholder")
    monkeypatch.setenv("DC_TRIRAW_LEARNED_ADAPTER", "rawfusion")
    monkeypatch.setenv("DC_RAWFUSION_REPO", str(repo))
    monkeypatch.setenv("DC_RAWFUSION_CKPT", str(ckpt))

    result = materialize_tri_raw_learned_adapter(
        _plan(tmp_path, frame_count=3),
        output_path=tmp_path / "out.tiff",
        preview_path=tmp_path / "out.jpg",
    )

    assert result.status == "unsupported"
    assert result.reason == "rawfusion_requires_nine_frames"
