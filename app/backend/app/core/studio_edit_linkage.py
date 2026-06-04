from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .rawprep_contract import build_directory_layout
from .studio_paths import resolve_output_path, resolve_output_root
from .studio_selection_service import StudioSelectionState, load_session_selection_state


class StudioEditLinkageState(BaseModel):
    session_id: str
    output_root: str
    linkage_root: str
    state_path: str
    current_source_path: str | None = None
    current_source_kind: str | None = None
    current_source_label: str | None = None
    active_tool: str | None = None
    latest_job_id: str | None = None
    latest_tool: str | None = None
    latest_prompt: str | None = None
    latest_background_cutout_paths: list[str] = Field(default_factory=list)
    latest_generated_candidate_paths: list[str] = Field(default_factory=list)
    latest_linked_mask_paths: list[str] = Field(default_factory=list)
    selection_source_mask_path: str | None = None
    selection_current_mask_path: str | None = None
    selection_preview_path: str | None = None
    selection_summary: str | None = None
    source_history: list[str] = Field(default_factory=list)
    source_history_index: int = -1
    mask_ready: bool = False
    dreamgen_ready: bool = False
    current_source_matches_generated: bool = False
    current_source_matches_cutout: bool = False
    summary: str
    next_step: str
    updated_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def linkage_root_for(*, session_id: str, output_root: str) -> Path:
    layout = build_directory_layout(output_root, session_id)
    return Path(layout.ai_dir) / "edit_linkage"


def linkage_state_path_for(linkage_root: Path) -> Path:
    return linkage_root / "dreamgen_edit_linkage.json"


def _normalize_optional_path(value: str | None, *, output_root: str) -> str | None:
    if not value:
        return None
    return str(resolve_output_path(value, output_root=output_root))


