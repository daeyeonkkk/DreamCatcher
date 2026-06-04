from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .recipe_router import choose_recipe, normalize_tool_key
from .studio_files import resolve_output_target


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_seed_root(seed_root: str | Path) -> Path:
    path = Path(seed_root)
    if not path.is_absolute():
        path = repo_root() / path
    return path.resolve()


@lru_cache(maxsize=24)
def _load_json_document(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_path(bundle_path: str | None) -> Path | None:
    if not bundle_path:
        return None
    path = Path(bundle_path)
    if not path.is_absolute():
        path = repo_root() / path
    return path.resolve()


def _safe_stat_band(payload: dict[str, Any], key: str) -> tuple[float | None, float | None]:
    stats = payload.get(key)
    if not isinstance(stats, dict):
        return None, None
    lower = stats.get("p10")
    upper = stats.get("p90")
    try:
        return (
            float(lower) if lower is not None else None,
            float(upper) if upper is not None else None,
        )
    except (TypeError, ValueError):
        return None, None


def _format_band(label: str, lower: float | None, upper: float | None, suffix: str = "") -> str | None:
    if lower is None or upper is None:
        return None
    return f"{label}: {lower:.2f}..{upper:.2f}{suffix}"


def sample_image_metrics(path: Path) -> dict[str, float]:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((512, 512), Image.Resampling.BILINEAR)
            pixels = np.asarray(image, dtype=np.float32)
    except UnidentifiedImageError as exc:
        raise ValueError(f"비교 안내가 이 이미지를 읽지 못했습니다: {path.name}") from exc

    if pixels.ndim != 3 or pixels.shape[2] < 3:
        raise ValueError(f"비교 안내는 RGB 계열 이미지를 기대했습니다: {path.name}")

    red = pixels[..., 0]
    green = pixels[..., 1]
    blue = pixels[..., 2]
    luminance = (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)

    if luminance.size == 0:
        raise ValueError(f"비교 안내가 읽을 수 있는 픽셀을 찾지 못했습니다: {path.name}")

    gradient_x = float(np.abs(np.diff(luminance, axis=1)).mean()) if luminance.shape[1] > 1 else 0.0
    gradient_y = float(np.abs(np.diff(luminance, axis=0)).mean()) if luminance.shape[0] > 1 else 0.0
    saturation = np.mean((np.max(pixels, axis=2) - np.min(pixels, axis=2)) / 255.0)

    return {
        "mean_luma": float(luminance.mean() / 255.0),
        "contrast": float(luminance.std() / 255.0),
        "highlight_clip_ratio": float(np.mean(luminance >= 250.0)),
        "shadow_clip_ratio": float(np.mean(luminance <= 5.0)),
        "warmth": float((red.mean() - blue.mean()) / 255.0),
        "saturation": float(saturation),
        "detail_energy": float(((gradient_x + gradient_y) * 0.5) / 255.0),
    }


def rounded_compare_metrics(payload: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 4) for key, value in payload.items()}


def _signal(severity: str, title: str, detail: str) -> dict[str, str]:
    return {
        "severity": severity,
        "title": title,
        "detail": detail,
    }


def _metric_label(metric: str) -> str:
    mapping = {
        "mean_luma": "밝기",
        "contrast": "대비",
        "highlight_clip_ratio": "하이라이트 클립",
        "shadow_clip_ratio": "암부 뭉침",
        "warmth": "화이트 밸런스 온도",
        "saturation": "채도",
        "detail_energy": "디테일 유지",
    }
    return mapping.get(metric, metric.replace("_", " "))


def _basename_label(path: str) -> str:
    return Path(path).name.lower()


