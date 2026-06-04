from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


RawRestorationTone = Literal["default", "accent", "success", "warning"]
DEFAULT_RAW_RESTORATION_GOAL = "truth_preserving"

_FALLBACK_LABELS = {
    "truth_preserving": "진실 보존",
    "aggressive_restore": "공격적 복원 후보",
}


class RawRestorationGoalPolicy(BaseModel):
    id: str
    label: str
    summary: str
    approval: str | None = None
    risk: str | None = None
    delivery_default: bool = False
    requires_human_review: bool = False
    tone: RawRestorationTone = "default"
    review_gates: list[str] = Field(default_factory=list)


class RawRestorationPolicy(BaseModel):
    schema_version: str = "raw_restoration_policy_v1"
    contract_id: str = "tri_raw_frontier_v1"
    baseline_backend: str = "tri_raw_baseline_v1"
    studio_official_inputs: list[str] = Field(default_factory=list)
    accepted_frame_counts: list[int] = Field(default_factory=list)
    nine_frame_status: str | None = None
    default_goal: str = DEFAULT_RAW_RESTORATION_GOAL
    options: list[RawRestorationGoalPolicy]
    source_manifest: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _manifest_path() -> Path:
    return _repo_root() / "app" / "models" / "model_manifest.yaml"


def _fallback_options() -> list[dict[str, Any]]:
    return [
        {
            "id": "truth_preserving",
            "summary": "실제 프레임 근거를 우선해 고스팅과 과한 질감 생성을 낮춥니다.",
            "approval": "default_delivery_path",
        },
        {
            "id": "aggressive_restore",
            "summary": "고스트와 노이즈 근거를 보며 더 강한 디테일 후보를 만듭니다. 최종 채택 전 검수가 필요합니다.",
            "approval": "qwen_metric_golden_human_review_required",
            "risk": "hallucinated_detail_or_over_sharpened_texture",
        },
    ]


def _load_raw_frontier(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {}
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    raw_frontier = payload.get("raw_frontier")
    return raw_frontier if isinstance(raw_frontier, dict) else {}


def _option_tone(option_id: str, requires_human_review: bool) -> RawRestorationTone:
    if requires_human_review:
        return "warning"
    if option_id == DEFAULT_RAW_RESTORATION_GOAL:
        return "success"
    return "default"


def _review_gates(option: dict[str, Any]) -> list[str]:
    approval = str(option.get("approval") or "")
    if "review" not in approval and not option.get("risk"):
        return []
    return [
        "qwen_judge_signal_v2",
        "metric_checker_layer",
        "golden_session_runner",
        "human_approval",
    ]


def _coerce_option(option: dict[str, Any], default_goal: str) -> RawRestorationGoalPolicy:
    option_id = str(option.get("id") or "").strip() or default_goal
    approval = str(option.get("approval") or "").strip() or None
    risk = str(option.get("risk") or "").strip() or None
    requires_human_review = bool(risk or (approval and "review" in approval))
    return RawRestorationGoalPolicy(
        id=option_id,
        label=str(option.get("label") or _FALLBACK_LABELS.get(option_id, option_id.replace("_", " "))),
        summary=str(option.get("summary") or "").strip(),
        approval=approval,
        risk=risk,
        delivery_default=option_id == default_goal or approval == "default_delivery_path",
        requires_human_review=requires_human_review,
        tone=_option_tone(option_id, requires_human_review),
        review_gates=_review_gates(option),
    )


@lru_cache(maxsize=4)
def build_raw_restoration_policy(manifest_path: str | None = None) -> RawRestorationPolicy:
    resolved_manifest = Path(manifest_path) if manifest_path else _manifest_path()
    raw_frontier = _load_raw_frontier(resolved_manifest)
    goals = raw_frontier.get("restoration_goals") if isinstance(raw_frontier.get("restoration_goals"), dict) else {}
    default_goal = str(goals.get("default") or DEFAULT_RAW_RESTORATION_GOAL)
    options_payload = goals.get("options") if isinstance(goals.get("options"), list) else _fallback_options()
    options = [
        _coerce_option(option, default_goal)
        for option in options_payload
        if isinstance(option, dict)
    ]
    if not options:
        options = [_coerce_option(option, default_goal) for option in _fallback_options()]
    if default_goal not in {option.id for option in options}:
        default_goal = options[0].id

    return RawRestorationPolicy(
        contract_id=str(raw_frontier.get("contract_id") or "tri_raw_frontier_v1"),
        baseline_backend=str(raw_frontier.get("baseline_backend") or "tri_raw_baseline_v1"),
        studio_official_inputs=[str(item) for item in raw_frontier.get("studio_official_inputs") or []],
        accepted_frame_counts=[int(item) for item in raw_frontier.get("accepted_frame_counts") or []],
        nine_frame_status=str(raw_frontier.get("nine_frame_status") or "") or None,
        default_goal=default_goal,
        options=options,
        source_manifest=str(resolved_manifest),
    )


def raw_restoration_goal_ids() -> list[str]:
    return [option.id for option in build_raw_restoration_policy().options]


def normalize_raw_restoration_goal(value: str | None) -> str:
    goals = raw_restoration_goal_ids()
    candidate = (value or "").strip()
    if candidate in goals:
        return candidate
    return build_raw_restoration_policy().default_goal


def raw_restoration_goal_policy(value: str | None) -> RawRestorationGoalPolicy:
    normalized = normalize_raw_restoration_goal(value)
    for option in build_raw_restoration_policy().options:
        if option.id == normalized:
            return option
    return build_raw_restoration_policy().options[0]
