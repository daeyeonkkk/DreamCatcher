from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


MODULE_STATUS = "phase1_foundation"

NormalizedCfaPattern = Literal["rggb", "bggr", "grbg", "gbrg", "unknown"]


def _lookup(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        lowered_key = key.lower()
        if lowered_key in lowered:
            return lowered[lowered_key]
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
        if not items:
            return None
        if len(items) == 2:
            numerator = _coerce_float(items[0])
            denominator = _coerce_float(items[1])
            if numerator is not None and denominator not in {None, 0.0}:
                return numerator / denominator
        return _coerce_float(items[0])
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if "/" in normalized:
            left, right = normalized.split("/", 1)
            numerator = _coerce_float(left)
            denominator = _coerce_float(right)
            if numerator is None or denominator in {None, 0.0}:
                return None
            return numerator / denominator
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any, *, default: int) -> int:
    coerced = _coerce_float(value)
    if coerced is None:
        return default
    return max(default if default > 0 else 0, int(round(coerced)))


def _normalize_levels(value: Any, *, channel_count: int = 4, fallback: float) -> tuple[float, ...]:
    if value is None:
        return tuple(fallback for _ in range(channel_count))
    if isinstance(value, str) and "," in value:
        items = [item.strip() for item in value.split(",") if item.strip()]
        return _normalize_levels(items, channel_count=channel_count, fallback=fallback)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [_coerce_float(item) for item in value]
        levels = [item for item in items if item is not None]
        if not levels:
            return tuple(fallback for _ in range(channel_count))
        while len(levels) < channel_count:
            levels.append(levels[-1])
        return tuple(float(levels[index]) for index in range(channel_count))
    scalar = _coerce_float(value)
    if scalar is None:
        return tuple(fallback for _ in range(channel_count))
    return tuple(float(scalar) for _ in range(channel_count))


def normalize_black_level(value: Any) -> tuple[float, float, float, float]:
    normalized = _normalize_levels(value, channel_count=4, fallback=0.0)
    return (
        float(normalized[0]),
        float(normalized[1]),
        float(normalized[2]),
        float(normalized[3]),
    )


def normalize_white_level(value: Any, *, fallback: float = 16383.0) -> float:
    normalized = _normalize_levels(value, channel_count=1, fallback=fallback)
    return max(float(normalized[0]), 1.0)


def normalize_cfa_pattern(value: Any) -> NormalizedCfaPattern:
    if value is None:
        return "unknown"
    if isinstance(value, str):
        letters = "".join(character.lower() for character in value if character.lower() in {"r", "g", "b"})
        if len(letters) >= 4:
            token = letters[:4]
            if token in {"rggb", "bggr", "grbg", "gbrg"}:
                return token  # type: ignore[return-value]
        return "unknown"
    if isinstance(value, Sequence):
        mapping = {0: "r", 1: "g", 2: "b", 3: "g"}
        letters = "".join(mapping.get(int(item), "x") for item in list(value)[:4] if _coerce_float(item) is not None)
        if letters in {"rggb", "bggr", "grbg", "gbrg"}:
            return letters  # type: ignore[return-value]
    return "unknown"


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _slug_key(*parts: str | None) -> str:
    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        token = re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_")
        if token:
            tokens.append(token)
    return "_".join(tokens) if tokens else "unknown"


def infer_bit_depth(value: Any, *, white_level: float) -> int:
    explicit = _coerce_float(value)
    if explicit is not None and explicit > 0:
        return int(explicit)
    derived = math.ceil(math.log2(max(white_level + 1.0, 2.0)))
    return max(8, int(derived))


@dataclass(frozen=True)
class NormalizedRawMetadata:
    source_path: str | None
    make: str | None
    camera_model: str | None
    camera_key: str
    lens_model: str | None
    lens_key: str
    iso: int
    exposure_seconds: float
    aperture_f_number: float | None
    focal_length_mm: float | None
    exposure_bias_ev: float
    orientation: int
    bit_depth: int
    cfa_pattern: NormalizedCfaPattern
    black_level: tuple[float, float, float, float]
    white_level: float
    notes: tuple[str, ...] = ()

    def reference_black_level(self) -> float:
        return sum(self.black_level) / len(self.black_level)

    def dynamic_range_code_values(self) -> float:
        return max(self.white_level - self.reference_black_level(), 1.0)


@dataclass(frozen=True)
class BracketMetadataSummary:
    frame_count: int
    shared_camera_key: str
    shared_lens_key: str
    iso_values: tuple[int, ...]
    exposure_seconds: tuple[float, ...]
    reference_frame_index: int
    exposure_order: Literal["single", "ascending", "descending", "unordered"]
    mixed_sensor_calibration: bool
    notes: tuple[str, ...] = ()


