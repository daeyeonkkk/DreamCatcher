from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from zipfile import ZIP_DEFLATED, ZipFile

from .rawprep_contract import build_directory_layout
from .studio_catalog import load_session_catalog
from .studio_intake import load_studio_intake_plan, latest_studio_job_payload, try_read_json
from .studio_paths import resolve_output_path, resolve_output_root


DeliveryPresetKey = Literal[
    "review_pack",
    "client_delivery",
    "master_archive",
    "proofing_sheet",
    "print_master",
    "client_review_portal",
]
DeliveryProfileStage = Literal["review", "finish", "archive"]

DELIVERY_PROFILE_SPECS: dict[DeliveryPresetKey, dict[str, str | bool]] = {
    "review_pack": {
        "profile_id": "review_contact_sheet_v1",
        "label": "검토 묶음",
        "branch_stage": "review",
        "master_source": "raster",
        "description": "검토용 JPG/TIFF 결과를 묶어 비교와 승인 라운드를 빠르게 진행합니다.",
    },
    "client_delivery": {
        "profile_id": "finish_delivery_scene_linear_v2",
        "label": "고객 전달본",
        "branch_stage": "finish",
        "master_source": "scene_linear",
        "description": "최종 결과와 가장 안전한 장면 선형 작업 마스터를 함께 전달합니다.",
    },
    "master_archive": {
        "profile_id": "scene_linear_archive_v2",
        "label": "마스터 보관본",
        "branch_stage": "archive",
        "master_source": "mixed",
        "description": "장면 선형 마스터, 미리보기, 진단 산출물, 최종 결과를 장기 보관용으로 남깁니다.",
    },
    "proofing_sheet": {
        "profile_id": "proofing_sheet_v1",
        "label": "교정 시트",
        "branch_stage": "review",
        "master_source": "raster",
        "description": "내부 검수나 랩 교정을 위해 미리보기, 최신 결과, 검토 메모를 함께 정리합니다.",
    },
    "print_master": {
        "profile_id": "print_master_v2",
        "label": "출력 마스터",
        "branch_stage": "finish",
        "master_source": "scene_linear",
        "description": "출력용 최종 결과와 가장 안전한 장면 선형 마스터, 작업 소스를 함께 넘깁니다.",
    },
    "client_review_portal": {
        "profile_id": "client_review_portal_v1",
        "label": "고객 검토 포털",
        "branch_stage": "review",
        "master_source": "mixed",
        "description": "고객 검토 포털에 맞춘 미리보기, 최신 결과, 고객용 세션 메타데이터 묶음을 만듭니다.",
    },
}


def resolve_output_target(path: str, *, output_root: str) -> Path:
    try:
        target = resolve_output_path(path, output_root=output_root)
    except ValueError as exc:
        raise ValueError("Studio file path must stay inside the configured output root.") from exc
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Studio file does not exist: {target}")
    return target


def sanitize_export_label(value: str | None) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    normalized = normalized.strip("._-")
    return normalized or "export"


def delivery_profile_spec(preset: DeliveryPresetKey) -> dict[str, str]:
    spec = DELIVERY_PROFILE_SPECS[preset]
    return {
        "preset": preset,
        "profile_id": str(spec["profile_id"]),
        "label": str(spec["label"]),
        "branch_stage": str(spec["branch_stage"]),
        "master_source": str(spec["master_source"]),
        "description": str(spec["description"]),
    }


