from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .recipe_router import normalize_tool_key
from .studio_compare_advisor import rounded_compare_metrics, sample_image_metrics
from .studio_files import resolve_output_target
from .studio_paths import resolve_output_root


QualityVerdict = Literal["fail", "suspicious", "pass"]
QWEN_AUTOMATION_MODEL = "Qwen3.6-35B-A3B-FP8"
QUALITY_AUTOMATION_VERSION = "quality_automation_v2"
QUALITY_TUNING_VERSION = "quality_tuning_loop_v1"
QWEN_JUDGE_SIGNAL_SCHEMA_VERSION = "qwen_judge_signal_v2"
JUDGE_EVIDENCE_PACKET_SCHEMA_VERSION = "judge_evidence_packet_v1"
GOLDEN_CALIBRATION_VERSION = "golden_calibration_v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QualityAutomationPolicy(BaseModel):
    version: str = QUALITY_AUTOMATION_VERSION
    tuning_version: str = QUALITY_TUNING_VERSION
    qwen_judge_schema_version: str = QWEN_JUDGE_SIGNAL_SCHEMA_VERSION
    judge_evidence_packet_schema_version: str = JUDGE_EVIDENCE_PACKET_SCHEMA_VERSION
    golden_calibration_version: str = GOLDEN_CALIBRATION_VERSION
    primary_local_model: str = QWEN_AUTOMATION_MODEL
    primary_local_repo: str = "Qwen/Qwen3.6-35B-A3B-FP8"
    local_judge_endpoint_env: str = "DC_QWEN_JUDGE_BASE_URL"
    local_judge_model_path_env: str = "DC_QWEN_JUDGE_MODEL_PATH"
    cloud_fallback_enabled: bool = False
    verdicts: list[QualityVerdict] = Field(default_factory=lambda: ["fail", "suspicious", "pass"])
    runtime_layers: list[str] = Field(
        default_factory=lambda: [
            "qwen_vlm_judge",
            "metric_checker_layer",
            "golden_session_runner",
            "human_approval_memory",
        ]
    )
    metric_checkers: list[str] = Field(
        default_factory=lambda: [
            "image_luma_contrast_clip_detail",
            "color_shift_delta",
            "judge_evidence_packet",
            "mask_checker_contract",
            "raw_ghost_confidence_alignment_contract",
            "golden_quality_calibration",
            "lpips_or_dreamsim_slot",
            "musiq_or_nr_iqa_slot",
        ]
    )
    automation_allowed: list[str] = Field(
        default_factory=lambda: [
            "quality_inspection",
            "failure_tagging",
            "axis_scoring",
            "localized_issue_detection",
            "correction_plan_draft",
            "retry_instruction",
            "evidence_packet_enrichment",
            "candidate_comparison",
            "golden_session_replay",
            "golden_score_calibration",
            "tuning_proposal_draft",
        ]
    )
    human_approval_required_for: list[str] = Field(
        default_factory=lambda: [
            "suspicious_verdict",
            "preset_change",
            "workflow_change",
            "prompt_or_rubric_change",
            "metric_threshold_change",
            "code_change",
            "release_promotion",
        ]
    )
    automation_blocked: list[str] = Field(
        default_factory=lambda: [
            "auto_apply_code_change",
            "auto_replace_workflow",
            "auto_change_metric_threshold",
            "auto_release_after_tuning",
        ]
    )
    qwen_response_required_keys: list[str] = Field(
        default_factory=lambda: [
            "schema_version",
            "verdict",
            "confidence",
            "axis_scores",
            "failure_tags",
            "localized_issues",
            "correction_plan",
            "rationale",
            "retry_instruction",
            "work_instruction",
        ]
    )


class QwenAxisScores(BaseModel):
    intent_match: float | None = None
    technical_quality: float | None = None
    aesthetic_quality: float | None = None
    subject_preservation: float | None = None
    mask_boundary: float | None = None
    color_naturalness: float | None = None


class QwenLocalizedIssue(BaseModel):
    area: str
    issue_type: str
    severity: Literal["info", "warning", "critical"] = "warning"
    description: str
    confidence: float | None = None
    bbox_norm: list[float] | None = None
    suggested_action: str | None = None


class QwenCorrectionPlan(BaseModel):
    exposure_delta: float | None = None
    contrast_delta: float | None = None
    shadow_delta: float | None = None
    highlight_delta: float | None = None
    temperature_delta: float | None = None
    tint_delta: float | None = None
    saturation_delta: float | None = None
    denoise_strength: float | None = None
    edit_strength: float | None = None
    crop_box_norm: list[float] | None = None
    notes: str | None = None


class QwenJudgeSignal(BaseModel):
    schema_version: str = QWEN_JUDGE_SIGNAL_SCHEMA_VERSION
    verdict: QualityVerdict = "suspicious"
    confidence: float = 0.0
    axis_scores: QwenAxisScores = Field(default_factory=QwenAxisScores)
    rationale: str | None = None
    failure_tags: list[str] = Field(default_factory=list)
    localized_issues: list[QwenLocalizedIssue] = Field(default_factory=list)
    correction_plan: QwenCorrectionPlan = Field(default_factory=QwenCorrectionPlan)
    retry_instruction: str | None = None
    work_instruction: str | None = None


