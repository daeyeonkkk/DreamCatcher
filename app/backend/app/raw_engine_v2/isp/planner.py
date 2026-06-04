from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.raw_engine_v2.shared.engine_registry import get_engine_descriptor


MODULE_STATUS = "phase1_foundation"


class DreamISPExpectedFile(BaseModel):
    kind: str
    path: str
    required: bool = False
    notes: str | None = None


class DreamISPHandoffPlan(BaseModel):
    engine_key: str
    engine_version: str
    engine_lifecycle: str
    status: Literal["phase1_foundation"] = "phase1_foundation"
    materialization_status: Literal["planned", "handoff_written", "preview_rendered"] = "planned"
    source_stage: Literal["single_raw", "tri_raw"]
    source_item_key: str
    source_engine_key: str
    source_engine_version: str
    session_root: str
    working_root: str
    plan_path: str
    render_state_path: str
    report_path: str
    scene_linear_path: str
    scene_linear_exists: bool
    preview_path: str | None = None
    preview_exists: bool = False
    recommended_editable_source_path: str | None = None
    render_preview_path: str | None = None
    render_preview_exists: bool = False
    render_source_kind: Literal["scene_linear", "preview_proxy"] | None = None
    render_backend: str | None = None
    source_report_path: str | None = None
    source_diagnostics_manifest_path: str | None = None
    render_state: dict[str, Any]
    expected_files: list[DreamISPExpectedFile] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _handoff_root(session_root: str | Path, source_item_key: str) -> Path:
    return Path(session_root) / "02_manual" / source_item_key


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_recommended_editable_source(scene_linear_path: Path, preview_path: Path | None) -> str | None:
    if preview_path is not None and preview_path.is_file():
        return str(preview_path)
    if scene_linear_path.is_file():
        return str(scene_linear_path)
    return None


def build_dreamisp_handoff_plan(
    *,
    session_root: str | Path,
    source_stage: Literal["single_raw", "tri_raw"],
    source_item_key: str,
    source_engine_key: str,
    source_engine_version: str,
    scene_linear_path: str,
    preview_path: str | None = None,
    source_report_path: str | None = None,
    source_diagnostics_manifest_path: str | None = None,
) -> DreamISPHandoffPlan:
    engine = get_engine_descriptor("dreamisp_v2")
    resolved_session_root = Path(session_root)
    resolved_scene_linear_path = Path(scene_linear_path)
    resolved_preview_path = Path(preview_path) if preview_path else None
    working_root = _handoff_root(resolved_session_root, source_item_key)
    plan_path = working_root / "dreamisp_plan.json"
    render_state_path = working_root / "editable_render_state.json"
    report_path = working_root / "report.json"
    recommended_source_path = _resolve_recommended_editable_source(
        resolved_scene_linear_path,
        resolved_preview_path,
    )

    render_state = {
        "render_state_id": "dreamisp_lite_v2",
        "source": {
            "scene_linear_path": str(resolved_scene_linear_path),
            "preview_proxy_path": str(resolved_preview_path) if resolved_preview_path is not None else None,
            "recommended_editable_source_path": recommended_source_path,
        },
        "white_balance": {
            "mode": "as_shot",
            "temperature_delta": 0.0,
            "tint_delta": 0.0,
        },
        "tone": {
            "exposure_ev": 0.0,
            "contrast": 0.0,
            "highlights": 0.0,
            "shadows": 0.0,
            "whites": 0.0,
            "blacks": 0.0,
        },
        "color": {
            "saturation": 0.0,
            "vibrance": 0.0,
        },
        "detail": {
            "clarity": 0.0,
            "dehaze": 0.0,
        },
        "non_destructive": True,
        "editable": True,
    }
    expected_files = [
        DreamISPExpectedFile(
            kind="plan",
            path=str(plan_path),
            required=True,
            notes="상위 장면 선형 소스와 편집 진입 지점을 고정하는 DreamISP handoff 계획입니다.",
        ),
        DreamISPExpectedFile(
            kind="editable_render_state",
            path=str(render_state_path),
            required=True,
            notes="Phase 3의 실제 렌더와 UI 슬라이더가 그대로 재사용할 수 있는 DreamISP-lite 편집 상태입니다.",
        ),
        DreamISPExpectedFile(
            kind="report",
            path=str(report_path),
            required=True,
            notes="어떤 상위 산출물이 DreamISP 준비 상태인지 설명하는 구조화 handoff 보고서입니다.",
        ),
        DreamISPExpectedFile(
            kind="editable_preview",
            path=str(working_root / "editable_preview.jpg"),
            required=False,
            notes="Studio의 현재 편집 소스로 이어지는 DreamISP-lite 렌더 미리보기입니다.",
        ),
    ]
    notes = [
        "DreamISP handoff 계획은 장면 선형 마스터를 정식 기준으로 유지하고, 편집 소스는 비파괴 상태로 남깁니다.",
        "DreamISP-lite가 실제 편집 렌더를 만들기 시작하면 Phase 3가 이 렌더 상태 계약을 그대로 재사용합니다.",
    ]
    if not resolved_scene_linear_path.is_file():
        notes.append("장면 선형 마스터가 아직 실제 산출물로 만들어지지 않아, 상위 엔진이 기록할 때까지 이 handoff는 안내 정보로만 유지됩니다.")
    if resolved_preview_path is not None and resolved_preview_path.is_file():
        notes.append("미리보기 프록시가 있어 DreamISP가 장면 선형 마스터를 추적하는 동안에도 Studio는 현재 편집 진입 지점을 유지할 수 있습니다.")

    return DreamISPHandoffPlan(
        engine_key=engine.key,
        engine_version=engine.version,
        engine_lifecycle=engine.lifecycle,
        source_stage=source_stage,
        source_item_key=source_item_key,
        source_engine_key=source_engine_key,
        source_engine_version=source_engine_version,
        session_root=str(resolved_session_root),
        working_root=str(working_root),
        plan_path=str(plan_path),
        render_state_path=str(render_state_path),
        report_path=str(report_path),
        scene_linear_path=str(resolved_scene_linear_path),
        scene_linear_exists=resolved_scene_linear_path.is_file(),
        preview_path=str(resolved_preview_path) if resolved_preview_path is not None else None,
        preview_exists=resolved_preview_path.is_file() if resolved_preview_path is not None else False,
        recommended_editable_source_path=recommended_source_path,
        source_report_path=source_report_path,
        source_diagnostics_manifest_path=source_diagnostics_manifest_path,
        render_state=render_state,
        expected_files=expected_files,
        notes=notes,
    )


