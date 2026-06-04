from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..core.runpod_model_bootstrap_contract import (
    build_runpod_bootstrap_session_policy,
    build_runpod_model_profiles_payload,
    build_runpod_template_policy,
)


router = APIRouter(prefix="/api/runpod", tags=["runpod"])


@router.get("/model-profiles")
def model_profiles() -> dict[str, Any]:
    return build_runpod_model_profiles_payload()


@router.get("/template-policy")
def template_policy() -> dict[str, Any]:
    return build_runpod_template_policy().model_dump()


@router.get("/bootstrap-session")
def bootstrap_session() -> dict[str, Any]:
    return build_runpod_bootstrap_session_policy().model_dump()