class JudgeEvidencePacket(BaseModel):
    schema_version: str = JUDGE_EVIDENCE_PACKET_SCHEMA_VERSION
    tool: str
    task_intent: str
    result_path: str
    reference_path: str | None = None
    result_metrics: dict[str, float]
    reference_metrics: dict[str, float] | None = None
    metric_delta: dict[str, float] = Field(default_factory=dict)
    metric_units: dict[str, str] = Field(default_factory=dict)
    operation_context: dict[str, Any] = Field(default_factory=dict)
    mask_evidence: dict[str, Any] = Field(default_factory=dict)
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    workflow_evidence: dict[str, Any] = Field(default_factory=dict)
    user_preference_evidence: dict[str, Any] = Field(default_factory=dict)
    golden_context: dict[str, Any] = Field(default_factory=dict)
    available_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)


class MetricSignal(BaseModel):
    tag: str
    severity: Literal["info", "warning", "critical"] = "warning"
    detail: str
    value: float | None = None
    threshold: float | None = None


class GoldenCalibrationResult(BaseModel):
    schema_version: str = GOLDEN_CALIBRATION_VERSION
    applied: bool = False
    calibration_source: str | None = None
    profile_id: str = "frontier_default"
    sample_count: int = 0
    calibrated_verdict: QualityVerdict | None = None
    calibrated_confidence: float | None = None
    calibrated_axis_scores: QwenAxisScores = Field(default_factory=QwenAxisScores)
    added_failure_tags: list[str] = Field(default_factory=list)
    adjustments: list[str] = Field(default_factory=list)
    replay_required: bool = True
    replay_case_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class QualityRetryPlan(BaseModel):
    retry_allowed: bool
    human_approval_before_accept: bool
    max_attempts: int = 1
    instructions: list[str] = Field(default_factory=list)


class QualityAssessmentRecord(BaseModel):
    assessment_id: str
    created_at: str
    session_id: str | None = None
    output_root: str
    tool: str
    result_path: str
    reference_path: str | None = None
    version: str = QUALITY_AUTOMATION_VERSION
    primary_local_model: str = QWEN_AUTOMATION_MODEL
    cloud_fallback_enabled: bool = False
    verdict: QualityVerdict
    human_approval_required: bool
    human_review_reason: list[str] = Field(default_factory=list)
    qwen_judge_signal: QwenJudgeSignal | None = None
    qwen_judge_schema_version: str = QWEN_JUDGE_SIGNAL_SCHEMA_VERSION
    judge_evidence_packet: JudgeEvidencePacket | None = None
    golden_calibration: GoldenCalibrationResult | None = None
    result_metrics: dict[str, float]
    reference_metrics: dict[str, float] | None = None
    metric_delta: dict[str, float] = Field(default_factory=dict)
    metric_signals: list[MetricSignal] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)
    work_instructions: list[str] = Field(default_factory=list)
    retry_plan: QualityRetryPlan
    tuning_targets: list[str] = Field(default_factory=list)
    golden_runner_required: bool = True
    code_tuning_gate: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str | None = None


class QualityTuningProposal(BaseModel):
    proposal_id: str
    created_at: str
    version: str = QUALITY_TUNING_VERSION
    output_root: str
    session_id: str | None = None
    source_assessment_count: int
    status: Literal["waiting_for_quality_evidence", "human_approval_required"] = "human_approval_required"
    automatic_code_tuning_enabled: bool = False
    human_approval_required: bool = True
    failure_clusters: dict[str, int] = Field(default_factory=dict)
    suggested_changes: list[dict[str, Any]] = Field(default_factory=list)
    golden_runner_plan: dict[str, Any] = Field(default_factory=dict)
    blocked_actions: list[str] = Field(default_factory=list)
    allowed_next_actions: list[str] = Field(default_factory=list)
    artifact_path: str | None = None


def build_quality_automation_policy() -> QualityAutomationPolicy:
    return QualityAutomationPolicy()


def _assessment_id() -> str:
    return "qa_" + utc_now_iso().replace(":", "").replace("-", "").replace(".", "")


def _proposal_id() -> str:
    return "qt_" + utc_now_iso().replace(":", "").replace("-", "").replace(".", "")


def _metric_delta(result_metrics: dict[str, float], reference_metrics: dict[str, float] | None) -> dict[str, float]:
    if not reference_metrics:
        return {}
    return {
        key: round(float(result_metrics[key]) - float(reference_metrics[key]), 6)
        for key in result_metrics
        if key in reference_metrics
    }


def _metric_units() -> dict[str, str]:
    return {
        "mean_luma": "0..1",
        "contrast": "0..1 relative tonal contrast",
        "highlight_clip_ratio": "0..1 lower is better",
        "shadow_clip_ratio": "0..1 lower is better",
        "warmth": "relative red-blue balance",
        "saturation": "0..1 relative saturation",
        "detail_energy": "relative edge/detail energy",
    }


