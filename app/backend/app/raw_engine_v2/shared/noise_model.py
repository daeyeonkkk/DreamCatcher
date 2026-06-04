from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .metadata import NormalizedRawMetadata


MODULE_STATUS = "phase1_foundation"


@dataclass(frozen=True)
class NoiseProfile:
    camera_key: str
    lens_key: str
    iso: int
    exposure_seconds: float
    bit_depth: int
    shot_noise_scale: float
    read_noise_scale: float
    row_noise_scale: float
    black_offset: float
    white_level: float
    confidence: float
    model_key: str = "phase1_deterministic_noise_profile"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BracketNoiseSummary:
    frame_count: int
    iso_values: tuple[int, ...]
    peak_shot_noise_scale: float
    peak_read_noise_scale: float
    quietest_frame_index: int
    notes: tuple[str, ...] = ()


def estimate_noise_profile(metadata: NormalizedRawMetadata) -> NoiseProfile:
    analog_gain = max(metadata.iso / 100.0, 1.0)
    dynamic_range = metadata.dynamic_range_code_values()
    shot_noise_scale = analog_gain / dynamic_range
    read_noise_scale = (1.25 + math.sqrt(analog_gain) * 0.85) / dynamic_range
    row_noise_scale = read_noise_scale * 0.35

    confidence = 0.55
    notes: list[str] = []
    if metadata.cfa_pattern != "unknown":
        confidence += 0.15
    else:
        notes.append("Noise profile confidence is reduced because CFA metadata is missing.")
    if metadata.lens_key != "unknown":
        confidence += 0.05
    if metadata.bit_depth >= 12:
        confidence += 0.1
    if metadata.white_level > metadata.reference_black_level() + 1024:
        confidence += 0.1

    return NoiseProfile(
        camera_key=metadata.camera_key,
        lens_key=metadata.lens_key,
        iso=metadata.iso,
        exposure_seconds=metadata.exposure_seconds,
        bit_depth=metadata.bit_depth,
        shot_noise_scale=shot_noise_scale,
        read_noise_scale=read_noise_scale,
        row_noise_scale=row_noise_scale,
        black_offset=metadata.reference_black_level(),
        white_level=metadata.white_level,
        confidence=min(confidence, 0.95),
        notes=tuple(notes),
    )


def summarize_bracket_noise(profiles: Sequence[NoiseProfile]) -> BracketNoiseSummary:
    if not profiles:
        raise ValueError("Bracket noise summary requires at least one per-frame noise profile")

    quietest_frame_index = min(range(len(profiles)), key=lambda index: profiles[index].read_noise_scale)
    return BracketNoiseSummary(
        frame_count=len(profiles),
        iso_values=tuple(profile.iso for profile in profiles),
        peak_shot_noise_scale=max(profile.shot_noise_scale for profile in profiles),
        peak_read_noise_scale=max(profile.read_noise_scale for profile in profiles),
        quietest_frame_index=quietest_frame_index,
        notes=tuple(
            note
            for profile in profiles
            for note in profile.notes
        ),
    )
