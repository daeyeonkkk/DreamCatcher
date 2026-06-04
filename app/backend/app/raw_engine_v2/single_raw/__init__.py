"""DreamRAW-One v2 package.

The executable engine path is still scaffolded, but Phase 1 now includes a real
planning layer plus runtime wiring that binds shared RAW core modules into the
direct RAW intake flow.
"""

from .planner import (
    MODULE_STATUS as PLANNER_MODULE_STATUS,
    build_single_raw_foundation_plan,
    materialize_single_raw_foundation_plan,
)
from .runtime import (
    MODULE_STATUS as RUNTIME_MODULE_STATUS,
    build_single_raw_runtime_health,
    materialize_single_raw_sensor_decode,
)

MODULE_STATUS = "phase0_scaffold"

__all__ = [
    "MODULE_STATUS",
    "PLANNER_MODULE_STATUS",
    "RUNTIME_MODULE_STATUS",
    "build_single_raw_foundation_plan",
    "materialize_single_raw_foundation_plan",
    "build_single_raw_runtime_health",
    "materialize_single_raw_sensor_decode",
]
