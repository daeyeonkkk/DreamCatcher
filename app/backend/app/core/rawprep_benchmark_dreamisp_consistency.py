from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from app.raw_engine_v2.isp.planner import DreamISPHandoffPlan, build_dreamisp_handoff_plan, materialize_dreamisp_handoff_plan
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render

from .studio_paths import repo_root, resolve_output_root


class RawPrepDreamISPConsistencyRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    local_e2e_smoke_path: str | None = None


class RawPrepDreamISPConsistencyFlow(BaseModel):
    flow_key: str
    status: str = "missing"
    source_stage: str | None = None
    source_item_key: str | None = None
    original_preview_path: str | None = None
    rerender_preview_path: str | None = None
    render_state_path: str | None = None
    plan_path: str | None = None
    report_path: str | None = None
    backend: str | None = None
    source_kind: str | None = None
    pixel_match: bool = False
    mean_luminance_original: float | None = None
    mean_luminance_rerender: float | None = None
    mean_luminance_delta: float | None = None
    checks: dict[str, bool] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    summary: str = ""


class RawPrepDreamISPConsistencyArtifact(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_evidence"
    summary: str
    artifact_path: str | None = None
    local_e2e_smoke_path: str | None = None
    checks: dict[str, bool] = Field(default_factory=dict)
    single_raw: RawPrepDreamISPConsistencyFlow
    tri_raw: RawPrepDreamISPConsistencyFlow
    blockers: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


def _resolve_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("DreamISP consistency output_dir must stay inside the configured output root.") from exc
    return resolved


def _artifact_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_dreamisp_consistency_smoke.json"


def _resolve_local_e2e_smoke_path(request: RawPrepDreamISPConsistencyRequest) -> Path:
    if request.local_e2e_smoke_path:
        candidate = Path(request.local_e2e_smoke_path)
        return candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    return _resolve_output_dir(request.output_dir, output_root=request.output_root) / "rawprep_local_e2e_smoke.json"


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_rgb_pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _resolve_evidence_path(path_value: str | None) -> Path | None:
    cleaned = str(path_value or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    return (repo_root() / candidate).resolve()


def _mean_luminance_from_pixels(pixels: np.ndarray) -> float:
    rgb = pixels.astype(np.float32) / 255.0
    return float(np.mean(np.dot(rgb[..., :3], np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))))


def _prepare_rerender_plan(original_plan_path: Path, render_state_path: Path, rerender_root: Path) -> DreamISPHandoffPlan:
    original_plan_payload = json.loads(original_plan_path.read_text(encoding="utf-8"))
    if not isinstance(original_plan_payload, dict):
        raise ValueError(f"DreamISP plan is invalid: {original_plan_path}")
    original_plan = DreamISPHandoffPlan(**original_plan_payload)
    render_state_payload = json.loads(render_state_path.read_text(encoding="utf-8"))
    if not isinstance(render_state_payload, dict):
        raise ValueError(f"DreamISP render state is invalid: {render_state_path}")

    base_plan = build_dreamisp_handoff_plan(
        session_root=rerender_root,
        source_stage=original_plan.source_stage,
        source_item_key=original_plan.source_item_key,
        source_engine_key=original_plan.source_engine_key,
        source_engine_version=original_plan.source_engine_version,
        scene_linear_path=original_plan.scene_linear_path,
        preview_path=original_plan.preview_path,
        source_report_path=original_plan.source_report_path,
        source_diagnostics_manifest_path=original_plan.source_diagnostics_manifest_path,
    )
    for key in ("white_balance", "tone", "color", "detail"):
        if isinstance(render_state_payload.get(key), dict):
            base_plan.render_state[key] = render_state_payload[key]
    base_plan = materialize_dreamisp_handoff_plan(base_plan)
    rerendered_plan = materialize_dreamisp_lite_render(base_plan)
    rerender_preview_path = Path(str(rerendered_plan.render_preview_path or "").strip()) if rerendered_plan.render_preview_path else None
    if rerender_preview_path is None or not rerender_preview_path.is_file():
        raise ValueError(f"DreamISP rerender did not materialize an editable preview: {original_plan_path}")
    return rerendered_plan


def _build_flow_consistency(
    flow_key: str,
    flow_payload: dict[str, Any],
    *,
    rerender_root: Path,
) -> RawPrepDreamISPConsistencyFlow:
    original_preview_path = _resolve_evidence_path(flow_payload.get("dreamisp_render_preview_path"))
    render_state_path = _resolve_evidence_path(flow_payload.get("dreamisp_render_state_path"))
    plan_path = render_state_path.with_name("dreamisp_plan.json") if render_state_path is not None else None
    report_path = render_state_path.with_name("report.json") if render_state_path is not None else None

    issues: list[str] = []
    for required_path, label in (
        (original_preview_path, "DreamISP editable preview"),
        (render_state_path, "DreamISP render state"),
        (plan_path, "DreamISP plan"),
        (report_path, "DreamISP report"),
    ):
        if required_path is None:
            issues.append(f"{label} path is missing.")
        elif not required_path.exists():
            issues.append(f"{label} file was not found: {required_path}")

    if issues:
        return RawPrepDreamISPConsistencyFlow(
            flow_key=flow_key,
            status="missing",
            original_preview_path=str(original_preview_path) if original_preview_path is not None else None,
            render_state_path=str(render_state_path) if render_state_path is not None else None,
            plan_path=str(plan_path) if plan_path is not None else None,
            report_path=str(report_path) if report_path is not None else None,
            issues=issues,
            summary=f"DreamISP consistency evidence is incomplete for {flow_key}.",
        )

    assert original_preview_path is not None
    assert render_state_path is not None
    assert plan_path is not None
    assert report_path is not None

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report_payload, dict):
        raise ValueError(f"DreamISP report is invalid: {report_path}")

    rerender_plan = _prepare_rerender_plan(plan_path, render_state_path, rerender_root / flow_key)
    rerender_preview_path = Path(rerender_plan.render_preview_path or "")
    original_pixels = _load_rgb_pixels(original_preview_path)
    rerender_pixels = _load_rgb_pixels(rerender_preview_path)
    pixel_match = bool(np.array_equal(original_pixels, rerender_pixels))
    mean_luminance_original = _mean_luminance_from_pixels(original_pixels)
    mean_luminance_rerender = _mean_luminance_from_pixels(rerender_pixels)
    mean_luminance_delta = abs(mean_luminance_original - mean_luminance_rerender)

    source_stage = str(report_payload.get("source_stage") or "") or None
    source_item_key = str(report_payload.get("source_item_key") or "") or None
    backend = str(report_payload.get("render_backend") or "") or None
    source_kind = str(report_payload.get("render_source_kind") or "") or None
    render_state_summary = report_payload.get("render_state_summary") if isinstance(report_payload.get("render_state_summary"), dict) else {}
    state_payload = json.loads(render_state_path.read_text(encoding="utf-8"))

    checks = {
        "pixel_match": pixel_match,
        "mean_luminance_stable": mean_luminance_delta <= 1e-6,
        "scene_linear_source": source_kind == "scene_linear",
        "expected_backend": backend == "dreamisp_lite_preview_v1",
        "render_state_summary_matches": all(render_state_summary.get(key) == state_payload.get(key) for key in ("white_balance", "tone", "color", "detail")),
    }
    if not checks["pixel_match"]:
        issues.append("Rerendered editable preview differs from the recorded editable preview.")
    if not checks["mean_luminance_stable"]:
        issues.append("Mean luminance drifted after DreamISP rerender.")
    if not checks["scene_linear_source"]:
        issues.append("DreamISP render source_kind is not scene_linear.")
    if not checks["expected_backend"]:
        issues.append("DreamISP render backend is not dreamisp_lite_preview_v1.")
    if not checks["render_state_summary_matches"]:
        issues.append("DreamISP report render_state_summary does not match the editable render state.")

    status = "passed" if not issues else "partial"
    summary = (
        f"DreamISP rerender stayed pixel-identical for {flow_key}."
        if not issues
        else f"DreamISP rerender showed consistency drift for {flow_key}."
    )
    return RawPrepDreamISPConsistencyFlow(
        flow_key=flow_key,
        status=status,
        source_stage=source_stage,
        source_item_key=source_item_key,
        original_preview_path=str(original_preview_path),
        rerender_preview_path=str(rerender_preview_path),
        render_state_path=str(render_state_path),
        plan_path=str(plan_path),
        report_path=str(report_path),
        backend=backend,
        source_kind=source_kind,
        pixel_match=pixel_match,
        mean_luminance_original=mean_luminance_original,
        mean_luminance_rerender=mean_luminance_rerender,
        mean_luminance_delta=mean_luminance_delta,
        checks=checks,
        issues=issues,
        summary=summary,
    )


