"""DreamRAW-Tri v2 scaffold package."""

from .planner import (
    MODULE_STATUS as PLANNER_MODULE_STATUS,
    build_tri_raw_foundation_plan,
    materialize_tri_raw_foundation_plan,
)
from .runtime import (
    MODULE_STATUS as RUNTIME_MODULE_STATUS,
    TRI_RAW_BASELINE_RUNTIME_BACKEND,
    TRI_RAW_FRONTIER_CONTRACT_ID,
    TRI_RAW_RUNTIME_BACKEND,
    TriRawPreviewRuntimeResult,
    materialize_tri_raw_preview_runtime,
)

MODULE_STATUS = "phase0_scaffold"

__all__ = [
    "MODULE_STATUS",
    "PLANNER_MODULE_STATUS",
    "RUNTIME_MODULE_STATUS",
    "TRI_RAW_BASELINE_RUNTIME_BACKEND",
    "TRI_RAW_FRONTIER_CONTRACT_ID",
    "TRI_RAW_RUNTIME_BACKEND",
    "TriRawPreviewRuntimeResult",
    "build_tri_raw_foundation_plan",
    "materialize_tri_raw_foundation_plan",
    "materialize_tri_raw_preview_runtime",
]
