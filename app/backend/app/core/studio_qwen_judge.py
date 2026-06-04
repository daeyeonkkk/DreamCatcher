from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx

from .studio_files import resolve_output_target
from .studio_quality_automation import (
    QWEN_AUTOMATION_MODEL,
    QWEN_JUDGE_SIGNAL_SCHEMA_VERSION,
    QwenAxisScores,
    QwenCorrectionPlan,
    QwenJudgeSignal,
    QwenLocalizedIssue,
    build_judge_evidence_packet,
)


QWEN_JUDGE_MODEL_REPO = "Qwen/Qwen3.6-35B-A3B-FP8"
QWEN_JUDGE_DEFAULT_BASE_URL = "http://127.0.0.1:8011/v1"


class QwenJudgeError(RuntimeError):
    pass


def qwen_judge_model_id() -> str:
    return os.getenv("DC_QWEN_JUDGE_MODEL", QWEN_JUDGE_MODEL_REPO) or QWEN_JUDGE_MODEL_REPO


def qwen_judge_base_url() -> str:
    return os.getenv("DC_QWEN_JUDGE_BASE_URL", QWEN_JUDGE_DEFAULT_BASE_URL) or QWEN_JUDGE_DEFAULT_BASE_URL


def qwen_judge_model_path() -> str:
    return os.getenv(
        "DC_QWEN_JUDGE_MODEL_PATH",
        "/workspace/DreamCatcher/models/qwen_judge/Qwen3.6-35B-A3B-FP8",
    )


def qwen_judge_configured() -> bool:
    return bool(qwen_judge_base_url().strip() and qwen_judge_model_id().strip())


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise QwenJudgeError("Qwen judge response did not include choices[0].message.content.") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    raise QwenJudgeError("Qwen judge response content was not text.")


