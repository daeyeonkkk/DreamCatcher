from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SceneLinearFormat = Literal["exr", "tiff"]

PHASE0_ARTIFACT_SCHEMA_ID = "dreamcatcher.raw_engine_v2.artifacts"
PHASE0_ARTIFACT_SCHEMA_VERSION = "2026-04-06"


class ArtifactSlot(BaseModel):
    key: str
    relative_path: str
    required: bool = True
    content_type: str
    description: str


class DiagnosticSlot(BaseModel):
    key: str
    relative_path: str
    required: bool = False
    description: str


class RawEngineArtifactSchema(BaseModel):
    schema_id: str
    schema_version: str
    scene_linear_preferred_format: SceneLinearFormat = "exr"
    scene_linear_fallback_format: SceneLinearFormat = "tiff"
    required_slots: list[ArtifactSlot]
    optional_diagnostics: list[DiagnosticSlot] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def slot_keys(self) -> list[str]:
        return [slot.key for slot in self.required_slots]

    def slot(self, key: str) -> ArtifactSlot:
        for slot in self.required_slots:
            if slot.key == key:
                return slot
        raise KeyError(f"Unknown artifact slot: {key}")

    def expected_paths(self, scene_linear_format: SceneLinearFormat | None = None) -> dict[str, str]:
        selected_format = scene_linear_format or self.scene_linear_preferred_format
        paths: dict[str, str] = {}
        for slot in self.required_slots:
            if slot.key == "scene_linear":
                paths[slot.key] = f"scene_linear.{selected_format}"
                continue
            paths[slot.key] = slot.relative_path
        return paths


def build_phase0_artifact_schema() -> RawEngineArtifactSchema:
    return RawEngineArtifactSchema(
        schema_id=PHASE0_ARTIFACT_SCHEMA_ID,
        schema_version=PHASE0_ARTIFACT_SCHEMA_VERSION,
        required_slots=[
            ArtifactSlot(
                key="preview",
                relative_path="preview.jpg",
                content_type="image/jpeg",
                description="Fast human-readable preview for compare, queue, and export surfaces.",
            ),
            ArtifactSlot(
                key="scene_linear",
                relative_path="scene_linear.exr",
                content_type="image/x-exr",
                description="Shared scene-linear intermediate that bridges RAW restoration and ISP rendering.",
            ),
            ArtifactSlot(
                key="report",
                relative_path="report.json",
                content_type="application/json",
                description="Structured processing report including engine identity, mode, warnings, and timing.",
            ),
            ArtifactSlot(
                key="diagnostics_manifest",
                relative_path="diagnostics/manifest.json",
                content_type="application/json",
                description="Manifest for every optional diagnostic artifact emitted by the engine.",
            ),
        ],
        optional_diagnostics=[
            DiagnosticSlot(
                key="noise_map",
                relative_path="diagnostics/noise_map.png",
                description="Noise estimate or denoise attention visualization.",
            ),
            DiagnosticSlot(
                key="motion_map",
                relative_path="diagnostics/motion_map.png",
                description="Motion or alignment diagnostic for bracketed RAW groups.",
            ),
            DiagnosticSlot(
                key="confidence_map",
                relative_path="diagnostics/confidence_map.exr",
                description="Confidence or uncertainty visualization for fusion and fallback decisions.",
            ),
        ],
        notes=[
            "All engine outputs are rooted per single RAW item or per bracket group.",
            "scene_linear prefers EXR and may fall back to TIFF when EXR is unavailable in the runtime.",
            "diagnostics/manifest.json is required even when the engine emits no optional diagnostic images.",
        ],
    )


PHASE0_ARTIFACT_SCHEMA = build_phase0_artifact_schema()