def materialize_dreamisp_handoff_plan(plan: DreamISPHandoffPlan) -> DreamISPHandoffPlan:
    payload = plan.model_dump()
    payload["materialization_status"] = "handoff_written"
    updated_plan = DreamISPHandoffPlan(**payload)

    _write_json(Path(updated_plan.render_state_path), updated_plan.render_state)

    report_payload = {
        "engine_key": updated_plan.engine_key,
        "engine_version": updated_plan.engine_version,
        "status": updated_plan.materialization_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_stage": updated_plan.source_stage,
        "source_item_key": updated_plan.source_item_key,
        "source_engine_key": updated_plan.source_engine_key,
        "source_engine_version": updated_plan.source_engine_version,
        "scene_linear_path": updated_plan.scene_linear_path,
        "scene_linear_exists": updated_plan.scene_linear_exists,
        "preview_path": updated_plan.preview_path,
        "preview_exists": updated_plan.preview_exists,
        "recommended_editable_source_path": updated_plan.recommended_editable_source_path,
        "render_preview_path": updated_plan.render_preview_path,
        "render_preview_exists": updated_plan.render_preview_exists,
        "render_source_kind": updated_plan.render_source_kind,
        "render_backend": updated_plan.render_backend,
        "handoff_ready": updated_plan.scene_linear_exists,
        "source_report_path": updated_plan.source_report_path,
        "source_diagnostics_manifest_path": updated_plan.source_diagnostics_manifest_path,
        "notes": [
            *updated_plan.notes,
            "DreamISP 보고서는 현재 편집 렌더 계약만 기록하며, 렌더 미리보기 파이프라인이 이미 완성됐다고 주장하지 않습니다.",
        ],
    }
    _write_json(Path(updated_plan.report_path), report_payload)
    _write_json(Path(updated_plan.plan_path), updated_plan.model_dump())
    return updated_plan
