from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .studio_paths import repo_root, resolve_output_root


class RawPrepBenchmarkRunPodSmokeRequest(BaseModel):
    output_dir: str
    output_root: str = "outputs"


class RawPrepBenchmarkRunPodSmokeIssue(BaseModel):
    severity: str = "error"
    code: str
    message: str
    path: str | None = None


class RawPrepBenchmarkRunPodSmokeEvidence(BaseModel):
    output_dir: str
    output_root: str
    generated_at: str
    ok: bool = False
    status: str = "missing"
    summary: str
    smoke_path: str | None = None
    runtime_dir: str | None = None
    bootstrap_summary_path: str | None = None
    rawprep_healthcheck_path: str | None = None
    single_raw_healthcheck_path: str | None = None
    required_checks: dict[str, bool] = Field(default_factory=dict)
    rawprep_healthcheck_ok: bool | None = None
    single_raw_healthcheck_ok: bool | None = None
    preferred_single_raw_backend: str | None = None
    single_raw_sample_smoke_status: str = "missing"
    single_raw_sample_raw_path: str | None = None
    single_raw_sample_preview_path: str | None = None
    single_raw_sample_scene_linear_path: str | None = None
    blockers: list[RawPrepBenchmarkRunPodSmokeIssue] = Field(default_factory=list)
    warnings: list[RawPrepBenchmarkRunPodSmokeIssue] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def _runtime_dir() -> Path:
    return repo_root() / "app" / "runtime"


