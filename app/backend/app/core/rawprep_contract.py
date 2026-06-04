from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.raw_engine_v2.shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA
from app.raw_engine_v2.shared.engine_registry import get_engine_descriptor

from .rawprep_catalog import RawPrepQualityPreset, legacy_removed_note
from .raw_restoration_policy import DEFAULT_RAW_RESTORATION_GOAL, normalize_raw_restoration_goal
from .studio_paths import resolve_output_root


ReferencePolicy = Literal["auto", "first", "middle", "last"]
RawPrepRestorationGoal = Literal["truth_preserving", "aggressive_restore"]
DEFAULT_RAWPREP_ENGINE_STACK = "dreamraw_tri_v2"


class RawPrepBracketRequest(BaseModel):
    bracket_id: str = Field(default="bracket_01")
    raw_files: list[str] = Field(..., description="Exactly three or nine RAW file paths in bracket order.")
    reference_policy: ReferencePolicy = "auto"

    @field_validator("bracket_id")
    @classmethod
    def validate_bracket_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("bracket_id must not be empty")
        return normalized

    @field_validator("raw_files")
    @classmethod
    def validate_raw_files(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) not in {3, 9}:
            raise ValueError("raw_files must contain exactly three or nine RAW paths")
        return cleaned


class RawPrepEnginePlan(BaseModel):
    engine_stack: str = DEFAULT_RAWPREP_ENGINE_STACK
    engine_version: str = "2.0.0-phase0"
    engine_family: str = "tri_raw"
    develop_tool: str = "dreamisp_v2"
    metadata_tool: str = "exiftool"
    artifact_schema_id: str = PHASE0_ARTIFACT_SCHEMA.schema_id
    artifact_schema_version: str = PHASE0_ARTIFACT_SCHEMA.schema_version
    supported_modes: list[str] = Field(default_factory=list)
    camera_profile_request: str = "auto"
    camera_profile: str = "auto"
    quality_preset: RawPrepQualityPreset = "balanced"
    restoration_goal: RawPrepRestorationGoal = DEFAULT_RAW_RESTORATION_GOAL
    keep_intermediates: bool = True
    status: Literal["phase0_scaffold", "phase1_preview_runtime"] = "phase1_preview_runtime"
    notes: list[str] = Field(
        default_factory=lambda: [
            legacy_removed_note(),
            "TriRaw 미리보기 런타임으로 브라켓 분석, 보수 병합 미리보기, DreamISP handoff를 먼저 실행할 수 있습니다.",
            "실행형 TriRaw 엔진이 올라오기 전에 v2 공통 artifact schema를 먼저 고정합니다.",
        ]
    )


class RawPrepArtifact(BaseModel):
    bracket_id: str
    kind: str
    path: str
    required: bool = False
    content_type: str | None = None
    notes: str | None = None


class RawPrepDirectoryLayout(BaseModel):
    session_root: str
    input_dir: str
    rawprep_dir: str
    manual_dir: str
    ai_dir: str
    export_dir: str


