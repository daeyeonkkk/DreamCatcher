import json
from pathlib import Path

from PIL import Image

from app.core.studio_job_service import StudioJobRequest, build_job_record, collect_job_outputs, prepare_source_image

SEED_ROOT = Path(__file__).resolve().parents[3] / "seed_bundle"


def make_session_image(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 96), (180, 140, 120)).save(path)
    return str(path)


def test_collect_job_outputs_extracts_reusable_mask_from_alpha_result(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "remove_bg_preview.png"

    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    for x in range(18, 78):
        for y in range(18, 78):
            image.putpixel((x, y), (220, 180, 160, 255))
    image.save(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "background_cutout"
    assert outputs[0].alpha_extracted is True
    assert outputs[0].linked_mask_path is not None
    mask_path = Path(outputs[0].linked_mask_path)
    assert mask_path.is_file()
    with Image.open(mask_path) as mask:
        assert mask.mode == "L"
        assert mask.getextrema() == (0, 255)


def test_collect_job_outputs_skips_mask_when_output_has_no_alpha(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "remove_bg_preview.png"
    Image.new("RGB", (96, 96), (220, 180, 160)).save(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="removeBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "background_cutout"
    assert outputs[0].linked_mask_path is None
    assert outputs[0].alpha_extracted is False


def test_collect_job_outputs_marks_generated_edit_candidates(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "replace_bg_preview.png"
    Image.new("RGB", (96, 96), (90, 120, 180)).save(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="replaceBg",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "generated_candidate"


def test_collect_job_outputs_marks_object_fill_candidates(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "replace_object_preview.png"
    Image.new("RGB", (96, 96), (140, 110, 180)).save(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="replaceObject",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "generated_candidate"


def test_prepare_source_image_builds_expand_canvas_input_and_plan(tmp_path):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")

    record = build_job_record(
        StudioJobRequest(
            tool="expandCanvas",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )

    prepared_path = prepare_source_image(record)

    assert prepared_path.is_file()
    with Image.open(prepared_path) as image:
        assert image.mode == "RGBA"
        assert image.size[0] > 128
        assert image.size[1] > 96
        assert image.getchannel("A").getextrema() == (0, 255)
        prepared_size = image.size
    plan_path = Path(record.job_root) / "prepared" / "expand_canvas_plan.json"
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["mask_strategy"] == "transparent_border_from_alpha"
    assert (plan["target_size"]["width"], plan["target_size"]["height"]) == prepared_size
    assert any("화면 확장 입력" in note for note in record.notes)


def test_collect_job_outputs_marks_expand_canvas_candidates(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    session_root = output_root / "session_demo"
    source_path = make_session_image(session_root / "02_manual" / "source.png")
    comfy_output_root = tmp_path / "comfy_output"
    comfy_output_root.mkdir(parents=True, exist_ok=True)
    rendered_path = comfy_output_root / "expand_canvas_preview.png"
    Image.new("RGB", (160, 120), (110, 140, 190)).save(rendered_path)

    record = build_job_record(
        StudioJobRequest(
            tool="expandCanvas",
            session_id="session_demo",
            output_root=str(output_root),
            source_path=source_path,
            seed_root=str(SEED_ROOT),
        )
    )
    monkeypatch.setenv("COMFY_OUTPUT_DIR", str(comfy_output_root))

    outputs = collect_job_outputs(
        record,
        prompt_id="prompt-demo",
        history_payload={
            "prompt-demo": {
                "outputs": {
                    "node-1": {
                        "images": [
                            {
                                "filename": rendered_path.name,
                                "subfolder": "",
                            }
                        ]
                    }
                }
            }
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "generated_candidate"
    assert outputs[0].label == "화면 확장 결과 1"
