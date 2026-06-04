from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_paths import repo_root, resolve_output_root


class RawPrepSingleRawDecodeReadinessRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"
    single_raw_healthcheck_path: str | None = None


class RawPrepSingleRawDecodeReadinessChecks(BaseModel):
    runtime_modules_ready: bool = False
    sensor_decode_supported: bool = False
    sample_decode_ok: bool = False
    sample_raw_recorded: bool = False
    preview_artifacts_available: bool = False
    editable_artifacts_available: bool = False


class RawPrepSingleRawDecodeReadinessArtifact(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    status: str = "missing_evidence"
    summary: str
    artifact_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    preferred_backend: str | None = None
    sample_raw_path: str | None = None
    runtime_profile: str | None = None
    scene_linear_format: str | None = None
    required_modules: dict[str, bool] = Field(default_factory=dict)
    checks: RawPrepSingleRawDecodeReadinessChecks
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
        raise ValueError("SingleRaw decode readiness output_dir must stay inside the configured output root.") from exc
    return resolved


def _artifact_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_output_dir(output_dir, output_root=output_root) / "rawprep_single_raw_decode_readiness.json"


def _resolve_healthcheck_path(request: RawPrepSingleRawDecodeReadinessRequest) -> Path:
    if request.single_raw_healthcheck_path:
        candidate = Path(request.single_raw_healthcheck_path)
        return candidate.resolve() if candidate.is_absolute() else (repo_root() / candidate).resolve()
    return (repo_root() / "app" / "runtime" / "single_raw_healthcheck.json").resolve()


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def build_rawprep_single_raw_decode_readiness(
    request: RawPrepSingleRawDecodeReadinessRequest,
) -> RawPrepSingleRawDecodeReadinessArtifact:
    healthcheck_path = _resolve_healthcheck_path(request)
    payload = _load_json_dict(healthcheck_path)

    blockers: list[str] = []
    recommended_actions: list[str] = []

    if payload is None:
        blockers.append("single_raw_healthcheck.json이 없어 SingleRaw decode readiness를 판단할 수 없습니다.")
        recommended_actions.append("RunPod에서 single_raw_healthcheck.py sample decode smoke를 다시 실행해 JSON evidence를 남겨 주세요.")
        return RawPrepSingleRawDecodeReadinessArtifact(
            output_dir=request.output_dir,
            output_root=request.output_root,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="missing_evidence",
            summary="SingleRaw decode readiness를 판단할 healthcheck evidence가 아직 없습니다.",
            artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
            single_raw_healthcheck_path=str(healthcheck_path),
            checks=RawPrepSingleRawDecodeReadinessChecks(),
            blockers=blockers,
            recommended_actions=recommended_actions,
            ok=False,
        )

    sample_result = payload.get("sample_result") if isinstance(payload.get("sample_result"), dict) else {}
    required_modules = {
        str(key): bool(value)
        for key, value in (payload.get("required_modules", {}) or {}).items()
    }
    sample_raw_path = str(payload.get("sample_raw_path") or "") or None
    preferred_backend = str(payload.get("preferred_backend") or "") or None
    runtime_profile = str(sample_result.get("runtime_profile") or "") or None
    input_preview_path = str(sample_result.get("input_preview_path") or "") or None
    preview_path = str(sample_result.get("preview_path") or "") or None
    scene_linear_path = str(sample_result.get("scene_linear_path") or "") or None
    scene_linear_format = str(sample_result.get("scene_linear_format") or "") or None

    checks = RawPrepSingleRawDecodeReadinessChecks(
        runtime_modules_ready=bool(required_modules) and all(required_modules.values()),
        sensor_decode_supported=bool(payload.get("supports_sensor_decode")),
        sample_decode_ok=bool(payload.get("sample_decode_ok")),
        sample_raw_recorded=bool(sample_raw_path),
        preview_artifacts_available=bool(input_preview_path and preview_path),
        editable_artifacts_available=bool(preview_path and scene_linear_path),
    )

    if not checks.runtime_modules_ready:
        blockers.append("SingleRaw sensor decode runtime module 준비가 아직 완전하지 않습니다.")
    if not checks.sensor_decode_supported:
        blockers.append("SingleRaw sensor decode backend가 아직 지원 상태로 올라오지 않았습니다.")
    if not checks.sample_decode_ok:
        blockers.append("RunPod sample RAW decode smoke가 아직 성공 상태가 아닙니다.")
    if not checks.sample_raw_recorded:
        blockers.append("sample_raw_path가 남지 않아 어떤 RAW로 decode smoke를 통과했는지 확인할 수 없습니다.")
    if not checks.preview_artifacts_available:
        blockers.append("decode 기준 input preview와 preview output artifact가 함께 남지 않았습니다.")
    if not checks.editable_artifacts_available:
        blockers.append("preview 또는 scene_linear artifact가 없어 후속 DreamISP handoff 증거가 부족합니다.")
    if scene_linear_format and scene_linear_format.lower() != "tiff":
        blockers.append("scene_linear output format이 기대 형식(tiff)과 다릅니다.")

    if blockers:
        status = "needs_tuning"
        summary = "SingleRaw decode evidence는 있지만 3.1을 닫기에는 아직 누락된 조건이 있습니다."
    else:
        status = "ready_for_sensor_decode"
        summary = (
            f"SingleRaw sensor decode가 RunPod sample RAW `{sample_raw_path}`에서 "
            f"`{preferred_backend}` backend와 `{runtime_profile}` profile로 실제 통과했습니다."
        )

    return RawPrepSingleRawDecodeReadinessArtifact(
        output_dir=request.output_dir,
        output_root=request.output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        summary=summary,
        artifact_path=str(_artifact_path(request.output_dir, output_root=request.output_root)),
        single_raw_healthcheck_path=str(healthcheck_path),
        preferred_backend=preferred_backend,
        sample_raw_path=sample_raw_path,
        runtime_profile=runtime_profile,
        scene_linear_format=scene_linear_format,
        required_modules=required_modules,
        checks=checks,
        blockers=blockers,
        recommended_actions=recommended_actions,
        ok=not blockers,
    )


def write_rawprep_single_raw_decode_readiness(
    request: RawPrepSingleRawDecodeReadinessRequest,
) -> RawPrepSingleRawDecodeReadinessArtifact:
    artifact = build_rawprep_single_raw_decode_readiness(request)
    path = _artifact_path(request.output_dir, output_root=request.output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def load_rawprep_single_raw_decode_readiness(
    output_dir: str,
    *,
    output_root: str = "outputs",
) -> RawPrepSingleRawDecodeReadinessArtifact:
    path = _artifact_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"SingleRaw decode readiness artifact was not found: {path}")
    return RawPrepSingleRawDecodeReadinessArtifact(**json.loads(path.read_text(encoding="utf-8")))