def _motion_watch_payload(
    *,
    output_root: str,
    motion_overlay_path: str | None,
    motion_overlay_summary: str | None,
    motion_overlay_coverage: float | None,
    primary_path: str,
    candidate_path: str,
) -> dict[str, Any] | None:
    if not motion_overlay_path:
        return None
    try:
        overlay_target = resolve_output_target(motion_overlay_path, output_root=output_root)
    except ValueError:
        return None
    if not overlay_target.exists():
        return None

    try:
        coverage = max(0.0, min(1.0, float(motion_overlay_coverage))) if motion_overlay_coverage is not None else 0.0
    except (TypeError, ValueError):
        coverage = 0.0

    primary_name = _basename_label(primary_path)
    candidate_name = _basename_label(candidate_path)
    overlay_name = _basename_label(str(overlay_target))
    compares_overlay = primary_name == overlay_name or candidate_name == overlay_name
    candidate_is_scene_linear = (
        "scene_linear" in candidate_name
        or "scene-linear" in candidate_name
        or "base_16" in candidate_name
        or "merged" in candidate_name
    )
    candidate_is_preview_branch = "preview" in candidate_name or "hybrid" in candidate_name

    recommendation = "오버레이로 강조된 움직임 구역을 먼저 확인한 뒤 최종 비교 결정을 내리세요."
    if compares_overlay:
        recommendation = "오버레이는 진단용입니다. 움직임 구역을 확인한 뒤 실제 결과물끼리 비교하세요."
    elif coverage >= 0.08 and candidate_is_scene_linear:
        recommendation = "현재 후보는 장면 선형 마스터이고 움직임 범위도 큽니다. 채택 전에 강조 구역을 확대해 고스트 흔적을 확인하세요."
    elif coverage >= 0.08 and candidate_is_preview_branch:
        recommendation = "현재 후보는 미리보기 계열이라 움직임 범위가 클 때 더 안전한 검토 표면일 가능성이 높습니다."
    elif coverage < 0.02:
        recommendation = "움직임 감시가 조용하므로 이번 비교는 고스팅보다 톤과 디테일 판단 비중이 더 큽니다."

    return {
        "path": str(overlay_target),
        "summary": motion_overlay_summary or (
            "움직임 감시가 거의 조용합니다."
            if coverage < 0.01
            else f"움직임 감시가 프레임의 {coverage * 100.0:.1f}% 구역을 강조합니다."
        ),
        "coverage": round(coverage, 4),
        "compares_overlay": compares_overlay,
        "recommendation": recommendation,
    }


def _tool_checklist(tool: str) -> list[str]:
    if tool in {"removeBg", "replaceBg"}:
        return [
            "피사체 가장자리, 머리카락, 유리, 얇은 디테일 경계가 100% 확대에서도 자연스러운지 확인합니다.",
            "전경과 배경 밝기가 할로 없이 자연스럽게 이어지는지 확인합니다.",
            "새 배경이 피사체보다 과하게 시선을 끌지 않는지 확인합니다.",
        ]
    if tool == "expandCanvas":
        return [
            "새로 확장된 가장자리에서 결, 노이즈, 색온도가 원본 프레임과 끊기지 않는지 확인합니다.",
            "인물이나 제품의 비율이 늘어나거나 잘린 흔적 없이 원래 구도를 자연스럽게 이어 주는지 확인합니다.",
            "확장 구역이 시선을 과하게 끌지 않고 원본 중심 피사체를 보조하는 배경 역할을 유지하는지 확인합니다.",
        ]
    if tool == "relight":
        return [
            "얼굴, 제품 하이라이트, 그림자 방향이 의도한 광원과 맞는지 확인합니다.",
            "조명 보정 뒤 중성 영역이 지나치게 따뜻하거나 초록으로 치우치지 않는지 확인합니다.",
            "암부를 들어 올려도 피사체 입체감이 납작해지지 않는지 확인합니다.",
        ]
    if tool in {"retouch", "enhance"}:
        return [
            "피부, 라벨, 의상 질감이 100% 확대에서도 밀랍처럼 뭉개지지 않는지 확인합니다.",
            "밝은 흰색과 반사 하이라이트가 거칠게 클립되지 않고 부드럽게 이어지는지 확인합니다.",
            "이 후보가 같은 세트의 인접 컷과 나란히 놓여도 어색하지 않은지 확인합니다.",
        ]
    return [
        "밝은 흰색, 피부, 금속 하이라이트가 100% 확대에서도 부드럽게 이어지는지 확인합니다.",
        "화이트 밸런스와 전체 색감이 유지 후보 기준 컷과 어긋나지 않는지 확인합니다.",
        "한 장만 좋아 보이는지 말고, 전체 세트를 개선하는 버전인지 확인합니다.",
    ]