def normalize_raw_metadata(payload: Mapping[str, Any], *, source_path: str | None = None) -> NormalizedRawMetadata:
    make = _normalize_text(_lookup(payload, "Make", "CameraMake"))
    model = _normalize_text(_lookup(payload, "Model", "CameraModel"))
    lens_model = _normalize_text(_lookup(payload, "LensModel", "Lens", "LensID"))
    iso = _coerce_int(_lookup(payload, "ISO", "ISOSpeedRatings"), default=100)
    exposure_seconds = _coerce_float(_lookup(payload, "ExposureTime", "ShutterSpeed")) or 0.01
    aperture_f_number = _coerce_float(_lookup(payload, "FNumber", "Aperture"))
    focal_length_mm = _coerce_float(_lookup(payload, "FocalLength"))
    exposure_bias_ev = _coerce_float(_lookup(payload, "ExposureBiasValue", "ExposureCompensation")) or 0.0
    orientation = _coerce_int(_lookup(payload, "Orientation"), default=1)
    black_level = normalize_black_level(_lookup(payload, "BlackLevel", "BlackLevels"))
    white_level = normalize_white_level(_lookup(payload, "WhiteLevel", "WhiteLevels"))
    cfa_pattern = normalize_cfa_pattern(_lookup(payload, "CFAPattern", "CFARepeatPatternDim", "BayerPattern"))
    bit_depth = infer_bit_depth(_lookup(payload, "BitsPerSample", "BitDepth"), white_level=white_level)

    notes: list[str] = []
    if cfa_pattern == "unknown":
        notes.append("CFA pattern is not available; later decode stages must infer or override it.")
    if lens_model is None:
        notes.append("Lens model is missing; deterministic correction must fall back to an identity profile.")

    return NormalizedRawMetadata(
        source_path=source_path,
        make=make,
        camera_model=model,
        camera_key=_slug_key(make, model),
        lens_model=lens_model,
        lens_key=_slug_key(lens_model),
        iso=max(iso, 100),
        exposure_seconds=max(exposure_seconds, 1e-6),
        aperture_f_number=aperture_f_number,
        focal_length_mm=focal_length_mm,
        exposure_bias_ev=exposure_bias_ev,
        orientation=max(orientation, 1),
        bit_depth=bit_depth,
        cfa_pattern=cfa_pattern,
        black_level=black_level,
        white_level=max(white_level, max(black_level) + 1.0),
        notes=tuple(notes),
    )


def summarize_bracket_metadata(records: Sequence[NormalizedRawMetadata]) -> BracketMetadataSummary:
    if not records:
        raise ValueError("Bracket metadata summary requires at least one normalized RAW metadata record")

    iso_values = tuple(record.iso for record in records)
    exposure_seconds = tuple(record.exposure_seconds for record in records)
    if len(records) == 1:
        order: Literal["single", "ascending", "descending", "unordered"] = "single"
        reference_frame_index = 0
    elif list(exposure_seconds) == sorted(exposure_seconds):
        order = "ascending"
        median_exposure = sorted(exposure_seconds)[len(exposure_seconds) // 2]
        reference_frame_index = min(
            range(len(records)),
            key=lambda index: (abs(exposure_seconds[index] - median_exposure), abs(index - len(records) // 2)),
        )
    elif list(exposure_seconds) == sorted(exposure_seconds, reverse=True):
        order = "descending"
        median_exposure = sorted(exposure_seconds)[len(exposure_seconds) // 2]
        reference_frame_index = min(
            range(len(records)),
            key=lambda index: (abs(exposure_seconds[index] - median_exposure), abs(index - len(records) // 2)),
        )
    else:
        order = "unordered"
        reference_frame_index = len(records) // 2

    camera_keys = {record.camera_key for record in records}
    lens_keys = {record.lens_key for record in records}
    white_levels = {record.white_level for record in records}
    black_levels = {record.black_level for record in records}
    notes: list[str] = []
    if len(camera_keys) > 1:
        notes.append("Mixed camera bodies detected inside the same RAW bundle.")
    if len(lens_keys) > 1:
        notes.append("Mixed lens identities detected inside the same RAW bundle.")

    return BracketMetadataSummary(
        frame_count=len(records),
        shared_camera_key=records[0].camera_key if len(camera_keys) == 1 else "mixed",
        shared_lens_key=records[0].lens_key if len(lens_keys) == 1 else "mixed",
        iso_values=iso_values,
        exposure_seconds=exposure_seconds,
        reference_frame_index=reference_frame_index,
        exposure_order=order,
        mixed_sensor_calibration=len(white_levels) > 1 or len(black_levels) > 1,
        notes=tuple(notes),
    )
