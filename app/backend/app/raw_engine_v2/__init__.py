"""DreamCatcher v2 RAW engine scaffold.

Phase 0 locks package names and shared contracts before the engine internals land.
"""

from .shared.artifact_schema import PHASE0_ARTIFACT_SCHEMA
from .shared.engine_registry import PHASE0_ENGINE_REGISTRY

__all__ = ["PHASE0_ARTIFACT_SCHEMA", "PHASE0_ENGINE_REGISTRY"]