def build_rawprep_dreamisp_consistency(
    request: RawPrepDreamISPConsistencyRequest,
) -> RawPrepDreamISPConsistencyArtifact:
    local_e2e_smoke_path = _resolve_local_e2e_smoke_path(request)
    smoke_payload = _load_json_dict(local_e2e_smoke_path)

    blockers: list[str] = []
    recommended_actions: list[str] = []
    if smoke_payload is None:
        blockers.append("rawprep_local_e2e_smoke.json이 없어 DreamISP consistency를 판단할 수 없습니다.")
        recommended_actions.append("먼저 local E2E smoke를 다시 실행해 SingleRaw/TriRaw DreamISP handoff artifact를 남겨 주세요.")
        single_raw = RawPrepDreamISPConsistencyFlow(flow_key="single_raw")
        tri_raw = RawPrepDreamISPConsistencyFlow(flow_key="tri_raw")
        checks = {
            "local_e2e_passed": False,
            "single_raw_consistent": False,
            "tri_raw_consistent": False,
            "shared_backend_consistent": False,
            "scene_linear_master_preserved": False,
        }
        return RawPrepDreamISPConsistencyArtifact(
            output_dir=request.output_dir,
            output_root=request.output_root,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="missing_evidence",
            summary="DreamISP consistency를 판단할 local E2E smoke evidence가 아직 없습니다.",
            artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
            local_e2e_smoke_path=str(local_e2e_smoke_path),
            checks=checks,
            single_raw=single_raw,
            tri_raw=tri_raw,
            blockers=blockers,
            recommended_actions=recommended_actions,
            ok=False,
        )

    rerender_root = _resolve_output_dir(request.output_dir, output_root=request.output_root) / "_dreamisp_consistency"
    rerender_root.mkdir(parents=True, exist_ok=True)

    single_raw = _build_flow_consistency("single_raw", smoke_payload.get("single_raw", {}) or {}, rerender_root=rerender_root)
    tri_raw = _build_flow_consistency("tri_raw", smoke_payload.get("tri_raw", {}) or {}, rerender_root=rerender_root)

    local_e2e_passed = bool(smoke_payload.get("ok"))
    if not local_e2e_passed:
        blockers.append("DreamISP consistency는 local E2E smoke가 passed 상태일 때만 release 근거로 사용할 수 있습니다.")
    if single_raw.status != "passed":
        blockers.append("SingleRaw DreamISP rerender consistency가 아직 완전하지 않습니다.")
    if tri_raw.status != "passed":
        blockers.append("TriRaw DreamISP rerender consistency가 아직 완전하지 않습니다.")

    shared_backend_consistent = (
        single_raw.backend == "dreamisp_lite_preview_v1"
        and tri_raw.backend == "dreamisp_lite_preview_v1"
    )
    scene_linear_master_preserved = (
        single_raw.source_kind == "scene_linear"
        and tri_raw.source_kind == "scene_linear"
    )
    if not shared_backend_consistent:
        blockers.append("SingleRaw와 TriRaw가 같은 DreamISP backend로 렌더되지 않았습니다.")
    if not scene_linear_master_preserved:
        blockers.append("DreamISP rerender가 scene_linear master 기준으로 유지되지 않았습니다.")

    checks = {
        "local_e2e_passed": local_e2e_passed,
        "single_raw_consistent": single_raw.status == "passed",
        "tri_raw_consistent": tri_raw.status == "passed",
        "shared_backend_consistent": shared_backend_consistent,
        "scene_linear_master_preserved": scene_linear_master_preserved,
    }

    if blockers:
        status = "needs_tuning"
        summary = "DreamISP consistency evidence는 생겼지만 색/톤 일관성을 닫기엔 아직 보완이 필요합니다."
    else:
        status = "ready_for_consistent_tone"
        summary = "DreamISP-lite가 SingleRaw/TriRaw editable preview를 scene_linear 기준으로 재렌더해도 pixel drift 없이 같은 색/톤 결과를 유지했습니다."

    return RawPrepDreamISPConsistencyArtifact(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
        local_e2e_smoke_path=str(local_e2e_smoke_path),
        checks=checks,
        single_raw=single_raw,
        tri_raw=tri_raw,
        blockers=blockers,
        recommended_actions=recommended_actions,
        ok=not blockers,
    )


def write_rawprep_dreamisp_consistency(
    request: RawPrepDreamISPConsistencyRequest,
) -> RawPrepDreamISPConsistencyArtifact:
    artifact = build_rawprep_dreamisp_consistency(request)
    path = _artifact_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def load_rawprep_dreamisp_consistency(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepDreamISPConsistencyArtifact:
    path = _artifact_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"DreamISP consistency artifact was not found: {path}")
    return RawPrepDreamISPConsistencyArtifact(**json.loads(path.read_text(encoding="utf-8")))