def _coerce_evidence_dict(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {str(key): item for key, item in value.items() if item is not None}


def _seed_root_path(seed_root: str | Path) -> Path:
    root = Path(seed_root)
    if root.is_absolute():
        return root
    candidates = [Path.cwd() / root]
    candidates.extend(parent / root for parent in Path.cwd().parents)
    candidates.extend(parent / root for parent in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path.cwd() / root


def _golden_calibration_seed_path(seed_root: str | Path) -> Path:
    return _seed_root_path(seed_root) / "runtime_priors" / "evaluator" / "golden_quality_calibration.seed.json"


def _load_golden_calibration_seed(seed_root: str | Path = "seed_bundle") -> tuple[dict[str, Any], Path | None]:
    path = _golden_calibration_seed_path(seed_root)
    if not path.exists():
        return {}, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path
    return payload if isinstance(payload, dict) else {}, path


def _profile_matches_tool(profile: dict[str, Any], tool: str) -> bool:
    tools = profile.get("tools")
    return isinstance(tools, list) and tool in {str(item) for item in tools}


def _select_golden_profile(seed: dict[str, Any], tool: str) -> dict[str, Any]:
    profiles = seed.get("profiles")
    if not isinstance(profiles, list):
        return {}
    for item in profiles:
        if isinstance(item, dict) and _profile_matches_tool(item, tool):
            return item
    default_id = str(seed.get("default_profile") or "frontier_default")
    for item in profiles:
        if isinstance(item, dict) and str(item.get("profile_id") or "") == default_id:
            return item
    return profiles[0] if profiles and isinstance(profiles[0], dict) else {}


def build_golden_context_for_tool(*, tool: str, seed_root: str | Path = "seed_bundle") -> dict[str, Any]:
    normalized_tool = normalize_tool_key(tool)
    seed, path = _load_golden_calibration_seed(seed_root)
    profile = _select_golden_profile(seed, normalized_tool)
    if not profile:
        return {
            "schema_version": "golden_quality_context_v1",
            "profile_id": "missing",
            "available": False,
            "note": "Golden calibration seed is not available.",
        }
    return {
        "schema_version": "golden_quality_context_v1",
        "available": True,
        "source_path": str(path) if path else None,
        "profile_id": str(profile.get("profile_id") or "frontier_default"),
        "sample_count": int(profile.get("sample_count") or 0),
        "axis_suspicious_below": profile.get("axis_suspicious_below") or {},
        "axis_fail_below": profile.get("axis_fail_below") or {},
        "required_evidence": profile.get("required_evidence") or [],
        "style_rubric": profile.get("style_rubric") or [],
        "replay_case_ids": profile.get("replay_case_ids") or [],
    }


def build_judge_evidence_packet(
    *,
    result_path: str,
    output_root: str = "outputs",
    reference_path: str | None = None,
    tool: str = "compare",
    task_intent: str | None = None,
    seed_root: str | Path = "seed_bundle",
    operation_context: dict[str, Any] | None = None,
    mask_evidence: dict[str, Any] | None = None,
    raw_evidence: dict[str, Any] | None = None,
    workflow_evidence: dict[str, Any] | None = None,
    user_preference_evidence: dict[str, Any] | None = None,
    golden_context: dict[str, Any] | None = None,
) -> JudgeEvidencePacket:
    result_target = resolve_output_target(result_path, output_root=output_root)
    reference_target = resolve_output_target(reference_path, output_root=output_root) if reference_path else None
    normalized_tool = normalize_tool_key(tool)
    result_metrics = rounded_compare_metrics(sample_image_metrics(result_target))
    reference_metrics = rounded_compare_metrics(sample_image_metrics(reference_target)) if reference_target else None
    delta = _metric_delta(result_metrics, reference_metrics)
    operation_payload = _coerce_evidence_dict(operation_context)
    mask_payload = _coerce_evidence_dict(mask_evidence)
    raw_payload = _coerce_evidence_dict(raw_evidence)
    workflow_payload = _coerce_evidence_dict(workflow_evidence)
    preference_payload = _coerce_evidence_dict(user_preference_evidence)
    golden_payload = _coerce_evidence_dict(golden_context) or build_golden_context_for_tool(
        tool=normalized_tool,
        seed_root=seed_root,
    )

    available = ["deterministic_metrics"]
    optional_blocks = {
        "reference_image": bool(reference_target),
        "operation_context": bool(operation_payload),
        "mask_evidence": bool(mask_payload),
        "raw_evidence": bool(raw_payload),
        "workflow_evidence": bool(workflow_payload),
        "user_preference_evidence": bool(preference_payload),
        "golden_context": bool(golden_payload and golden_payload.get("available") is not False),
    }
    available.extend(name for name, present in optional_blocks.items() if present)
    missing = [name for name, present in optional_blocks.items() if not present]
    cautions: list[str] = []
    if not reference_target:
        cautions.append("No reference image was supplied; preserve/delta judgments must rely on result-only evidence.")
    if not mask_payload and normalized_tool in {"removeBg", "replaceBg", "replaceObject", "expandCanvas"}:
        cautions.append("Mask evidence is missing for a mask-sensitive tool.")
    if not raw_payload and normalized_tool in {"enhance", "compare"}:
        cautions.append("RAW/alignment evidence is only available when the session produced RAW diagnostics.")
    if not preference_payload:
        cautions.append("No user preference memory was supplied; aesthetic judgment should stay conservative.")

    return JudgeEvidencePacket(
        tool=normalized_tool,
        task_intent=task_intent or "Judge whether the result is acceptable for professional photo editing.",
        result_path=str(result_target),
        reference_path=str(reference_target) if reference_target else None,
        result_metrics=result_metrics,
        reference_metrics=reference_metrics,
        metric_delta=delta,
        metric_units=_metric_units(),
        operation_context=operation_payload,
        mask_evidence=mask_payload,
        raw_evidence=raw_payload,
        workflow_evidence=workflow_payload,
        user_preference_evidence=preference_payload,
        golden_context=golden_payload,
        available_evidence=available,
        missing_evidence=missing,
        cautions=cautions,
    )


def _metric_signals(
    result_metrics: dict[str, float],
    reference_metrics: dict[str, float] | None,
    delta: dict[str, float],
) -> list[MetricSignal]:
    signals: list[MetricSignal] = []
    highlight = result_metrics.get("highlight_clip_ratio", 0.0)
    shadow = result_metrics.get("shadow_clip_ratio", 0.0)
    detail = result_metrics.get("detail_energy", 0.0)

    if highlight >= 0.04:
        signals.append(
            MetricSignal(
                tag="highlight_clip",
                severity="critical" if highlight >= 0.08 else "warning",
                detail="Result has elevated highlight clipping.",
                value=round(highlight, 6),
                threshold=0.04,
            )
        )
    if shadow >= 0.10:
        signals.append(
            MetricSignal(
                tag="shadow_crush",
                severity="critical" if shadow >= 0.18 else "warning",
                detail="Result has elevated crushed-shadow ratio.",
                value=round(shadow, 6),
                threshold=0.10,
            )
        )
    if detail <= 0.018:
        signals.append(
            MetricSignal(
                tag="low_detail",
                severity="warning",
                detail="Result detail-energy is low; inspect denoise or softness.",
                value=round(detail, 6),
                threshold=0.018,
            )
        )

    if reference_metrics:
        if delta.get("detail_energy", 0.0) <= -0.015:
            signals.append(
                MetricSignal(
                    tag="detail_loss",
                    severity="critical",
                    detail="Result lost detail compared with the reference.",
                    value=round(delta["detail_energy"], 6),
                    threshold=-0.015,
                )
            )
        if abs(delta.get("warmth", 0.0)) >= 0.18:
            signals.append(
                MetricSignal(
                    tag="color_shift",
                    severity="warning",
                    detail="Result has a large warmth shift compared with the reference.",
                    value=round(delta["warmth"], 6),
                    threshold=0.18,
                )
            )
        if abs(delta.get("mean_luma", 0.0)) >= 0.18:
            signals.append(
                MetricSignal(
                    tag="exposure_shift",
                    severity="warning",
                    detail="Result has a large exposure shift compared with the reference.",
                    value=round(delta["mean_luma"], 6),
                    threshold=0.18,
                )
            )
        if delta.get("saturation", 0.0) >= 0.25:
            signals.append(
                MetricSignal(
                    tag="over_saturation",
                    severity="warning",
                    detail="Result saturation increased sharply compared with the reference.",
                    value=round(delta["saturation"], 6),
                    threshold=0.25,
                )
            )

    return signals


def _normalized_tags(
    metric_signals: list[MetricSignal],
    qwen_judge_signal: QwenJudgeSignal | None,
    golden_calibration: GoldenCalibrationResult | None = None,
) -> list[str]:
    tags = [signal.tag for signal in metric_signals]
    if qwen_judge_signal:
        tags.extend(tag.strip() for tag in qwen_judge_signal.failure_tags if tag.strip())
        tags.extend(issue.issue_type.strip() for issue in qwen_judge_signal.localized_issues if issue.issue_type.strip())
    if golden_calibration:
        tags.extend(tag.strip() for tag in golden_calibration.added_failure_tags if tag.strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        normalized = tag.lower().replace(" ", "_")
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _verdict(
    metric_signals: list[MetricSignal],
    qwen_judge_signal: QwenJudgeSignal | None,
    golden_calibration: GoldenCalibrationResult | None = None,
) -> QualityVerdict:
    if golden_calibration and golden_calibration.calibrated_verdict == "fail":
        return "fail"
    if qwen_judge_signal and qwen_judge_signal.verdict == "fail":
        return "fail"
    critical_count = sum(1 for signal in metric_signals if signal.severity == "critical")
    if critical_count >= 2:
        return "fail"
    if golden_calibration and golden_calibration.calibrated_verdict == "suspicious":
        return "suspicious"
    if qwen_judge_signal and qwen_judge_signal.verdict == "suspicious":
        return "suspicious"
    if critical_count == 1 or metric_signals:
        return "suspicious"
    return "pass"


def _work_instructions(
    failure_tags: list[str],
    qwen_judge_signal: QwenJudgeSignal | None,
    golden_calibration: GoldenCalibrationResult | None = None,
) -> list[str]:
    instructions: list[str] = []
    if qwen_judge_signal and qwen_judge_signal.work_instruction:
        instructions.append(qwen_judge_signal.work_instruction)
    if qwen_judge_signal and qwen_judge_signal.retry_instruction:
        instructions.append(qwen_judge_signal.retry_instruction)
    if qwen_judge_signal:
        for issue in qwen_judge_signal.localized_issues:
            if issue.suggested_action:
                instructions.append(issue.suggested_action)
        plan = qwen_judge_signal.correction_plan
        plan_deltas: list[str] = []
        if plan.exposure_delta is not None:
            plan_deltas.append(f"exposure {plan.exposure_delta:+.2f} EV")
        if plan.contrast_delta is not None:
            plan_deltas.append(f"contrast {plan.contrast_delta:+.0f}")
        if plan.shadow_delta is not None:
            plan_deltas.append(f"shadows {plan.shadow_delta:+.0f}")
        if plan.highlight_delta is not None:
            plan_deltas.append(f"highlights {plan.highlight_delta:+.0f}")
        if plan.temperature_delta is not None:
            plan_deltas.append(f"temperature {plan.temperature_delta:+.0f}")
        if plan.tint_delta is not None:
            plan_deltas.append(f"tint {plan.tint_delta:+.0f}")
        if plan.saturation_delta is not None:
            plan_deltas.append(f"saturation {plan.saturation_delta:+.0f}")
        if plan.denoise_strength is not None:
            plan_deltas.append(f"denoise strength {plan.denoise_strength:.2f}")
        if plan.edit_strength is not None:
            plan_deltas.append(f"edit strength {plan.edit_strength:.2f}")
        if plan.crop_box_norm:
            plan_deltas.append("review the proposed crop box before applying")
        if plan_deltas:
            instructions.append("Draft correction plan: " + ", ".join(plan_deltas) + ".")
        if plan.notes:
            instructions.append(plan.notes)
    if golden_calibration and golden_calibration.adjustments:
        instructions.append("Golden calibration notes: " + " ".join(golden_calibration.adjustments))
    if golden_calibration and golden_calibration.replay_case_ids:
        instructions.append("Replay golden cases before tuning: " + ", ".join(golden_calibration.replay_case_ids) + ".")

    tag_actions = {
        "highlight_clip": "Retry with lower exposure, lower denoise aggressiveness, or a conservative highlight-preservation prompt.",
        "shadow_crush": "Retry with lifted shadows or guarded tone mapping.",
        "detail_loss": "Retry with lower denoise strength and stronger texture preservation.",
        "low_detail": "Inspect softness at 100 percent crop before accepting.",
        "color_shift": "Retry with color-preservation constraints and compare skin/product neutrals.",
        "exposure_shift": "Retry with reference exposure lock or lower generation strength.",
        "over_saturation": "Retry with lower saturation and color-stability guardrails.",
        "mask_boundary_failure": "Rebuild the mask and run boundary checker before generation.",
        "subject_damage": "Use a tighter mask and lower edit strength before retry.",
        "raw_ghosting": "Use guarded TriRaw fallback or a stricter alignment threshold.",
        "prompt_mismatch": "Rewrite the instruction with explicit preserve/remove constraints.",
        "missing_required_evidence": "Attach the missing evidence packet before accepting or tuning this result.",
        "qwen_judge_missing": "Run the local Qwen judge before making a tuning proposal.",
    }
    for tag in failure_tags:
        action = tag_actions.get(tag)
        if action:
            instructions.append(action)
    if not instructions and failure_tags:
        instructions.append("Generate one conservative retry and send it to human review before accepting.")
    if not instructions:
        instructions.append("No retry required unless human review finds a subjective issue.")
    return list(dict.fromkeys(instructions))


def _tuning_targets(failure_tags: list[str]) -> list[str]:
    targets: set[str] = set()
    for tag in failure_tags:
        if tag in {
            "highlight_clip",
            "shadow_crush",
            "detail_loss",
            "low_detail",
            "color_shift",
            "exposure_shift",
            "over_saturation",
            "technical_quality_low",
            "aesthetic_quality_low",
        }:
            targets.update({"metric_threshold", "preset", "rubric"})
        elif tag in {"mask_boundary_failure", "subject_damage"}:
            targets.update({"workflow", "mask_checker", "prompt"})
        elif tag in {"raw_ghosting"}:
            targets.update({"workflow", "raw_runtime", "metric_threshold"})
        elif tag in {"prompt_mismatch"}:
            targets.update({"prompt", "rubric"})
        elif tag in {"missing_required_evidence", "qwen_judge_missing"}:
            targets.update({"rubric", "golden_runner"})
        elif tag.endswith("_below_golden") or tag.endswith("_golden_fail") or tag.endswith("_golden_guard"):
            targets.update({"rubric", "golden_runner"})
        else:
            targets.add("rubric")
    if failure_tags:
        targets.add("code_proposal")
    return sorted(targets)


def _qwen_score_tuning_tags(qwen_judge_signal: QwenJudgeSignal | None) -> list[str]:
    if not qwen_judge_signal:
        return []
    scores = qwen_judge_signal.axis_scores
    tags: list[str] = []
    if scores.intent_match is not None and scores.intent_match < 0.55:
        tags.append("prompt_mismatch")
    if scores.subject_preservation is not None and scores.subject_preservation < 0.55:
        tags.append("subject_damage")
    if scores.mask_boundary is not None and scores.mask_boundary < 0.55:
        tags.append("mask_boundary_failure")
    if scores.color_naturalness is not None and scores.color_naturalness < 0.55:
        tags.append("color_shift")
    if scores.technical_quality is not None and scores.technical_quality < 0.50:
        tags.append("technical_quality_low")
    if scores.aesthetic_quality is not None and scores.aesthetic_quality < 0.50:
        tags.append("aesthetic_quality_low")
    return tags


def _worse_verdict(current: QualityVerdict, candidate: QualityVerdict) -> QualityVerdict:
    order = {"pass": 0, "suspicious": 1, "fail": 2}
    return candidate if order[candidate] > order[current] else current


def _axis_scores_dict(scores: QwenAxisScores) -> dict[str, float | None]:
    return scores.model_dump()


def _calibration_axis_scores(scores: QwenAxisScores | None) -> QwenAxisScores:
    return scores.model_copy(deep=True) if scores else QwenAxisScores()


def apply_golden_calibration(
    *,
    qwen_judge_signal: QwenJudgeSignal | None,
    judge_evidence_packet: JudgeEvidencePacket | None,
    metric_signals: list[MetricSignal],
    seed_root: str | Path = "seed_bundle",
) -> GoldenCalibrationResult:
    seed, path = _load_golden_calibration_seed(seed_root)
    tool = judge_evidence_packet.tool if judge_evidence_packet else "compare"
    profile = _select_golden_profile(seed, tool)
    if not profile:
        return GoldenCalibrationResult(
            applied=False,
            calibration_source=str(path) if path else None,
            profile_id="missing",
            notes=["Golden calibration seed was not found; raw Qwen and metric scores were used."],
        )

    profile_id = str(profile.get("profile_id") or "frontier_default")
    sample_count = int(profile.get("sample_count") or 0)
    replay_case_ids = [str(item) for item in profile.get("replay_case_ids") or []]
    notes = [str(item) for item in profile.get("notes") or []]
    adjustments: list[str] = []
    added_tags: list[str] = []
    calibrated_verdict: QualityVerdict = qwen_judge_signal.verdict if qwen_judge_signal else "suspicious"
    calibrated_confidence = qwen_judge_signal.confidence if qwen_judge_signal else 0.0
    calibrated_scores = _calibration_axis_scores(qwen_judge_signal.axis_scores if qwen_judge_signal else None)

    if not qwen_judge_signal:
        return GoldenCalibrationResult(
            applied=True,
            calibration_source=str(path) if path else None,
            profile_id=profile_id,
            sample_count=sample_count,
            calibrated_verdict="suspicious",
            calibrated_confidence=0.0,
            calibrated_axis_scores=calibrated_scores,
            added_failure_tags=["qwen_judge_missing"],
            adjustments=["Golden calibration requires a Qwen signal; assessment remains suspicious."],
            replay_required=True,
            replay_case_ids=replay_case_ids,
            notes=notes,
        )

    axis_values = _axis_scores_dict(qwen_judge_signal.axis_scores)
    suspicious_below = profile.get("axis_suspicious_below") if isinstance(profile.get("axis_suspicious_below"), dict) else {}
    fail_below = profile.get("axis_fail_below") if isinstance(profile.get("axis_fail_below"), dict) else {}
    for axis, threshold_value in suspicious_below.items():
        value = axis_values.get(str(axis))
        try:
            threshold = float(threshold_value)
        except (TypeError, ValueError):
            continue
        if value is not None and value < threshold:
            calibrated_verdict = _worse_verdict(calibrated_verdict, "suspicious")
            tag = f"{axis}_below_golden"
            added_tags.append(tag)
            adjustments.append(f"{axis} {value:.2f} is below golden suspicious threshold {threshold:.2f}.")
    for axis, threshold_value in fail_below.items():
        value = axis_values.get(str(axis))
        try:
            threshold = float(threshold_value)
        except (TypeError, ValueError):
            continue
        if value is not None and value < threshold:
            calibrated_verdict = _worse_verdict(calibrated_verdict, "fail")
            tag = f"{axis}_golden_fail"
            added_tags.append(tag)
            adjustments.append(f"{axis} {value:.2f} is below golden fail threshold {threshold:.2f}.")

    signal_penalties = profile.get("metric_signal_confidence_penalties")
    if not isinstance(signal_penalties, dict):
        signal_penalties = {}
    for signal in metric_signals:
        penalty = signal_penalties.get(signal.tag, signal_penalties.get(signal.severity, 0.0))
        try:
            penalty_value = float(penalty)
        except (TypeError, ValueError):
            penalty_value = 0.0
        if penalty_value > 0:
            calibrated_confidence = max(0.0, calibrated_confidence - penalty_value)
            adjustments.append(f"{signal.tag} reduced calibrated confidence by {penalty_value:.2f}.")
        if signal.severity == "critical":
            calibrated_verdict = _worse_verdict(calibrated_verdict, "suspicious")
            added_tags.append(f"{signal.tag}_golden_guard")

    if judge_evidence_packet:
        required_evidence = [str(item) for item in profile.get("required_evidence") or []]
        missing_required = [item for item in required_evidence if item in judge_evidence_packet.missing_evidence]
        if missing_required:
            cap = float(profile.get("confidence_cap_when_required_evidence_missing") or 0.72)
            if calibrated_confidence > cap:
                calibrated_confidence = cap
            calibrated_verdict = _worse_verdict(calibrated_verdict, "suspicious")
            added_tags.append("missing_required_evidence")
            adjustments.append("Missing required evidence for golden profile: " + ", ".join(missing_required) + ".")

    return GoldenCalibrationResult(
        applied=True,
        calibration_source=str(path) if path else None,
        profile_id=profile_id,
        sample_count=sample_count,
        calibrated_verdict=calibrated_verdict,
        calibrated_confidence=round(calibrated_confidence, 6),
        calibrated_axis_scores=calibrated_scores,
        added_failure_tags=list(dict.fromkeys(added_tags)),
        adjustments=list(dict.fromkeys(adjustments)),
        replay_required=True,
        replay_case_ids=replay_case_ids,
        notes=notes,
    )


def _assessment_dir(output_root: str | Path) -> Path:
    directory = resolve_output_root(output_root) / "_quality_automation" / "assessments"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _proposal_dir(output_root: str | Path) -> Path:
    directory = resolve_output_root(output_root) / "_quality_automation" / "tuning_proposals"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_quality_assessment(record: QualityAssessmentRecord) -> QualityAssessmentRecord:
    directory = _assessment_dir(record.output_root)
    path = directory / f"{record.assessment_id}.json"
    record.artifact_path = str(path)
    path.write_text(json.dumps(record.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_quality_assessment(path: str | Path) -> QualityAssessmentRecord:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return QualityAssessmentRecord(**payload)


def build_quality_assessment(
    *,
    result_path: str,
    output_root: str = "outputs",
    reference_path: str | None = None,
    session_id: str | None = None,
    tool: str = "compare",
    task_intent: str | None = None,
    qwen_judge_signal: QwenJudgeSignal | None = None,
    judge_evidence_packet: JudgeEvidencePacket | None = None,
    seed_root: str | Path = "seed_bundle",
    operation_context: dict[str, Any] | None = None,
    mask_evidence: dict[str, Any] | None = None,
    raw_evidence: dict[str, Any] | None = None,
    workflow_evidence: dict[str, Any] | None = None,
    user_preference_evidence: dict[str, Any] | None = None,
    write_artifact: bool = True,
) -> QualityAssessmentRecord:
    result_target = resolve_output_target(result_path, output_root=output_root)
    reference_target = resolve_output_target(reference_path, output_root=output_root) if reference_path else None
    result_metrics = rounded_compare_metrics(sample_image_metrics(result_target))
    reference_metrics = rounded_compare_metrics(sample_image_metrics(reference_target)) if reference_target else None
    delta = _metric_delta(result_metrics, reference_metrics)
    signals = _metric_signals(result_metrics, reference_metrics, delta)
    packet = judge_evidence_packet or build_judge_evidence_packet(
        result_path=str(result_target),
        output_root=output_root,
        reference_path=str(reference_target) if reference_target else None,
        tool=tool,
        task_intent=task_intent,
        seed_root=seed_root,
        operation_context=operation_context,
        mask_evidence=mask_evidence,
        raw_evidence=raw_evidence,
        workflow_evidence=workflow_evidence,
        user_preference_evidence=user_preference_evidence,
    )
    golden_calibration = apply_golden_calibration(
        qwen_judge_signal=qwen_judge_signal,
        judge_evidence_packet=packet,
        metric_signals=signals,
        seed_root=seed_root,
    )
    failure_tags = list(
        dict.fromkeys(
            [
                *_normalized_tags(signals, qwen_judge_signal, golden_calibration),
                *_qwen_score_tuning_tags(qwen_judge_signal),
            ]
        )
    )
    verdict = _verdict(signals, qwen_judge_signal, golden_calibration)
    human_reasons: list[str] = []
    if verdict in {"fail", "suspicious"}:
        human_reasons.append(f"{verdict}_verdict")
    if qwen_judge_signal and qwen_judge_signal.confidence < 0.70:
        human_reasons.append("low_qwen_judge_confidence")
    if golden_calibration.applied:
        human_reasons.append("golden_calibration_applied")
    if golden_calibration.calibrated_confidence is not None and golden_calibration.calibrated_confidence < 0.70:
        human_reasons.append("low_golden_calibrated_confidence")
    if golden_calibration.adjustments:
        human_reasons.append("golden_calibration_adjusted")
    if failure_tags:
        human_reasons.append("failure_tags_present")
    if verdict == "pass":
        human_reasons.append("sample_passes_for_human_audit")

    instructions = _work_instructions(failure_tags, qwen_judge_signal, golden_calibration)
    retry_plan = QualityRetryPlan(
        retry_allowed=verdict in {"fail", "suspicious"},
        human_approval_before_accept=verdict in {"fail", "suspicious"},
        max_attempts=2 if verdict == "fail" else 1,
        instructions=instructions if verdict in {"fail", "suspicious"} else [],
    )
    approval_required = (
        verdict in {"fail", "suspicious"}
        or "low_qwen_judge_confidence" in human_reasons
        or "low_golden_calibrated_confidence" in human_reasons
    )
    record = QualityAssessmentRecord(
        assessment_id=_assessment_id(),
        created_at=utc_now_iso(),
        session_id=session_id,
        output_root=str(resolve_output_root(output_root)),
        tool=normalize_tool_key(tool),
        result_path=str(result_target),
        reference_path=str(reference_target) if reference_target else None,
        verdict=verdict,
        human_approval_required=approval_required,
        human_review_reason=list(dict.fromkeys(human_reasons)),
        qwen_judge_signal=qwen_judge_signal,
        judge_evidence_packet=packet,
        golden_calibration=golden_calibration,
        result_metrics=result_metrics,
        reference_metrics=reference_metrics,
        metric_delta=delta,
        metric_signals=signals,
        failure_tags=failure_tags,
        work_instructions=instructions,
        retry_plan=retry_plan,
        tuning_targets=_tuning_targets(failure_tags),
        code_tuning_gate={
            "automatic_code_change": False,
            "human_approval_required": True,
            "requires_golden_regression": True,
            "golden_calibration_profile": golden_calibration.profile_id,
            "golden_calibrated_verdict": golden_calibration.calibrated_verdict,
            "allowed_output": "proposal_only",
        },
    )
    return save_quality_assessment(record) if write_artifact else record


def _coerce_assessment(value: QualityAssessmentRecord | dict[str, Any] | str | Path) -> QualityAssessmentRecord:
    if isinstance(value, QualityAssessmentRecord):
        return value
    if isinstance(value, dict):
        return QualityAssessmentRecord(**value)
    return load_quality_assessment(value)


def _suggested_change(tag: str, count: int) -> dict[str, Any]:
    target = "rubric"
    action = "tighten judge rubric and add a golden regression case"
    if tag in {"highlight_clip", "shadow_crush", "exposure_shift"}:
        target = "metric_threshold"
        action = "review tone thresholds and add exposure-preservation retry preset"
    elif tag in {"detail_loss", "low_detail"}:
        target = "preset"
        action = "review denoise/detail preset and add texture-preservation regression"
    elif tag == "technical_quality_low":
        target = "metric_threshold"
        action = "compare Qwen technical axis against deterministic metrics and add a golden regression case"
    elif tag == "aesthetic_quality_low":
        target = "rubric"
        action = "tighten aesthetic rubric with accepted style references before changing presets"
    elif tag in {"color_shift", "over_saturation"}:
        target = "prompt"
        action = "add color-preservation instruction and compare neutral-region metrics"
    elif tag in {"mask_boundary_failure", "subject_damage"}:
        target = "workflow"
        action = "route through stricter mask checker before generation"
    elif tag == "raw_ghosting":
        target = "raw_runtime"
        action = "raise alignment evidence requirement and prefer guarded fallback"
    elif tag == "prompt_mismatch":
        target = "prompt"
        action = "rewrite task prompt with explicit preserve/remove constraints"
    elif tag in {"missing_required_evidence", "qwen_judge_missing"}:
        target = "rubric"
        action = "require complete judge evidence before accepting a pass or drafting tuning"
    elif tag.endswith("_below_golden") or tag.endswith("_golden_fail") or tag.endswith("_golden_guard"):
        target = "rubric"
        action = "compare Qwen score against golden calibration and add or replay the matching golden case"
    return {
        "failure_tag": tag,
        "count": count,
        "target": target,
        "proposal": action,
        "automatic_apply": False,
        "requires_human_approval": True,
    }


def save_quality_tuning_proposal(proposal: QualityTuningProposal) -> QualityTuningProposal:
    directory = _proposal_dir(proposal.output_root)
    path = directory / f"{proposal.proposal_id}.json"
    proposal.artifact_path = str(path)
    path.write_text(json.dumps(proposal.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return proposal


def build_quality_tuning_proposal(
    *,
    output_root: str = "outputs",
    session_id: str | None = None,
    assessments: list[QualityAssessmentRecord | dict[str, Any] | str | Path] | None = None,
    write_artifact: bool = True,
) -> QualityTuningProposal:
    records = [_coerce_assessment(item) for item in (assessments or [])]
    tag_counter: Counter[str] = Counter()
    for record in records:
        tag_counter.update(record.failure_tags)
    suggested_changes = [_suggested_change(tag, count) for tag, count in tag_counter.most_common()]
    status: Literal["waiting_for_quality_evidence", "human_approval_required"] = (
        "human_approval_required" if records else "waiting_for_quality_evidence"
    )
    proposal = QualityTuningProposal(
        proposal_id=_proposal_id(),
        created_at=utc_now_iso(),
        output_root=str(resolve_output_root(output_root)),
        session_id=session_id,
        source_assessment_count=len(records),
        status=status,
        failure_clusters=dict(tag_counter),
        suggested_changes=suggested_changes,
        golden_runner_plan={
            "required_before_merge": True,
            "runner": "DreamCatcher Golden Session Runner",
            "calibration": "golden_quality_calibration_v1",
            "minimum_scope": [
                "replay affected workflow samples",
                "compare against accepted golden winners",
                "apply golden-calibrated verdict and confidence checks",
                "verify no new fail or suspicious regressions",
            ],
        },
        blocked_actions=[
            "apply_code_without_human_approval",
            "replace_workflow_without_regression",
            "change_metric_threshold_without_review",
            "release_without_golden_runner",
        ],
        allowed_next_actions=[
            "write_quality_report",
            "draft_tuning_patch_after_human_approval",
            "queue_golden_session_runner",
            "append_to_human_approval_memory",
        ],
    )
    return save_quality_tuning_proposal(proposal) if write_artifact else proposal
