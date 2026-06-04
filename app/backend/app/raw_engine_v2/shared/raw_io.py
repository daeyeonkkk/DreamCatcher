from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


MODULE_STATUS = "phase1_foundation"

RawBundleKind = Literal["single_raw", "raw_bracket"]
RawFrameRole = Literal["single", "low", "middle", "high"]

SUPPORTED_RAW_SUFFIXES = frozenset(
    {
        ".arw",
        ".cr2",
        ".cr3",
        ".dng",
        ".erf",
        ".nef",
        ".orf",
        ".pef",
        ".raf",
        ".raw",
        ".rw2",
        ".srw",
    }
)


@dataclass(frozen=True)
class RawFrameInput:
    path: str
    file_name: str
    suffix: str
    frame_index: int
    frame_role: RawFrameRole
    bracket_id: str | None = None

    @property
    def is_bracketed(self) -> bool:
        return self.frame_role != "single"


@dataclass(frozen=True)
class RawDecodePlan:
    input_path: str
    decoder_key: str
    suffix: str
    preserve_cfa: bool = True
    normalize_black_level: bool = True
    normalize_white_level: bool = True


@dataclass(frozen=True)
class RawInputBundle:
    kind: RawBundleKind
    frames: tuple[RawFrameInput, ...]
    bracket_id: str | None = None

    def frame_paths(self) -> list[str]:
        return [frame.path for frame in self.frames]

    def reference_frame(self) -> RawFrameInput:
        if self.kind == "single_raw":
            return self.frames[0]
        for frame in self.frames:
            if frame.frame_role == "middle":
                return frame
        return self.frames[len(self.frames) // 2]

    def build_decode_plans(self) -> list[RawDecodePlan]:
        return [build_decode_plan(frame) for frame in self.frames]


def normalize_raw_path(path: str) -> str:
    normalized = str(path).strip()
    if not normalized:
        raise ValueError("RAW path must not be empty")
    return normalized


def raw_suffix(path: str) -> str:
    return Path(path).suffix.lower()


def validate_raw_suffix(path: str) -> str:
    suffix = raw_suffix(path)
    if suffix not in SUPPORTED_RAW_SUFFIXES:
        raise ValueError(f"Unsupported RAW suffix: {suffix or '<none>'}")
    return suffix


def infer_frame_role(total_frames: int, frame_index: int) -> RawFrameRole:
    if total_frames == 1:
        return "single"
    if total_frames == 3:
        roles: tuple[RawFrameRole, RawFrameRole, RawFrameRole] = ("low", "middle", "high")
        return roles[frame_index]
    if total_frames == 9:
        if frame_index <= 2:
            return "low"
        if frame_index <= 5:
            return "middle"
        return "high"
    raise ValueError("DreamCatcher v2 shared RAW core supports exactly 1, 3, or 9 RAW frames")


def build_raw_frame_input(
    path: str,
    *,
    frame_index: int,
    total_frames: int,
    bracket_id: str | None = None,
) -> RawFrameInput:
    normalized_path = normalize_raw_path(path)
    suffix = validate_raw_suffix(normalized_path)
    file_name = Path(normalized_path).name
    return RawFrameInput(
        path=normalized_path,
        file_name=file_name,
        suffix=suffix,
        frame_index=frame_index,
        frame_role=infer_frame_role(total_frames, frame_index),
        bracket_id=bracket_id,
    )


def build_decode_plan(frame: RawFrameInput) -> RawDecodePlan:
    return RawDecodePlan(
        input_path=frame.path,
        decoder_key=f"raw_decode{frame.suffix}",
        suffix=frame.suffix,
    )


def build_raw_input_bundle(paths: list[str], *, bracket_id: str | None = None) -> RawInputBundle:
    normalized_paths = [normalize_raw_path(path) for path in paths]
    if len(normalized_paths) not in {1, 3, 9}:
        raise ValueError("Shared RAW input bundle must contain exactly 1, 3, or 9 RAW paths")
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ValueError("Shared RAW input bundle must not contain duplicate RAW paths")

    kind: RawBundleKind = "single_raw" if len(normalized_paths) == 1 else "raw_bracket"
    effective_bracket_id = bracket_id.strip() if bracket_id and bracket_id.strip() else None
    if kind == "raw_bracket" and effective_bracket_id is None:
        effective_bracket_id = "bracket_01"

    frames = tuple(
        build_raw_frame_input(
            path,
            frame_index=index,
            total_frames=len(normalized_paths),
            bracket_id=effective_bracket_id,
        )
        for index, path in enumerate(normalized_paths)
    )
    return RawInputBundle(
        kind=kind,
        frames=frames,
        bracket_id=effective_bracket_id,
    )