def _risk_points(signals: list[dict[str, str]]) -> int:
    total = 0
    for item in signals:
        severity = item.get("severity")
        if severity == "risk":
            total += 2
        elif severity == "warning":
            total += 1
    return total


def _risk_level(total_points: int) -> str:
    if total_points >= 4:
        return "high"
    if total_points >= 2:
        return "medium"
    return "low"


def _dominant_dimensions(payload: dict[str, Any], tool: str) -> list[str]:
    overrides = payload.get("tool_overrides")
    dimensions = payload.get("dimensions")
    if not isinstance(overrides, dict) or not isinstance(dimensions, dict):
        return []
    weights = overrides.get(tool)
    if not isinstance(weights, dict):
        return []

    ranked = sorted(
        (
            (str(key), float(value))
            for key, value in weights.items()
            if isinstance(value, (int, float))
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    labels: list[str] = []
    for key, _weight in ranked:
        dimension = dimensions.get(key)
        if isinstance(dimension, dict) and isinstance(dimension.get("label"), str):
            labels.append(str(dimension["label"]))
        else:
            labels.append(key)
    return labels


def _prior_guardrails(
    runtime_prior_artifacts: list[dict[str, Any]],
    *,
    tool: str,
) -> tuple[list[str], list[str]]:
    guardrails: list[str] = []
    priority_dimensions: list[str] = []

    for artifact in runtime_prior_artifacts:
        artifact_id = str(artifact.get("artifact_id") or "")
        path = _artifact_path(artifact.get("bundle_path"))
        payload = _load_json_document(str(path)) if path else {}
        if not payload:
            continue

        if artifact_id == "dear_rendering_seed":
            stats = payload.get("rendering_parameter_stats")
            if isinstance(stats, dict):
                exposure_band = _format_band("DEAR 노출", *_safe_stat_band(stats, "Exposure"), " EV")
                temperature_band = _format_band("DEAR 색온도", *_safe_stat_band(stats, "Temperature"), " K")
                contrast_band = _format_band("DEAR 대비", *_safe_stat_band(stats, "Contrast"))
                for item in (exposure_band, temperature_band, contrast_band):
                    if item:
                        guardrails.append(item)

        elif artifact_id == "mmart_ppr10k_reference_pack":
            stats = payload.get("adjustment_stats")
            if isinstance(stats, dict):
                exposure_band = _format_band("MMArt 리터치 노출", *_safe_stat_band(stats, "Exposure2012"), " EV")
                highlight_band = _format_band("MMArt 하이라이트 복원", *_safe_stat_band(stats, "Highlights2012"))
                shadow_band = _format_band("MMArt 암부 리프트", *_safe_stat_band(stats, "Shadows2012"))
                for item in (exposure_band, highlight_band, shadow_band):
                    if item:
                        guardrails.append(item)

        elif artifact_id == "edit_evaluator_rules":
            priority_dimensions = _dominant_dimensions(payload, tool)

    return guardrails[:5], priority_dimensions


def _frontier_activation_guardrails(
    frontier_dataset_items: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    guardrails: list[str] = []
    priority_dimensions: list[str] = []
    dimension_by_use = {
        "compare_guardrail": "tone_safety",
        "retouch_reference_prior": "reference_consistency",
        "mask_boundary_eval": "mask_boundary_quality",
        "cutout_model_evidence": "subject_edge_fidelity",
        "composition_guardrail": "composition_consistency",
        "subject_preservation_eval": "subject_preservation",
        "mask_distribution_regression": "mask_distribution_coverage",
        "large_hole_fill_eval": "large_hole_coherence",
        "tri_raw_frontier_eval": "raw_merge_confidence",
        "alignment_ghost_denoise_evidence": "alignment_ghost_denoise_balance",
    }
    active_stages = {"runtime_prior_active", "model_contract_active", "adapter_hook_active", "eval_guardrail_ready"}

    for item in frontier_dataset_items:
        stage = str(item.get("activation_stage") or "")
        if stage not in active_stages:
            continue
        label = str(item.get("label") or item.get("dataset_id") or "Frontier dataset")
        uses = [str(value) for value in item.get("studio_use", []) if str(value).strip()]
        if uses:
            guardrails.append(f"Frontier {stage}: {label} informs {', '.join(uses[:2])}.")
        for use in uses:
            dimension = dimension_by_use.get(use)
            if dimension and dimension not in priority_dimensions:
                priority_dimensions.append(dimension)

    return guardrails[:4], priority_dimensions[:4]


def _local_compare_learning(
    runtime_prior_artifacts: list[dict[str, Any]],
    *,
    tool: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    guardrails: list[str] = []
    preference_rules: list[dict[str, Any]] = []

    for artifact in runtime_prior_artifacts:
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact_id != "local_compare_learning_seed":
            continue
        path = _artifact_path(artifact.get("bundle_path"))
        payload = _load_json_document(str(path)) if path else {}
        if not payload:
            continue
        tool_stats = payload.get("tool_stats")
        if not isinstance(tool_stats, dict):
            continue
        tool_payload = tool_stats.get(tool) or tool_stats.get("compare")
        if not isinstance(tool_payload, dict):
            continue
        decision_count = tool_payload.get("decision_count")
        if isinstance(decision_count, int) and decision_count > 0:
            guardrails.append(f"로컬 비교 기억: 승인된 결정 {decision_count}건")
        patterns = tool_payload.get("preferred_patterns")
        if isinstance(patterns, list):
            guardrails.extend(str(item) for item in patterns[:2] if str(item).strip())
        rules = tool_payload.get("preference_rules")
        if isinstance(rules, list):
            preference_rules = [item for item in rules if isinstance(item, dict)]
        break

    return guardrails[:3], preference_rules


def _local_learning_signals(delta: dict[str, float], rules: list[dict[str, Any]]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for rule in rules:
        metric = str(rule.get("metric") or "").strip()
        direction = str(rule.get("preferred_direction") or "").strip()
        support = int(rule.get("support") or 0)
        if not metric or direction not in {"lower", "higher"} or support < 2:
            continue
        value = delta.get(metric)
        if value is None:
            continue
        try:
            threshold = float(rule.get("activation_threshold") or 0.0)
        except (TypeError, ValueError):
            threshold = 0.0
        label = str(rule.get("label") or _metric_label(metric))

        if direction == "lower" and value > threshold:
            severity = "risk" if support >= 6 and value > threshold * 2 else "warning"
            signals.append(
                _signal(
                    severity,
                    f"로컬 승자들은 보통 {label}이 더 낮습니다",
                    f"지금까지 채택된 결과는 보통 제외된 버전보다 {label}이 더 낮았는데, 이번 대안 후보는 반대로 움직입니다.",
                )
            )
        elif direction == "higher" and value < -threshold:
            severity = "risk" if support >= 6 and abs(value) > threshold * 2 else "warning"
            signals.append(
                _signal(
                    severity,
                    f"로컬 승자들은 보통 {label}이 더 높습니다",
                    f"지금까지 채택된 결과는 보통 제외된 버전보다 {label}이 더 높았는데, 이번 대안 후보는 그 패턴보다 아래로 내려갑니다.",
                )
            )
    return signals


def build_compare_advice(
    *,
    output_root: str,
    primary_path: str,
    candidate_path: str,
    tool: str = "compare",
    seed_root: str = "seed_bundle",
    motion_overlay_path: str | None = None,
    motion_overlay_summary: str | None = None,
    motion_overlay_coverage: float | None = None,
) -> dict[str, Any]:
    normalized_tool = normalize_tool_key(tool)
    seed_root_path = _resolve_seed_root(seed_root)
    primary_target = resolve_output_target(primary_path, output_root=output_root)
    candidate_target = resolve_output_target(candidate_path, output_root=output_root)

    primary_metrics = sample_image_metrics(primary_target)
    candidate_metrics = sample_image_metrics(candidate_target)
    delta = {key: candidate_metrics[key] - primary_metrics[key] for key in primary_metrics}

    decision = choose_recipe(normalized_tool, seed_root=seed_root_path)
    public_prior_labels = [str(item.get("label") or item.get("dataset_id") or "") for item in decision.public_priors][:4]
    community_takeaways = decision.community_takeaways[:2]
    prior_guardrails, priority_dimensions = _prior_guardrails(
        decision.runtime_prior_artifacts,
        tool=normalized_tool,
    )
    frontier_guardrails, frontier_priority_dimensions = _frontier_activation_guardrails(
        decision.frontier_dataset_items,
    )
    local_learning_guardrails, local_learning_rules = _local_compare_learning(
        decision.runtime_prior_artifacts,
        tool=normalized_tool,
    )
    motion_watch = _motion_watch_payload(
        output_root=output_root,
        motion_overlay_path=motion_overlay_path,
        motion_overlay_summary=motion_overlay_summary,
        motion_overlay_coverage=motion_overlay_coverage,
        primary_path=primary_path,
        candidate_path=candidate_path,
    )

    signals: list[dict[str, str]] = []
    if motion_watch is not None:
        if motion_watch["compares_overlay"]:
            signals.append(
                _signal(
                    "warning",
                    "오버레이는 진단 레이어입니다",
                    "이번 비교 쌍의 한쪽이 움직임 오버레이 자체입니다. 위험 구역 점검에는 쓰되, 최종 결과물처럼 채택하면 안 됩니다.",
                )
            )
        elif float(motion_watch["coverage"]) >= 0.10:
            candidate_label = _basename_label(candidate_path)
            severity = (
                "risk"
                if (
                    "scene_linear" in candidate_label
                    or "scene-linear" in candidate_label
                    or "merged" in candidate_label
                    or "base_16" in candidate_label
                )
                else "warning"
            )
            signals.append(
                _signal(
                    severity,
                    "움직임 감시가 활성화됐습니다",
                    motion_watch["recommendation"],
                )
            )
        elif float(motion_watch["coverage"]) >= 0.03:
            signals.append(
                _signal(
                    "info",
                    "강조된 움직임 구역을 확인하세요",
                    motion_watch["recommendation"],
                )
            )

    if delta["highlight_clip_ratio"] >= 0.015:
        severity = "risk" if delta["highlight_clip_ratio"] >= 0.035 else "warning"
        signals.append(
            _signal(
                severity,
                "하이라이트 클립이 더 강해졌습니다",
                f"대안 후보의 하이라이트 클립 비율이 {candidate_metrics['highlight_clip_ratio'] * 100:.1f}%로, 유지 후보의 {primary_metrics['highlight_clip_ratio'] * 100:.1f}%보다 높습니다.",
            )
        )
    elif delta["highlight_clip_ratio"] <= -0.01:
        signals.append(
            _signal(
                "info",
                "하이라이트 롤오프가 더 안전합니다",
                f"대안 후보가 클립된 하이라이트를 {primary_metrics['highlight_clip_ratio'] * 100:.1f}%에서 {candidate_metrics['highlight_clip_ratio'] * 100:.1f}%로 줄였습니다.",
            )
        )

    if delta["shadow_clip_ratio"] >= 0.02:
        severity = "risk" if delta["shadow_clip_ratio"] >= 0.05 else "warning"
        signals.append(
            _signal(
                severity,
                "암부가 더 막히고 있습니다",
                f"대안 후보의 깊은 암부 비율이 {candidate_metrics['shadow_clip_ratio'] * 100:.1f}%로, 유지 후보의 {primary_metrics['shadow_clip_ratio'] * 100:.1f}%보다 높습니다.",
            )
        )
    elif delta["shadow_clip_ratio"] <= -0.015:
        signals.append(
            _signal(
                "info",
                "암부 열림이 더 깨끗합니다",
                f"대안 후보가 암부 디테일을 {abs(delta['shadow_clip_ratio']) * 100:.1f}포인트만큼 더 열어 줍니다.",
            )
        )

    if abs(delta["mean_luma"]) >= 0.08:
        tone_word = "더 밝아졌습니다" if delta["mean_luma"] > 0 else "더 어두워졌습니다"
        severity = "warning" if abs(delta["mean_luma"]) < 0.14 else "risk"
        signals.append(
            _signal(
                severity,
                f"노출이 {tone_word}",
                f"대안 후보의 평균 장면 밝기가 {abs(delta['mean_luma']) * 100:.1f}포인트 움직여, 채택 전 점검 기준으로는 변화폭이 큰 편입니다.",
            )
        )

    if abs(delta["warmth"]) >= 0.08:
        direction = "더 따뜻해졌습니다" if delta["warmth"] > 0 else "더 차가워졌습니다"
        signals.append(
            _signal(
                "warning",
                f"화이트 밸런스가 {direction}",
                f"대안 후보의 온도감이 유지 후보 대비 {abs(delta['warmth']) * 100:.1f}포인트 움직였습니다.",
            )
        )

    if delta["saturation"] >= 0.08:
        severity = "warning" if delta["saturation"] < 0.14 else "risk"
        signals.append(
            _signal(
                severity,
                "색 밀어올림이 과합니다",
                f"대안 후보의 채도가 {delta['saturation'] * 100:.1f}포인트 올라갔습니다. 채택 전 피부, 흰색, 제품 색을 다시 확인하세요.",
            )
        )
    elif delta["saturation"] <= -0.08:
        signals.append(
            _signal(
                "warning",
                "색이 평평해졌을 수 있습니다",
                f"대안 후보의 채도가 유지 후보보다 {abs(delta['saturation']) * 100:.1f}포인트 낮아졌습니다.",
            )
        )

    if delta["detail_energy"] <= -0.02:
        signals.append(
            _signal(
                "warning",
                "미세 디테일이 부드러워졌습니다",
                f"경계 에너지가 {primary_metrics['detail_energy']:.3f}에서 {candidate_metrics['detail_energy']:.3f}로 내려갔습니다. 채택 전 질감을 확대해 확인하세요.",
            )
        )
    elif delta["detail_energy"] >= 0.02 and delta["highlight_clip_ratio"] >= 0.01:
        signals.append(
            _signal(
                "info",
                "더 또렷하지만 거칠어질 수 있습니다",
                "대안 후보가 더 선명해 보이지만, 그만큼 하이라이트 압박도 함께 커졌습니다.",
            )
        )

    signals.extend(_local_learning_signals(delta, local_learning_rules))

    if not signals:
        signals.append(
            _signal(
                "info",
                "뚜렷한 위험 급등은 없습니다",
                "대안 후보가 클립, 색, 디테일 면에서 유지 후보와 크게 벌어지지 않아 최종 수동 점검까지는 안전한 편입니다.",
            )
        )

    total_points = _risk_points(signals)
    risk_level = _risk_level(total_points)
    if risk_level == "high":
        summary = "대안 후보가 더 강하게 보이지만, 유지 후보 기준점에서 꽤 멀어져 있어 채택 전 세밀한 최종 점검이 필요합니다."
    elif risk_level == "medium":
        summary = "대안 후보가 유망해 보이지만, 한두 개 신호가 충분히 움직여서 집중 점검을 한 번 더 하는 편이 좋습니다."
    else:
        summary = "대안 후보가 실무적으로 허용 가능한 범위 안에 있어 계속 검토해도 비교적 안전합니다."

    return {
        "tool": normalized_tool,
        "summary": summary,
        "risk_level": risk_level,
        "signals": signals[:5],
        "checklist": _tool_checklist(normalized_tool),
        "public_prior_labels": [label for label in public_prior_labels if label],
        "community_takeaways": community_takeaways,
        "prior_guardrails": [*prior_guardrails, *frontier_guardrails, *local_learning_guardrails][:6],
        "priority_dimensions": list(dict.fromkeys([*priority_dimensions, *frontier_priority_dimensions])),
        "select_metrics": rounded_compare_metrics(primary_metrics),
        "candidate_metrics": rounded_compare_metrics(candidate_metrics),
        "motion_watch": motion_watch,
    }
