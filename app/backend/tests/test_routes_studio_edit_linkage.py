from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.main import app
from app.core.studio_job_service import (
    StudioJobOutput,
    StudioJobRequest,
    build_job_record,
    save_job_record,
)
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
    for x in range(18, 104):
        for y in range(18, 80):
            mask.putpixel((x, y), 220)
    mask.save(path)
    return str(path)


def test_edit_linkage_route_reads_current_source_and_latest_job(tmp_path):
    client = TestClient(app)
    output_root = tmp_path / "outputs"
    session_id = "session_demo"
    source_asset_path = make_rgb_image(output_root / session_id / "02_manual" / "source.png", (188, 150, 132))
    source_mask_path = make_mask_image(output_root / session_id / "03_ai" / "results" / "job_01" / "subject__mask.png")

    apply_session_selection_state(
        session_id,
        output_root=str(output_root),
        source_mask_path=source_mask_path,
        source_asset_path=source_asset_path,
        controls=StudioSelectionControls(threshold=110, expand_pixels=2, feather_radius=4),
    )

    record = build_job_record(
        StudioJobRequest(
            tool="replaceObject",
            session_id=session_id,
            output_root=str(output_root),
            source_path=source_asset_path,
            prompt="remove the distracting bottle and restore table texture",
            seed_root=str(SEED_ROOT),
        )
    )
    result_dir = Path(record.session_root) / "03_ai" / "results" / record.job_id
    candidate_path = make_rgb_image(result_dir / "01_replace_object_preview.png", (126, 148, 178))
    linked_mask_path = make_mask_image(result_dir / "01_replace_object_preview__mask.png")
    record.outputs = [
        StudioJobOutput(
            label="오브젝트 편집 결과 1",
            path=candidate_path,
            origin=candidate_path,
            kind="generated_candidate",
            linked_mask_path=linked_mask_path,
            alpha_extracted=True,
        )
    ]
    save_job_record(record)

    response = client.post(
        "/api/studio/edit-linkage",
        json={
            "session_id": session_id,
            "output_root": str(output_root),
            "current_source_path": candidate_path,
            "active_tool": "replaceObject",
            "studio_job_id": record.job_id,
            "source_history": [source_asset_path, candidate_path],
            "source_history_index": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_source_matches_generated"] is True
    assert payload["mask_ready"] is True
    assert payload["dreamgen_ready"] is True
    assert payload["latest_tool"] == "replaceObject"
    assert payload["current_source_kind"] == "generated_candidate"

    fetch_response = client.get(
        "/api/studio/edit-linkage",
        params={"session_id": session_id, "output_root": str(output_root)},
    )
    assert fetch_response.status_code == 200
    fetch_payload = fetch_response.json()
    assert fetch_payload["state_path"] == payload["state_path"]
    assert fetch_payload["current_source_path"] == candidate_path
