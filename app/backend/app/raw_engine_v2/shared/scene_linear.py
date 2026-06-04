from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .artifact_schema import PHASE0_ARTIFACT_SCHEMA, SceneLinearFormat
from .lens_correction import LensCorrectionPlan
from .metadata import NormalizedRawMetadata
from .noise_model import NoiseProfile


MODULE_STATUS = "phase1_foundation"
PREFERRED_SCENE_LINEAR_EXTENSION = "exr"
FALLBACK_SCENE_LINEAR_EXTENSION = "tiff"


@dataclass(frozen=True)
class SceneLinearSpec:
    artifact_key: str
    preferred_format: SceneLinearFormat
    fallback_format: SceneLinearFormat
    relative_path: str
    working_space: str
    channel_layout: str
    notes: tuple[str, ...] = ()

    def path_for(self, scene_linear_format: SceneLinearFormat | None = None) -> str:
        selected_format = scene_linear_format or self.preferred_format
        return PHASE0_ARTIFACT_SCHEMA.expected_paths(selected_format)[self.artifact_key]


@dataclass(frozen=True)
class SceneLinearBuildPlan:
    source_path: str | None
    target_relative_path: str
    preferred_format: SceneLinearFormat
    fallback_format: SceneLinearFormat
    cfa_pattern: str
    reference_black_level: float
    white_level: float
    noise_model_key: str
    distortion_model: str
    notes: tuple[str, ...] = ()


def build_scene_linear_spec(
    *,
    preferred_format: SceneLinearFormat | None = None,
) -> SceneLinearSpec:
    selected_format = preferred_format or PHASE0_ARTIFACT_SCHEMA.scene_linear_preferred_format
    return SceneLinearSpec(
        artifact_key="scene_linear",
        preferred_format=selected_format,
        fallback_format=PHASE0_ARTIFACT_SCHEMA.scene_linear_fallback_format,
        relative_path=PHASE0_ARTIFACT_SCHEMA.expected_paths(selected_format)["scene_linear"],
        working_space="camera_native_scene_linear",
        channel_layout="R,G1,G2,B",
        notes=tuple(PHASE0_ARTIFACT_SCHEMA.notes),
    )


def normalize_sensor_value(value: float, *, black_level: float, white_level: float) -> float:
    if white_level <= black_level:
        return 0.0
    normalized = (float(value) - float(black_level)) / (float(white_level) - float(black_level))
    return min(max(normalized, 0.0), 1.0)


def normalize_sensor_channels(
    values: Sequence[float],
    metadata: NormalizedRawMetadata,
) -> tuple[float, ...]:
    if not values:
        raise ValueError("Scene-linear normalization requires at least one sensor value")

    normalized_values: list[float] = []
    for index, value in enumerate(values):
        black_level = metadata.black_level[min(index, len(metadata.black_level) - 1)]
        normalized_values.append(
            normalize_sensor_value(
                float(value),
                black_level=black_level,
                white_level=metadata.white_level,
            )
        )
    return tuple(normalized_values)


def build_scene_linear_plan(
    metadata: NormalizedRawMetadata,
    *,
    noise_profile: NoiseProfile | None = None,
    lens_correction: LensCorrectionPlan | None = None,
    preferred_format: SceneLinearFormat | None = None,
) -> SceneLinearBuildPlan:
    spec = build_scene_linear_spec(preferred_format=preferred_format)
    notes = list(spec.notes)
    notes.extend(metadata.notes)
    if noise_profile is not None:
        notes.extend(noise_profile.notes)
    if lens_correction is not None:
        notes.extend(lens_correction.notes)

    return SceneLinearBuildPlan(
        source_path=metadata.source_path,
        target_relative_path=spec.relative_path,
        preferred_format=spec.preferred_format,
        fallback_format=spec.fallback_format,
        cfa_pattern=metadata.cfa_pattern,
        reference_black_level=metadata.reference_black_level(),
        white_level=metadata.white_level,
        noise_model_key=noise_profile.model_key if noise_profile is not None else "unassigned",
        distortion_model=lens_correction.distortion_model if lens_correction is not None else "identity",
        notes=tuple(dict.fromkeys(notes)),
    )