def export_output_file(path: str, *, output_root: str, session_id: str, label: str | None = None) -> Path:
    source = resolve_output_target(path, output_root=output_root)
    layout = build_directory_layout(output_root, session_id)
    export_dir = Path(layout.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_label = sanitize_export_label(label)
    destination = export_dir / f"{timestamp}_{safe_label}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    return destination


def _unique_package_name(directory: Path, desired_name: str) -> str:
    candidate = desired_name
    stem = Path(desired_name).stem
    suffix = Path(desired_name).suffix
    counter = 2
    while (directory / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def export_session_package(
    *,
    session_id: str,
    output_root: str,
    items: Iterable[dict[str, str | None]],
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    layout = build_directory_layout(output_root, session_id)
    export_dir = Path(layout.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_label = sanitize_export_label(label or "delivery_package")
    package_root = export_dir / f"{timestamp}_{safe_label}"
    package_root.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict[str, str]] = []
    try:
        for index, item in enumerate(items, start=1):
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                continue

            source = resolve_output_target(path, output_root=output_root)
            requested_label = item.get("label") if isinstance(item.get("label"), str) else None
            base_name = sanitize_export_label(requested_label or source.stem)
            file_name = _unique_package_name(package_root, f"{index:02d}_{base_name}{source.suffix.lower()}")
            destination = package_root / file_name
            shutil.copy2(source, destination)
            manifest_items.append(
                {
                    "label": requested_label or source.name,
                    "source_path": str(source),
                    "package_path": file_name,
                }
            )

        if not manifest_items:
            raise ValueError("At least one valid studio file is required to build a package.")

        manifest_payload = {
            "session_id": session_id,
            "output_root": output_root,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "label": safe_label,
            "metadata": metadata or {},
            "items": manifest_items,
        }
        (package_root / "package_manifest.json").write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        archive_name = _unique_package_name(export_dir, f"{package_root.name}.zip")
        archive_path = export_dir / archive_name
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
            for child in package_root.rglob("*"):
                archive.write(child, arcname=str(Path(package_root.name) / child.relative_to(package_root)))
        return archive_path
    finally:
        shutil.rmtree(package_root, ignore_errors=True)


def _unique_items(items: Iterable[dict[str, str | None]]) -> list[dict[str, str | None]]:
    unique: list[dict[str, str | None]] = []
    seen = set()
    for item in items:
        path = item.get("path")
        if not isinstance(path, str) or not path.strip() or path in seen:
            continue
        seen.add(path)
        label = item.get("label")
        unique.append(
            {
                "path": path,
                "label": label if isinstance(label, str) and label.strip() else None,
            }
        )
    return unique


def _studio_output_items(payload: dict[str, Any] | None) -> list[dict[str, str | None]]:
    if not isinstance(payload, dict):
        return []
    outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        return []

    items: list[dict[str, str | None]] = []
    for index, output in enumerate(outputs, start=1):
        if not isinstance(output, dict):
            continue
        path = output.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        label = output.get("label") if isinstance(output.get("label"), str) else f"studio_output_{index}"
        items.append({"path": path, "label": label})
    return items


def _rawprep_artifact_items(payload: dict[str, Any] | None) -> list[dict[str, str | None]]:
    if not isinstance(payload, dict):
        return []
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return []

    items: list[dict[str, str | None]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("exists") is False:
            continue
        path = artifact.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        kind = artifact.get("kind") if isinstance(artifact.get("kind"), str) else "rawprep_artifact"
        items.append({"path": path, "label": kind})
    return items


def _rawprep_artifact_map(payload: dict[str, Any] | None) -> dict[str, list[dict[str, str | None]]]:
    items_by_kind: dict[str, list[dict[str, str | None]]] = {}
    for item in _rawprep_artifact_items(payload):
        label = item.get("label")
        if not isinstance(label, str):
            continue
        items_by_kind.setdefault(label, []).append(item)
    return items_by_kind


def _first_artifact_item(
    items_by_kind: dict[str, list[dict[str, str | None]]],
    *preferred_kinds: str,
    label: str | None = None,
) -> dict[str, str | None] | None:
    for kind in preferred_kinds:
        candidates = items_by_kind.get(kind)
        if not candidates:
            continue
        item = dict(candidates[0])
        if label:
            item["label"] = label
        return item
    return None


def _recommended_rawprep_item(payload: dict[str, Any] | None) -> dict[str, str | None] | None:
    if not isinstance(payload, dict):
        return None
    group_reports = payload.get("group_reports")
    if not isinstance(group_reports, list):
        return None

    for report in group_reports:
        if not isinstance(report, dict):
            continue
        dreamisp_handoff = report.get("dreamisp_handoff")
        if isinstance(dreamisp_handoff, dict):
            preview_path = dreamisp_handoff.get("render_preview_path")
            if isinstance(preview_path, str) and preview_path.strip():
                return {"path": preview_path, "label": "dreamisp_editable_preview"}
            editable_path = dreamisp_handoff.get("recommended_editable_source_path")
            if isinstance(editable_path, str) and editable_path.strip():
                return {"path": editable_path, "label": "dreamisp_editable_source"}
        path = report.get("recommended_artifact")
        if isinstance(path, str) and path.strip():
            return {"path": path, "label": "recommended_artifact"}
    return None


def _preferred_rawprep_result_item(payload: dict[str, Any] | None) -> dict[str, str | None] | None:
    recommended_item = _recommended_rawprep_item(payload)
    if recommended_item is not None:
        return recommended_item

    preferred_order = ("preview", "scene_linear")
    artifact_items = _rawprep_artifact_items(payload)
    for kind in preferred_order:
        for item in artifact_items:
            if item.get("label") == kind:
                return {"path": item["path"], "label": "rawprep_result"}
    return artifact_items[0] if artifact_items else None


def build_delivery_preset_items(
    *,
    session_id: str,
    output_root: str,
    preset: DeliveryPresetKey,
) -> list[dict[str, str | None]]:
    plan = load_studio_intake_plan(session_id, output_root=output_root)
    session_root = Path(plan.session_root)
    rawprep_payload = try_read_json(session_root / "rawprep_job.json")
    studio_payload, _ = latest_studio_job_payload(session_root)
    rawprep_artifacts_by_kind = _rawprep_artifact_map(rawprep_payload)

    staged_items = [
        {"path": asset.staged_path, "label": f"input_{index + 1}_{asset.file_name}"}
        for index, asset in enumerate(plan.staged_assets)
    ]
    scene_linear_master = _first_artifact_item(rawprep_artifacts_by_kind, "scene_linear", label="scene_linear_master")
    delivery_master = scene_linear_master
    review_preview = _first_artifact_item(rawprep_artifacts_by_kind, "preview", label="review_preview")
    archive_base = scene_linear_master
    working_source = _recommended_rawprep_item(rawprep_payload) or (
        {"path": plan.editable_asset_path, "label": "working_source"}
        if isinstance(plan.editable_asset_path, str) and plan.editable_asset_path.strip()
        else None
    )
    if working_source is None and staged_items:
        working_source = {"path": staged_items[0]["path"], "label": "working_source"}
    studio_outputs = _studio_output_items(studio_payload)
    latest_result = (
        {"path": studio_outputs[-1]["path"], "label": "latest_result"}
        if studio_outputs
        else _preferred_rawprep_result_item(rawprep_payload)
    )
    rawprep_items = _rawprep_artifact_items(rawprep_payload)

    if preset == "review_pack":
        return _unique_items(
            item
            for item in [
                review_preview,
                latest_result,
                working_source,
                archive_base,
            ]
            if item is not None
        )

    if preset == "client_delivery":
        return _unique_items(
            item
            for item in [
                {"path": latest_result["path"], "label": "finish_result"} if latest_result else None,
                delivery_master,
                {"path": working_source["path"], "label": "finish_source"} if working_source else None,
            ]
            if item is not None
        )

    if preset == "proofing_sheet":
        return _unique_items(
            item
            for item in [
                review_preview,
                {"path": latest_result["path"], "label": "proof_finish"} if latest_result else None,
                archive_base,
                {"path": working_source["path"], "label": "proof_source"} if working_source else None,
            ]
            if item is not None
        )

    if preset == "print_master":
        return _unique_items(
            item
            for item in [
                {"path": latest_result["path"], "label": "print_result"} if latest_result else None,
                {"path": archive_base["path"], "label": "print_scene_linear_master"} if archive_base else None,
                {"path": working_source["path"], "label": "print_source"} if working_source else None,
            ]
            if item is not None
        )

    if preset == "client_review_portal":
        return _unique_items(
            item
            for item in [
                review_preview,
                {"path": latest_result["path"], "label": "portal_latest_result"} if latest_result else None,
                {"path": working_source["path"], "label": "portal_source"} if working_source else None,
                archive_base,
            ]
            if item is not None
        )

    return _unique_items(
        item
        for item in [
            {"path": latest_result["path"], "label": "finish_result"} if latest_result else None,
            archive_base,
            review_preview,
            {"path": working_source["path"], "label": "working_source"} if working_source else None,
            *staged_items,
            *rawprep_items,
            *studio_outputs,
        ]
        if item is not None
    )


def build_delivery_preset_package(
    *,
    session_id: str,
    output_root: str,
    preset: DeliveryPresetKey,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = delivery_profile_spec(preset)
    items = build_delivery_preset_items(session_id=session_id, output_root=output_root, preset=preset)
    try:
        catalog_payload = load_session_catalog(session_id, output_root=output_root).model_dump()
    except FileNotFoundError:
        catalog_payload = None
    archive_path = export_session_package(
        session_id=session_id,
        output_root=output_root,
        items=items,
        label=label or preset,
        metadata={
            "preset": preset,
            "delivery_profile": profile,
            "catalog": catalog_payload,
            **(metadata or {}),
        },
    )
    return {
        "session_id": session_id,
        "output_root": str(resolve_output_root(output_root)),
        "preset": preset,
        "delivery_profile": profile,
        "archive_path": str(archive_path),
        "file_name": archive_path.name,
        "file_count": len(items),
    }


def export_batch_delivery_packages(
    *,
    output_root: str,
    session_ids: Iterable[str],
    preset: DeliveryPresetKey,
) -> dict[str, Any]:
    output_root_path = resolve_output_root(output_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_preset = sanitize_export_label(preset)
    batch_id = f"{timestamp}_{safe_preset}"
    report_dir = output_root_path / "_batch_exports"
    report_dir.mkdir(parents=True, exist_ok=True)

    unique_session_ids: list[str] = []
    seen_session_ids = set()
    for session_id in session_ids:
        normalized = str(session_id).strip()
        if not normalized or normalized in seen_session_ids:
            continue
        seen_session_ids.add(normalized)
        unique_session_ids.append(normalized)

    if not unique_session_ids:
        raise ValueError("At least one studio session is required for batch delivery export.")

    records: list[dict[str, Any]] = []
    for session_id in unique_session_ids:
        items = build_delivery_preset_items(session_id=session_id, output_root=output_root, preset=preset)
        try:
            catalog_payload = load_session_catalog(session_id, output_root=output_root).model_dump()
        except FileNotFoundError:
            catalog_payload = None
        archive_path = export_session_package(
            session_id=session_id,
            output_root=output_root,
            items=items,
            label=f"{preset}_{session_id}",
            metadata={
                "preset": preset,
                "batch_id": batch_id,
                "delivery_profile": delivery_profile_spec(preset),
                "catalog": catalog_payload,
            },
        )
        records.append(
            {
                "session_id": session_id,
                "output_root": str(output_root_path),
                "archive_path": str(archive_path),
                "file_name": archive_path.name,
                "file_count": len(items),
                "catalog": catalog_payload,
            }
        )

    report_path = report_dir / f"{batch_id}_report.json"
    report_path.write_text(
        json.dumps(
            {
                "output_root": str(output_root_path),
                "preset": preset,
                "batch_id": batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_count": len(records),
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "output_root": str(output_root_path),
        "preset": preset,
        "delivery_profile": delivery_profile_spec(preset),
        "batch_id": batch_id,
        "session_count": len(records),
        "report_path": str(report_path),
        "records": records,
    }
