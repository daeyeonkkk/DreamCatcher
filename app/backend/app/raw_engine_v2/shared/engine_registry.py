from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .artifact_schema import PHASE0_ARTIFACT_SCHEMA


EngineFamily = Literal["single_raw", "tri_raw", "isp"]
EngineLifecycle = Literal["phase0_scaffold"]

PHASE0_ENGINE_REGISTRY_ID = "dreamcatcher.raw_engine_v2.registry"
PHASE0_ENGINE_REGISTRY_VERSION = "2026-04-06"
PHASE0_ENGINE_VERSION = "2.0.0-phase0"


class EngineDescriptor(BaseModel):
    key: str
    display_name: str
    family: EngineFamily
    version: str = PHASE0_ENGINE_VERSION
    lifecycle: EngineLifecycle = "phase0_scaffold"
    entry_package: str
    adapter_key: str
    artifact_schema_id: str
    artifact_schema_version: str
    supported_modes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EngineRegistry(BaseModel):
    registry_id: str = PHASE0_ENGINE_REGISTRY_ID
    registry_version: str = PHASE0_ENGINE_REGISTRY_VERSION
    engines: list[EngineDescriptor]

    def keys(self) -> list[str]:
        return [engine.key for engine in self.engines]

    def by_key(self, key: str) -> EngineDescriptor:
        for engine in self.engines:
            if engine.key == key:
                return engine
        raise KeyError(f"Unknown engine key: {key}")


def build_phase0_engine_registry() -> EngineRegistry:
    shared_schema_id = PHASE0_ARTIFACT_SCHEMA.schema_id
    shared_schema_version = PHASE0_ARTIFACT_SCHEMA.schema_version

    return EngineRegistry(
        engines=[
            EngineDescriptor(
                key="dreamraw_one_v2",
                display_name="DreamRAW-One v2",
                family="single_raw",
                entry_package="app.raw_engine_v2.single_raw",
                adapter_key="dreamraw_one_v2",
                artifact_schema_id=shared_schema_id,
                artifact_schema_version=shared_schema_version,
                supported_modes=["fast", "hq", "safe"],
                notes=[
                    "Phase 2 and Phase 4 will implement the fast/hq/safe execution paths behind this identifier.",
                ],
            ),
            EngineDescriptor(
                key="dreamraw_tri_v2",
                display_name="DreamRAW-Tri v2",
                family="tri_raw",
                entry_package="app.raw_engine_v2.tri_raw",
                adapter_key="dreamraw_tri_v2",
                artifact_schema_id=shared_schema_id,
                artifact_schema_version=shared_schema_version,
                supported_modes=["auto", "motion", "highlight", "shadow", "safe"],
                notes=[
                    "Phase 5 and Phase 6 will implement learned alignment, confidence, and fallback policies here.",
                ],
            ),
            EngineDescriptor(
                key="dreamisp_v2",
                display_name="DreamISP v2",
                family="isp",
                entry_package="app.raw_engine_v2.isp",
                adapter_key="dreamisp_v2",
                artifact_schema_id=shared_schema_id,
                artifact_schema_version=shared_schema_version,
                supported_modes=["preview", "edit"],
                notes=[
                    "Phase 3 starts with ISP-lite and keeps the same public identifier for the modular ISP expansion.",
                ],
            ),
        ]
    )


PHASE0_ENGINE_REGISTRY = build_phase0_engine_registry()


def get_engine_descriptor(engine_key: str) -> EngineDescriptor:
    return PHASE0_ENGINE_REGISTRY.by_key(engine_key)