class RawPrepJobRequest(BaseModel):
    session_id: str | None = None
    output_root: str = "outputs"
    quality_preset: RawPrepQualityPreset = "balanced"
    restoration_goal: RawPrepRestorationGoal = DEFAULT_RAW_RESTORATION_GOAL
    engine_stack: str = DEFAULT_RAWPREP_ENGINE_STACK
    keep_intermediates: bool = True
    camera_profile: str | None = "auto"
    groups: list[RawPrepBracketRequest]

    @field_validator("output_root")
    @classmethod
    def validate_output_root(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("output_root must not be empty")
        return normalized

    @field_validator("engine_stack")
    @classmethod
    def validate_engine_stack(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("engine_stack must not be empty")
        try:
            descriptor = get_engine_descriptor(normalized)
        except KeyError as exc:
            raise ValueError(f"unknown engine_stack: {normalized}") from exc
        if descriptor.family != "tri_raw":
            raise ValueError("rawprep jobs currently require a tri_raw engine stack")
        return normalized

    @field_validator("restoration_goal")
    @classmethod
    def validate_restoration_goal(cls, value: RawPrepRestorationGoal) -> RawPrepRestorationGoal:
        return normalize_raw_restoration_goal(value)  # type: ignore[return-value]

    @field_validator("groups")
    @classmethod
    def validate_groups(cls, value: list[RawPrepBracketRequest]) -> list[RawPrepBracketRequest]:
        if not value:
            raise ValueError("at least one bracket group is required")
        return value


class RawPrepJobPlan(BaseModel):
    job_id: str
    session_id: str
    output_root: str
    camera_profile: str | None = None
    restoration_goal: RawPrepRestorationGoal = DEFAULT_RAW_RESTORATION_GOAL
    layout: RawPrepDirectoryLayout
    engine: RawPrepEnginePlan
    groups: list[RawPrepBracketRequest]
    expected_artifacts: list[RawPrepArtifact]
    notes: list[str] = Field(default_factory=list)


def default_session_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("session_%Y%m%d_%H%M%S")


def build_directory_layout(output_root: str, session_id: str) -> RawPrepDirectoryLayout:
    session_root = resolve_output_root(output_root) / session_id
    return RawPrepDirectoryLayout(
        session_root=str(session_root),
        input_dir=str(session_root / "00_input"),
        rawprep_dir=str(session_root / "01_rawprep"),
        manual_dir=str(session_root / "02_manual"),
        ai_dir=str(session_root / "03_ai"),
        export_dir=str(session_root / "04_export"),
    )


def build_group_artifacts(layout: RawPrepDirectoryLayout, group: RawPrepBracketRequest) -> list[RawPrepArtifact]:
    group_root = Path(layout.rawprep_dir) / group.bracket_id
    artifacts: list[RawPrepArtifact] = []

    for slot in PHASE0_ARTIFACT_SCHEMA.required_slots:
        artifacts.append(
            RawPrepArtifact(
                bracket_id=group.bracket_id,
                kind=slot.key,
                path=str(group_root / slot.relative_path),
                required=slot.required,
                content_type=slot.content_type,
                notes=slot.description,
            )
        )

    for diagnostic in PHASE0_ARTIFACT_SCHEMA.optional_diagnostics:
        artifacts.append(
            RawPrepArtifact(
                bracket_id=group.bracket_id,
                kind=diagnostic.key,
                path=str(group_root / diagnostic.relative_path),
                required=diagnostic.required,
                notes=diagnostic.description,
            )
        )

    return artifacts


def build_job_plan(request: RawPrepJobRequest) -> RawPrepJobPlan:
    session_id = request.session_id or default_session_id()
    layout = build_directory_layout(request.output_root, session_id)
    descriptor = get_engine_descriptor(request.engine_stack)
    engine = RawPrepEnginePlan(
        engine_stack=descriptor.key,
        engine_version=descriptor.version,
        engine_family=descriptor.family,
        develop_tool="dreamisp_v2",
        artifact_schema_id=descriptor.artifact_schema_id,
        artifact_schema_version=descriptor.artifact_schema_version,
        supported_modes=list(descriptor.supported_modes),
        camera_profile_request=(request.camera_profile or "auto").strip(),
        camera_profile=(request.camera_profile or "auto").strip(),
        quality_preset=request.quality_preset,
        restoration_goal=request.restoration_goal,
        keep_intermediates=request.keep_intermediates,
        notes=[
            legacy_removed_note(),
            f"Locked to artifact schema {descriptor.artifact_schema_id}:{descriptor.artifact_schema_version}.",
            f"Planned engine target: {descriptor.display_name} ({descriptor.version}).",
        ],
    )
    return RawPrepJobPlan(
        job_id=str(uuid4()),
        session_id=session_id,
        output_root=request.output_root,
        camera_profile=request.camera_profile,
        restoration_goal=request.restoration_goal,
        layout=layout,
        engine=engine,
        groups=request.groups,
        expected_artifacts=[artifact for group in request.groups for artifact in build_group_artifacts(layout, group)],
        notes=[
            legacy_removed_note(),
            "Use PROJECT_FOUNDATION as the source of truth while the executable tri-RAW engine is still scaffolded.",
        ],
    )