def _resolve_smoke_output_dir(output_dir: str, *, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    candidate = Path(output_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Benchmark RunPod smoke output_dir must stay inside the configured output root.") from exc
    return resolved


def _smoke_path(output_dir: str, *, output_root: str) -> Path:
    return _resolve_smoke_output_dir(output_dir, output_root=output_root) / "rawprep_runpod_smoke.json"


def _append_issue(
    issues: list[RawPrepBenchmarkRunPodSmokeIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    issues.append(
        RawPrepBenchmarkRunPodSmokeIssue(
            severity=severity,
            code=code,
            message=message,
            path=path,
        )
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at: {path}")
    return payload


def build_rawprep_benchmark_runpod_smoke(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkRunPodSmokeEvidence:
    blockers: list[RawPrepBenchmarkRunPodSmokeIssue] = []
    warnings: list[RawPrepBenchmarkRunPodSmokeIssue] = []
    recommended_actions: list[str] = []

    runtime_dir = _runtime_dir()
    bootstrap_summary_path = runtime_dir / "bootstrap_summary.json"
    rawprep_healthcheck_path = runtime_dir / "rawprep_healthcheck.json"
    single_raw_healthcheck_path = runtime_dir / "single_raw_healthcheck.json"

    bootstrap_summary = _load_optional_json(bootstrap_summary_path)
    rawprep_healthcheck = _load_optional_json(rawprep_healthcheck_path)
    single_raw_healthcheck = _load_optional_json(single_raw_healthcheck_path)

    if bootstrap_summary is None:
        _append_issue(
            blockers,
            severity="error",
            code="runpod_bootstrap_summary_missing",
            message="RunPod bootstrap_summary.json evidence is missing.",
            path=str(bootstrap_summary_path),
        )
    if rawprep_healthcheck is None:
        _append_issue(
            blockers,
            severity="error",
            code="runpod_rawprep_healthcheck_missing",
            message="RunPod rawprep_healthcheck.json evidence is missing.",
            path=str(rawprep_healthcheck_path),
        )
    if single_raw_healthcheck is None:
        _append_issue(
            blockers,
            severity="error",
            code="runpod_single_raw_healthcheck_missing",
            message="RunPod single_raw_healthcheck.json evidence is missing.",
            path=str(single_raw_healthcheck_path),
        )

    checks = bootstrap_summary.get("checks", {}) if isinstance(bootstrap_summary, dict) else {}
    required_check_messages = {
        "comfy_ready": "ComfyUI was not marked ready in bootstrap_summary.json.",
        "backend_ready": "backend was not marked ready in bootstrap_summary.json.",
        "runtime_workflows_present": "runtime workflow files were not present during RunPod smoke.",
        "rawprep_healthcheck_present": "rawprep_healthcheck.json was not present during RunPod smoke.",
        "single_raw_healthcheck_present": "single_raw_healthcheck.json was not present during RunPod smoke.",
        "single_raw_runtime_ready": "SingleRaw runtime was not marked ready during RunPod smoke.",
    }
    required_checks = {key: bool(checks.get(key)) for key in required_check_messages}
    for key, message in required_check_messages.items():
        if bootstrap_summary is not None and not bool(checks.get(key)):
            _append_issue(
                blockers,
                severity="error",
                code=f"runpod_{key}_failed",
                message=message,
                path=str(bootstrap_summary_path),
            )

    rawprep_healthcheck_ok = rawprep_healthcheck.get("ok") if rawprep_healthcheck is not None else None
    single_raw_healthcheck_ok = single_raw_healthcheck.get("ok") if single_raw_healthcheck is not None else None
    preferred_single_raw_backend = (
        str(single_raw_healthcheck.get("preferred_backend"))
        if single_raw_healthcheck is not None and single_raw_healthcheck.get("preferred_backend") is not None
        else None
    )
    single_raw_sample_raw_path = (
        str(single_raw_healthcheck.get("sample_raw_path"))
        if single_raw_healthcheck is not None and single_raw_healthcheck.get("sample_raw_path")
        else None
    )
    single_raw_sample_decode_ok = (
        bool(single_raw_healthcheck.get("sample_decode_ok"))
        if single_raw_healthcheck is not None and single_raw_healthcheck.get("sample_decode_ok") is not None
        else None
    )
    sample_result = single_raw_healthcheck.get("sample_result") if isinstance(single_raw_healthcheck, dict) else None
    single_raw_sample_preview_path = (
        str(sample_result.get("preview_path"))
        if isinstance(sample_result, dict) and sample_result.get("preview_path")
        else None
    )
    single_raw_sample_scene_linear_path = (
        str(sample_result.get("scene_linear_path"))
        if isinstance(sample_result, dict) and sample_result.get("scene_linear_path")
        else None
    )
    single_raw_sample_smoke_status = "missing"

    if single_raw_healthcheck is not None and not bool(single_raw_healthcheck_ok):
        _append_issue(
            blockers,
            severity="error",
            code="runpod_single_raw_healthcheck_not_ok",
            message="SingleRaw smoke evidence exists but reports ok=false.",
            path=str(single_raw_healthcheck_path),
        )

    if single_raw_healthcheck is not None and single_raw_healthcheck_ok is True:
        if not single_raw_sample_raw_path:
            _append_issue(
                blockers,
                severity="error",
                code="runpod_single_raw_sample_smoke_missing",
                message="single_raw_healthcheck.json does not include a sample RAW decode smoke result yet.",
                path=str(single_raw_healthcheck_path),
            )
            single_raw_sample_smoke_status = "missing"
        elif single_raw_sample_decode_ok:
            single_raw_sample_smoke_status = "passed"
        else:
            _append_issue(
                blockers,
                severity="error",
                code="runpod_single_raw_sample_smoke_failed",
                message="single_raw_healthcheck.json includes a sample RAW smoke result, but the decode did not complete successfully.",
                path=str(single_raw_healthcheck_path),
            )
            single_raw_sample_smoke_status = "failed"

    if rawprep_healthcheck is not None and not bool(rawprep_healthcheck_ok):
        _append_issue(
            warnings,
            severity="warning",
            code="runpod_rawprep_healthcheck_not_ok",
            message="rawprep healthcheck reports ok=false; bootstrap may still be acceptable if the missing tool reason is expected.",
            path=str(rawprep_healthcheck_path),
        )

    missing_codes = {
        "runpod_bootstrap_summary_missing",
        "runpod_rawprep_healthcheck_missing",
        "runpod_single_raw_healthcheck_missing",
    }
    if blockers:
        blocker_codes = {issue.code for issue in blockers}
        if blocker_codes and blocker_codes.issubset({"runpod_single_raw_sample_smoke_missing"}):
            status = "bootstrap_only"
            summary = "RunPod bootstrap evidence is present, but the sample RAW decode smoke required by BUILD_MANUAL is still missing."
            recommended_actions.append(
                "Run single_raw_healthcheck.py on RunPod with --sample-raw and keep the updated single_raw_healthcheck.json so the smoke artifact moves from bootstrap_only to passed."
            )
        elif blocker_codes and blocker_codes.issubset(missing_codes):
            status = "missing"
            summary = "RunPod smoke evidence is missing required bootstrap files."
            recommended_actions.append(
                "Run BUILD_MANUAL smoke on RunPod and keep bootstrap_summary.json, rawprep_healthcheck.json, single_raw_healthcheck.json as release evidence."
            )
        else:
            status = "failed"
            summary = "RunPod smoke evidence exists, but one or more required checks failed."
            recommended_actions.append(
                "Fix the failing RunPod bootstrap or sample RAW smoke checks, then regenerate bootstrap_summary.json, rawprep_healthcheck.json, and single_raw_healthcheck.json."
            )
    else:
        status = "passed"
        summary = "RunPod smoke evidence is present and passes bootstrap plus sample RAW decode checks."
        recommended_actions.append("Write rawprep_runpod_smoke.json into the benchmark output directory so release evidence stays with the measured run.")

    return RawPrepBenchmarkRunPodSmokeEvidence(
        output_dir=output_dir,
        output_root=output_root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ok=not blockers,
        status=status,
        summary=summary,
        smoke_path=str(_smoke_path(output_dir, output_root=output_root)),
        runtime_dir=str(runtime_dir),
        bootstrap_summary_path=str(bootstrap_summary_path),
        rawprep_healthcheck_path=str(rawprep_healthcheck_path),
        single_raw_healthcheck_path=str(single_raw_healthcheck_path),
        required_checks=required_checks,
        rawprep_healthcheck_ok=bool(rawprep_healthcheck_ok) if rawprep_healthcheck is not None else None,
        single_raw_healthcheck_ok=bool(single_raw_healthcheck_ok) if single_raw_healthcheck is not None else None,
        preferred_single_raw_backend=preferred_single_raw_backend,
        single_raw_sample_smoke_status=single_raw_sample_smoke_status,
        single_raw_sample_raw_path=single_raw_sample_raw_path,
        single_raw_sample_preview_path=single_raw_sample_preview_path,
        single_raw_sample_scene_linear_path=single_raw_sample_scene_linear_path,
        blockers=blockers,
        warnings=warnings,
        recommended_actions=recommended_actions,
    )


def write_rawprep_benchmark_runpod_smoke(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkRunPodSmokeEvidence:
    smoke = build_rawprep_benchmark_runpod_smoke(output_dir, output_root=output_root)
    path = _smoke_path(output_dir, output_root=output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(smoke.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return smoke


def load_rawprep_benchmark_runpod_smoke(output_dir: str, *, output_root: str = "outputs") -> RawPrepBenchmarkRunPodSmokeEvidence:
    path = _smoke_path(output_dir, output_root=output_root)
    if not path.exists():
        raise FileNotFoundError(f"Rawprep benchmark RunPod smoke artifact was not found: {path}")
    return RawPrepBenchmarkRunPodSmokeEvidence(**json.loads(path.read_text(encoding="utf-8")))
