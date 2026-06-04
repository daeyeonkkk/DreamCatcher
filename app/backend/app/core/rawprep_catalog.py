from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.raw_engine_v2.shared.engine_registry import PHASE0_ENGINE_REGISTRY


RawPrepQualityPreset = Literal["safe", "balanced"]
RAW_ENGINE_V2_BINARY = "dreamcatcher-raw-engine-v2"


class RawPrepEngineSpec(BaseModel):
    engine_stack: str
    label: str
    family: str
    version: str
    lifecycle: str
    enabled: bool = False
    required_tools: list[str] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    artifact_schema_id: str | None = None
    artifact_schema_version: str | None = None
    notes: list[str] = Field(default_factory=list)


def legacy_removed_note() -> str:
    return "Legacy RAW/TriRaw v1 경로는 제거됐습니다. DreamCatcher는 실행형 엔진이 올라오기 전까지 v2 계약 스캐폴드에 고정됩니다."


def preview_runtime_note() -> str:
    return "TriRaw는 이제 v2 미리보기 런타임으로 브라켓 분석, 미리보기 병합, DreamISP handoff를 먼저 실행할 수 있습니다."


def raw_engine_binary_name() -> str:
    return RAW_ENGINE_V2_BINARY


def required_tools_for_engine(engine_stack: str) -> list[str]:
    normalized = engine_stack.strip()
    for spec in list_engine_specs():
        if spec.engine_stack == normalized:
            return list(spec.required_tools)
    raise ValueError(f"unknown engine stack: {engine_stack}")


def list_engine_specs() -> list[RawPrepEngineSpec]:
    specs: list[RawPrepEngineSpec] = []
    for descriptor in PHASE0_ENGINE_REGISTRY.engines:
        specs.append(
            RawPrepEngineSpec(
                engine_stack=descriptor.key,
                label=descriptor.display_name,
                family=descriptor.family,
                version=descriptor.version,
                lifecycle=descriptor.lifecycle,
                enabled=True,
                required_tools=[],
                supported_modes=list(descriptor.supported_modes),
                artifact_schema_id=descriptor.artifact_schema_id,
                artifact_schema_version=descriptor.artifact_schema_version,
                notes=[preview_runtime_note(), legacy_removed_note(), *descriptor.notes],
            )
        )
    return specs


def rawprep_catalog_payload() -> dict[str, object]:
    return {
        "enabled": True,
        "status": "phase1_preview_runtime",
        "message": preview_runtime_note(),
        "engine_stacks": [spec.model_dump() for spec in list_engine_specs()],
        "camera_profiles": [],
        "lens_profiles": [],
    }