def _normalize_path_list(paths: list[str] | None, *, output_root: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in paths or []:
        if not raw_path:
            continue
        resolved = str(resolve_output_path(raw_path, output_root=output_root))
        if resolved in seen:
            continue
        seen.add(resolved)
        normalized.append(resolved)
    return normalized


def _job_value(job: Any, key: str, default: Any = None) -> Any:
    if job is None:
        return default
    if isinstance(job, dict):
        return job.get(key, default)
    return getattr(job, key, default)


def _normalize_job_paths(job: Any, *, output_root: str) -> dict[str, list[str] | str | None]:
    outputs = _job_value(job, "outputs", []) or []
    background_cutouts: list[str] = []
    generated_candidates: list[str] = []
    linked_masks: list[str] = []

    for output in outputs:
        path = _job_value(output, "path")
        normalized_path = _normalize_optional_path(path, output_root=output_root)
        if not normalized_path:
            continue
        kind = _job_value(output, "kind")
        if kind == "background_cutout":
            background_cutouts.append(normalized_path)
        elif kind == "generated_candidate":
            generated_candidates.append(normalized_path)
        linked_mask_path = _normalize_optional_path(_job_value(output, "linked_mask_path"), output_root=output_root)
        if linked_mask_path:
            linked_masks.append(linked_mask_path)

    return {
        "latest_job_id": _job_value(job, "job_id"),
        "latest_tool": _job_value(job, "tool"),
        "latest_prompt": _job_value(job, "prompt"),
        "latest_background_cutout_paths": background_cutouts,
        "latest_generated_candidate_paths": generated_candidates,
        "latest_linked_mask_paths": linked_masks,
    }


def _load_selection_state_or_none(session_id: str, *, output_root: str) -> StudioSelectionState | None:
    try:
        return load_session_selection_state(session_id, output_root=output_root)
    except FileNotFoundError:
        return None


def load_session_edit_linkage(session_id: str, *, output_root: str = "outputs") -> StudioEditLinkageState:
    linkage_root = linkage_root_for(session_id=session_id, output_root=output_root)
    state_path = linkage_state_path_for(linkage_root)
    if not state_path.exists():
        raise FileNotFoundError(f"DreamGen edit linkage state was not found for session: {session_id}")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["output_root"] = str(resolve_output_root(payload.get("output_root", output_root)))
    for key in (
        "linkage_root",
        "state_path",
        "current_source_path",
        "selection_source_mask_path",
        "selection_current_mask_path",
        "selection_preview_path",
    ):
        payload[key] = _normalize_optional_path(payload.get(key), output_root=payload["output_root"])
    for key in (
        "latest_background_cutout_paths",
        "latest_generated_candidate_paths",
        "latest_linked_mask_paths",
        "source_history",
    ):
        payload[key] = _normalize_path_list(payload.get(key), output_root=payload["output_root"])
    return StudioEditLinkageState(**payload)


def _current_source_kind(
    current_source_path: str | None,
    *,
    selection_preview_path: str | None,
    generated_candidates: list[str],
    background_cutouts: list[str],
) -> tuple[str | None, str | None]:
    if not current_source_path:
        return None, None
    if selection_preview_path and current_source_path == selection_preview_path:
        return "selection_preview", "현재 선택 미리보기 사용 중"
    if current_source_path in generated_candidates:
        return "generated_candidate", "생성 편집 결과 사용 중"
    if current_source_path in background_cutouts:
        return "background_cutout", "배경 분리 결과 사용 중"
    return "working_source", "현재 작업 소스 사용 중"


def _build_linkage_summary(
    *,
    current_source_path: str | None,
    current_source_kind: str | None,
    latest_tool: str | None,
    mask_ready: bool,
    dreamgen_ready: bool,
    current_source_matches_generated: bool,
    current_source_matches_cutout: bool,
    generated_count: int,
) -> tuple[str, str]:
    if current_source_matches_generated and mask_ready:
        return (
            "선택 마스크를 유지한 생성 편집 결과가 현재 작업 소스로 연결되어 있습니다.",
            "현재 결과를 기준으로 비교 보기와 추가 리터치를 이어가면 됩니다.",
        )
    if dreamgen_ready and mask_ready:
        return (
            f"선택 마스크를 기준으로 만든 생성 편집 후보 {generated_count}개가 준비되어 있습니다.",
            "대표 후보를 비교한 뒤 작업 소스로 채택해 편집 단계를 이어가면 됩니다.",
        )
    if current_source_matches_cutout and mask_ready:
        return (
            "배경 분리 결과와 현재 선택 기준이 연결되어 다음 생성 편집으로 바로 넘어갈 수 있습니다.",
            "배경 교체나 선택 영역 채우기처럼 마스크를 쓰는 생성 편집을 실행하면 됩니다.",
        )
    if mask_ready and latest_tool in {"replaceBg", "replaceObject", "expandCanvas"}:
        return (
            "마스크 기준은 준비되어 있지만 현재 작업 소스는 아직 생성 편집 결과로 채택되지 않았습니다.",
            "생성 편집 후보를 비교해서 현재 작업 소스로 채택하면 DreamGen 흐름이 완성됩니다.",
        )
    if mask_ready:
        return (
            "현재 선택 기준이 준비되어 있어 DreamGen 생성 편집으로 이어갈 수 있습니다.",
            "배경 교체, 선택 영역 채우기, 화면 확장 중 하나를 실행해 후보를 만들면 됩니다.",
        )
    if current_source_path and current_source_kind == "working_source":
        return (
            "현재 작업 소스는 유지되고 있지만, DreamGen과 연결할 마스크 기준이 아직 없습니다.",
            "배경 제거 결과에서 마스크를 고르거나 선택 기준을 먼저 적용해 주세요.",
        )
    return (
        "DreamGen과 마스크 편집 연결 근거가 아직 충분히 준비되지 않았습니다.",
        "배경 제거 결과에서 마스크를 고르고 선택 기준을 저장한 뒤 생성 편집을 실행해 주세요.",
    )


def build_or_update_session_edit_linkage(
    session_id: str,
    *,
    output_root: str = "outputs",
    current_source_path: str | None = None,
    active_tool: str | None = None,
    studio_job_record: Any | None = None,
    selection_state: StudioSelectionState | None = None,
    source_history: list[str] | None = None,
    source_history_index: int | None = None,
) -> StudioEditLinkageState:
    resolved_output_root = str(resolve_output_root(output_root))
    linkage_root = linkage_root_for(session_id=session_id, output_root=resolved_output_root)
    linkage_root.mkdir(parents=True, exist_ok=True)
    state_path = linkage_state_path_for(linkage_root)

    previous_state: StudioEditLinkageState | None = None
    if state_path.exists():
        try:
            previous_state = load_session_edit_linkage(session_id, output_root=resolved_output_root)
        except Exception:
            previous_state = None

    current_selection = selection_state or _load_selection_state_or_none(session_id, output_root=resolved_output_root)
    selection_source_mask_path = (
        _normalize_optional_path(current_selection.source_mask_path, output_root=resolved_output_root)
        if current_selection
        else previous_state.selection_source_mask_path if previous_state else None
    )
    selection_current_mask_path = (
        _normalize_optional_path(current_selection.current_mask_path, output_root=resolved_output_root)
        if current_selection
        else previous_state.selection_current_mask_path if previous_state else None
    )
    selection_preview_path = (
        _normalize_optional_path(current_selection.preview_path, output_root=resolved_output_root)
        if current_selection
        else previous_state.selection_preview_path if previous_state else None
    )
    selection_summary = (
        current_selection.summary
        if current_selection
        else previous_state.selection_summary if previous_state else None
    )

    job_payload = _normalize_job_paths(studio_job_record, output_root=resolved_output_root) if studio_job_record else {
        "latest_job_id": previous_state.latest_job_id if previous_state else None,
        "latest_tool": previous_state.latest_tool if previous_state else None,
        "latest_prompt": previous_state.latest_prompt if previous_state else None,
        "latest_background_cutout_paths": previous_state.latest_background_cutout_paths if previous_state else [],
        "latest_generated_candidate_paths": previous_state.latest_generated_candidate_paths if previous_state else [],
        "latest_linked_mask_paths": previous_state.latest_linked_mask_paths if previous_state else [],
    }

    normalized_current_source = _normalize_optional_path(current_source_path, output_root=resolved_output_root)
    normalized_history = _normalize_path_list(
        source_history if source_history is not None else (previous_state.source_history if previous_state else []),
        output_root=resolved_output_root,
    )
    normalized_history_index = source_history_index if source_history_index is not None else (
        previous_state.source_history_index if previous_state else -1
    )
    if normalized_history:
        normalized_history_index = max(0, min(int(normalized_history_index), len(normalized_history) - 1))
    else:
        normalized_history_index = -1

    current_source_kind, current_source_label = _current_source_kind(
        normalized_current_source,
        selection_preview_path=selection_preview_path,
        generated_candidates=job_payload["latest_generated_candidate_paths"],
        background_cutouts=job_payload["latest_background_cutout_paths"],
    )
    current_source_matches_generated = bool(
        normalized_current_source and normalized_current_source in job_payload["latest_generated_candidate_paths"]
    )
    current_source_matches_cutout = bool(
        normalized_current_source and normalized_current_source in job_payload["latest_background_cutout_paths"]
    )
    mask_ready = bool(selection_current_mask_path or selection_source_mask_path or job_payload["latest_linked_mask_paths"])
    dreamgen_ready = bool(job_payload["latest_generated_candidate_paths"])
    summary, next_step = _build_linkage_summary(
        current_source_path=normalized_current_source,
        current_source_kind=current_source_kind,
        latest_tool=active_tool or job_payload["latest_tool"],
        mask_ready=mask_ready,
        dreamgen_ready=dreamgen_ready,
        current_source_matches_generated=current_source_matches_generated,
        current_source_matches_cutout=current_source_matches_cutout,
        generated_count=len(job_payload["latest_generated_candidate_paths"]),
    )

    state = StudioEditLinkageState(
        session_id=session_id,
        output_root=resolved_output_root,
        linkage_root=str(linkage_root),
        state_path=str(state_path),
        current_source_path=normalized_current_source,
        current_source_kind=current_source_kind,
        current_source_label=current_source_label,
        active_tool=active_tool or _job_value(studio_job_record, "tool") or (previous_state.active_tool if previous_state else None),
        latest_job_id=job_payload["latest_job_id"],
        latest_tool=job_payload["latest_tool"],
        latest_prompt=job_payload["latest_prompt"],
        latest_background_cutout_paths=job_payload["latest_background_cutout_paths"],
        latest_generated_candidate_paths=job_payload["latest_generated_candidate_paths"],
        latest_linked_mask_paths=job_payload["latest_linked_mask_paths"],
        selection_source_mask_path=selection_source_mask_path,
        selection_current_mask_path=selection_current_mask_path,
        selection_preview_path=selection_preview_path,
        selection_summary=selection_summary,
        source_history=normalized_history,
        source_history_index=normalized_history_index,
        mask_ready=mask_ready,
        dreamgen_ready=dreamgen_ready,
        current_source_matches_generated=current_source_matches_generated,
        current_source_matches_cutout=current_source_matches_cutout,
        summary=summary,
        next_step=next_step,
        updated_at=utc_now_iso(),
    )
    state_path.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return state