def _coerce_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        stripped = stripped[start : end + 1]
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise QwenJudgeError("Qwen judge response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise QwenJudgeError("Qwen judge JSON response was not an object.")
    return payload


def _clamp_float(value: Any, *, default: float | None = None, minimum: float = 0.0, maximum: float = 1.0) -> float | None:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _optional_float(value: Any, *, minimum: float, maximum: float) -> float | None:
    return _clamp_float(value, default=None, minimum=minimum, maximum=maximum)


def _normalized_float_list(value: Any, *, expected_len: int) -> list[float] | None:
    if not isinstance(value, list) or len(value) != expected_len:
        return None
    values: list[float] = []
    for item in value:
        parsed = _clamp_float(item, default=None, minimum=0.0, maximum=1.0)
        if parsed is None:
            return None
        values.append(round(parsed, 6))
    return values


def _normalize_axis_scores(value: Any) -> QwenAxisScores:
    payload = value if isinstance(value, dict) else {}
    return QwenAxisScores(
        intent_match=_clamp_float(payload.get("intent_match"), default=None),
        technical_quality=_clamp_float(payload.get("technical_quality"), default=None),
        aesthetic_quality=_clamp_float(payload.get("aesthetic_quality"), default=None),
        subject_preservation=_clamp_float(payload.get("subject_preservation"), default=None),
        mask_boundary=_clamp_float(payload.get("mask_boundary"), default=None),
        color_naturalness=_clamp_float(payload.get("color_naturalness"), default=None),
    )


def _normalize_localized_issues(value: Any) -> list[QwenLocalizedIssue]:
    if not isinstance(value, list):
        return []
    issues: list[QwenLocalizedIssue] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        area = str(item.get("area") or "").strip()
        issue_type = str(item.get("issue_type") or "").strip().lower().replace(" ", "_")
        description = str(item.get("description") or "").strip()
        if not area or not issue_type or not description:
            continue
        severity = str(item.get("severity") or "warning").strip().lower()
        if severity not in {"info", "warning", "critical"}:
            severity = "warning"
        issues.append(
            QwenLocalizedIssue(
                area=area,
                issue_type=issue_type,
                severity=severity,  # type: ignore[arg-type]
                description=description,
                confidence=_clamp_float(item.get("confidence"), default=None),
                bbox_norm=_normalized_float_list(item.get("bbox_norm"), expected_len=4),
                suggested_action=str(item.get("suggested_action") or "").strip() or None,
            )
        )
    return issues


def _normalize_correction_plan(value: Any) -> QwenCorrectionPlan:
    payload = value if isinstance(value, dict) else {}
    return QwenCorrectionPlan(
        exposure_delta=_optional_float(payload.get("exposure_delta"), minimum=-3.0, maximum=3.0),
        contrast_delta=_optional_float(payload.get("contrast_delta"), minimum=-100.0, maximum=100.0),
        shadow_delta=_optional_float(payload.get("shadow_delta"), minimum=-100.0, maximum=100.0),
        highlight_delta=_optional_float(payload.get("highlight_delta"), minimum=-100.0, maximum=100.0),
        temperature_delta=_optional_float(payload.get("temperature_delta"), minimum=-100.0, maximum=100.0),
        tint_delta=_optional_float(payload.get("tint_delta"), minimum=-100.0, maximum=100.0),
        saturation_delta=_optional_float(payload.get("saturation_delta"), minimum=-100.0, maximum=100.0),
        denoise_strength=_optional_float(payload.get("denoise_strength"), minimum=0.0, maximum=1.0),
        edit_strength=_optional_float(payload.get("edit_strength"), minimum=0.0, maximum=1.0),
        crop_box_norm=_normalized_float_list(payload.get("crop_box_norm"), expected_len=4),
        notes=str(payload.get("notes") or "").strip() or None,
    )


def _normalize_signal(payload: dict[str, Any]) -> QwenJudgeSignal:
    verdict = str(payload.get("verdict") or "suspicious").strip().lower()
    if verdict not in {"fail", "suspicious", "pass"}:
        verdict = "suspicious"
    failure_tags = payload.get("failure_tags") or []
    if not isinstance(failure_tags, list):
        failure_tags = [str(failure_tags)]
    return QwenJudgeSignal(
        schema_version=QWEN_JUDGE_SIGNAL_SCHEMA_VERSION,
        verdict=verdict,  # type: ignore[arg-type]
        confidence=_clamp_float(payload.get("confidence"), default=0.0) or 0.0,
        axis_scores=_normalize_axis_scores(payload.get("axis_scores")),
        rationale=str(payload.get("rationale") or "").strip() or None,
        failure_tags=[str(tag).strip().lower().replace(" ", "_") for tag in failure_tags if str(tag).strip()],
        localized_issues=_normalize_localized_issues(payload.get("localized_issues")),
        correction_plan=_normalize_correction_plan(payload.get("correction_plan")),
        retry_instruction=str(payload.get("retry_instruction") or "").strip() or None,
        work_instruction=str(payload.get("work_instruction") or "").strip() or None,
    )


def _qwen_response_contract_text() -> str:
    return (
        "Return strict JSON only. Do not wrap it in Markdown. "
        "The object must match this schema: "
        "{"
        '"schema_version":"qwen_judge_signal_v2",'
        '"verdict":"fail|suspicious|pass",'
        '"confidence":0.0,'
        '"axis_scores":{'
        '"intent_match":0.0,'
        '"technical_quality":0.0,'
        '"aesthetic_quality":0.0,'
        '"subject_preservation":0.0,'
        '"mask_boundary":0.0,'
        '"color_naturalness":0.0'
        "},"
        '"failure_tags":["short_snake_case"],'
        '"localized_issues":[{'
        '"area":"subject|background|skin|hair|dress|product|text|whole_image",'
        '"issue_type":"short_snake_case",'
        '"severity":"info|warning|critical",'
        '"description":"brief visual evidence",'
        '"confidence":0.0,'
        '"bbox_norm":[0.0,0.0,1.0,1.0],'
        '"suggested_action":"operator-facing fix"'
        "}],"
        '"correction_plan":{'
        '"exposure_delta":null,'
        '"contrast_delta":null,'
        '"shadow_delta":null,'
        '"highlight_delta":null,'
        '"temperature_delta":null,'
        '"tint_delta":null,'
        '"saturation_delta":null,'
        '"denoise_strength":null,'
        '"edit_strength":null,'
        '"crop_box_norm":null,'
        '"notes":null'
        "},"
        '"rationale":"brief reason",'
        '"retry_instruction":"specific retry instruction",'
        '"work_instruction":"specific human/operator instruction"'
        "}. "
        "Axis scores are 0.0-1.0 where 1.0 is best. Use null for unknown correction numbers. "
        "Do not invent camera settings, EXIF, or exact physical causes without evidence."
    )


def build_qwen_judge_signal(
    *,
    result_path: str,
    output_root: str = "outputs",
    reference_path: str | None = None,
    tool: str = "compare",
    task_intent: str | None = None,
    seed_root: str = "seed_bundle",
    operation_context: dict[str, Any] | None = None,
    mask_evidence: dict[str, Any] | None = None,
    raw_evidence: dict[str, Any] | None = None,
    workflow_evidence: dict[str, Any] | None = None,
    user_preference_evidence: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> QwenJudgeSignal:
    if not qwen_judge_configured():
        raise QwenJudgeError("Qwen judge endpoint is not configured.")

    result_target = resolve_output_target(result_path, output_root=output_root)
    reference_target = resolve_output_target(reference_path, output_root=output_root) if reference_path else None
    evidence_packet = build_judge_evidence_packet(
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
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are DreamCatcher Studio's local quality judge. "
                "Judge the image as a conservative professional photo-editing assistant. "
                "Use the supplied evidence packet as the source of truth; do not replace metrics, "
                "RAW evidence, mask evidence, workflow settings, or user preference memory with guesses. "
                f"{_qwen_response_contract_text()} "
                "Judge evidence packet JSON: "
                f"{json.dumps(evidence_packet.model_dump(), ensure_ascii=False, sort_keys=True)}"
            ),
        }
    ]
    if reference_target:
        content.append({"type": "text", "text": "Reference image:"})
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(reference_target)}})
    content.append({"type": "text", "text": "Result image:"})
    content.append({"type": "image_url", "image_url": {"url": _image_data_url(result_target)}})

    endpoint = f"{qwen_judge_base_url().rstrip('/')}/chat/completions"
    request_payload = {
        "model": qwen_judge_model_id(),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You inspect photo edit quality. Be conservative: fail obvious damage, "
                    "mark uncertain subjective issues suspicious, pass only when the result is clean."
                ),
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "max_tokens": 1400,
    }
    headers = {"Content-Type": "application/json", "X-DreamCatcher-Judge": QWEN_AUTOMATION_MODEL}
    timeout = timeout_seconds or float(os.getenv("DC_QWEN_JUDGE_TIMEOUT_SECONDS", "120"))
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, headers=headers, json=request_payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise QwenJudgeError(f"Qwen judge request failed: {exc}") from exc

    content_text = _extract_content(response.json())
    return _normalize_signal(_coerce_json_object(content_text))
