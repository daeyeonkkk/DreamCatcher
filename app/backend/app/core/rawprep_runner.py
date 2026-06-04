from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel

from .rawprep_catalog import legacy_removed_note, preview_runtime_note, raw_engine_binary_name
from .rawprep_contract import RawPrepArtifact, RawPrepBracketRequest, RawPrepJobPlan, ReferencePolicy


class RawPrepToolStatus(BaseModel):
    name: str
    available: bool
    resolved_path: str | None = None
    notes: str | None = None


class RawPrepCommandPreview(BaseModel):
    bracket_id: str
    step: str
    command: list[str]
    description: str


def artifact_map(plan: RawPrepJobPlan) -> dict[str, RawPrepArtifact]:
    return {artifact.kind: artifact for artifact in plan.expected_artifacts}


def resolve_binary(tool_name: str) -> str | None:
    return shutil.which(tool_name)


def detect_rawprep_tools(tool_names: list[str] | None = None) -> dict[str, RawPrepToolStatus]:
    engine_binary = raw_engine_binary_name()
    names = tool_names or ["exiftool", engine_binary]
    statuses: dict[str, RawPrepToolStatus] = {}
    for name in names:
        resolved = resolve_binary(name)
        statuses[name] = RawPrepToolStatus(
            name=name,
            available=resolved is not None,
            resolved_path=resolved,
            notes=None if resolved else legacy_removed_note() if name == engine_binary else "Tool not found.",
        )
    return statuses


def missing_required_tools(tool_status: dict[str, RawPrepToolStatus], required_tools: list[str]) -> list[str]:
    missing: list[str] = []
    for tool_name in required_tools:
        status = tool_status.get(tool_name)
        if status is None or not status.available:
            missing.append(tool_name)
    return missing


def reference_policy_index(reference_policy: ReferencePolicy, frame_count: int) -> int | None:
    if frame_count <= 0:
        return None
    if reference_policy == "first":
        return 0
    if reference_policy == "middle":
        return min(max(frame_count // 2, 0), frame_count - 1)
    if reference_policy == "last":
        return frame_count - 1
    return None


def select_reference_frame(group: RawPrepBracketRequest) -> str:
    index = reference_policy_index(group.reference_policy, len(group.raw_files))
    if index is None:
        index = min(len(group.raw_files) // 2, len(group.raw_files) - 1)
    return group.raw_files[index]


def build_rawprep_command_previews(
    plan: RawPrepJobPlan,
    *,
    tool_status: dict[str, RawPrepToolStatus] | None = None,
) -> list[RawPrepCommandPreview]:
    return [
        RawPrepCommandPreview(
            bracket_id=group.bracket_id,
            step="phase1_preview_runtime",
            command=["python", "-m", "app.queue_worker", "--output-root", plan.output_root],
            description=f"{preview_runtime_note()} 공통 산출물은 계속 {plan.engine.artifact_schema_id} 계약에 고정됩니다.",
        )
        for group in plan.groups
    ]


def required_tools_for_plan(_plan: RawPrepJobPlan) -> list[str]:
    return []
