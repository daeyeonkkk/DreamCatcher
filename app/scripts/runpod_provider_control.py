from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_backend_import_path() -> None:
    backend_root = project_root() / "app" / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


ensure_backend_import_path()

from app.core.runpod_provider import (  # noqa: E402
    RunPodProviderError,
    load_runpod_provider_config,
    provider_runtime_summary,
    start_provider_pod,
    stop_provider_pod,
    wait_for_backend_health,
    wait_for_provider_control_state,
)

RECOVERY_PRESETS = [
    "review_pack",
    "client_delivery",
    "master_archive",
    "proofing_sheet",
    "print_master",
    "client_review_portal",
]


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def backend_base_url(explicit_url: str | None = None) -> str | None:
    if explicit_url:
        return explicit_url.rstrip("/")
    summary = provider_runtime_summary()
    if summary.backend_url:
        return summary.backend_url.rstrip("/")
    config = load_runpod_provider_config()
    if config.backend_url:
        return config.backend_url.rstrip("/")
    return None


def call_backend(path: str, *, method: str = "GET", payload: dict | None = None, base_url: str | None = None) -> dict:
    target_base = backend_base_url(base_url)
    if not target_base:
        raise SystemExit("Backend URL is not configured. Set RUNPOD_BACKEND_URL or expose the backend port on RunPod.")
    response = requests.request(
        method,
        f"{target_base}{path}",
        json=payload,
        timeout=30.0,
        headers={"Content-Type": "application/json"},
    )
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = None
        detail = body.get("detail") if isinstance(body, dict) else response.text
        raise SystemExit(f"Backend request failed: {detail or response.reason}")
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def command_status(_args: argparse.Namespace) -> int:
    print_json(provider_runtime_summary().model_dump())
    return 0


def ensure_provider_running(*, wait_seconds: float, poll_seconds: float):
    summary = provider_runtime_summary()
    if summary.control_state not in {"running", "starting"}:
        start_provider_pod()
    summary = wait_for_provider_control_state(
        {"running"},
        timeout_seconds=wait_seconds,
        poll_interval_seconds=poll_seconds,
    )
    if summary.control_state != "running":
        raise SystemExit(f"Pod did not reach running state in time. Last state: {summary.control_state}")
    return summary


def command_start(args: argparse.Namespace) -> int:
    summary = ensure_provider_running(
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
    )
    print_json(summary.model_dump())
    return 0


def command_stop(_args: argparse.Namespace) -> int:
    stop_provider_pod()
    print_json(provider_runtime_summary().model_dump())
    return 0


def command_resume(args: argparse.Namespace) -> int:
    ensure_provider_running(
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
    )
    if not wait_for_backend_health(
        timeout_seconds=args.wait_seconds,
        poll_interval_seconds=args.poll_seconds,
    ):
        raise SystemExit("Backend health did not become ready in time after the pod started.")
    payload = call_backend(
        "/api/studio/ops/provider/resume",
        method="POST",
        payload={
            "output_root": args.output_root,
            "worker_mode": args.worker_mode,
            "poll_interval_seconds": args.worker_poll_seconds,
        },
        base_url=args.backend_url,
    )
    print_json(payload)
    return 0


def command_pause(args: argparse.Namespace) -> int:
    payload = call_backend(
        "/api/studio/ops/provider/pause",
        method="POST",
        payload={
            "output_root": args.output_root,
            "reason": args.reason,
            "worker_mode": args.worker_mode,
            "poll_interval_seconds": args.worker_poll_seconds,
            "drain_timeout_seconds": args.drain_timeout_seconds,
            "stop_provider": True,
            "recovery_session_id": args.session_id,
            "recovery_preset": args.recovery_preset,
            "require_recovery_ready": bool(args.session_id) and not args.skip_recovery_check,
            "create_recovery_package": bool(args.session_id) and not args.skip_recovery_check,
        },
        base_url=args.backend_url,
    )
    print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control DreamCatcher RunPod provider lifecycle from the local workspace.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show the current RunPod provider + checkpoint summary.")
    status_parser.set_defaults(func=command_status)

    start_parser = subparsers.add_parser("start", help="Start the configured RunPod pod and wait for it to run.")
    start_parser.add_argument("--wait-seconds", type=float, default=240.0)
    start_parser.add_argument("--poll-seconds", type=float, default=5.0)
    start_parser.set_defaults(func=command_start)

    stop_parser = subparsers.add_parser("stop", help="Stop the configured RunPod pod immediately.")
    stop_parser.set_defaults(func=command_stop)

    resume_parser = subparsers.add_parser("resume", help="Start the pod, wait for backend health, then resume the checkpointed studio queues.")
    resume_parser.add_argument("--backend-url", default=None, help="Override the public backend base URL.")
    resume_parser.add_argument("--output-root", default="outputs")
    resume_parser.add_argument("--worker-mode", choices=["external", "embedded"], default="external")
    resume_parser.add_argument("--worker-poll-seconds", type=float, default=2.0)
    resume_parser.add_argument("--wait-seconds", type=float, default=240.0)
    resume_parser.add_argument("--poll-seconds", type=float, default=5.0)
    resume_parser.set_defaults(func=command_resume)

    pause_parser = subparsers.add_parser("pause", help="Checkpoint the current session through the backend and stop the pod.")
    pause_parser.add_argument("--backend-url", default=None, help="Override the public backend base URL.")
    pause_parser.add_argument("--output-root", default="outputs")
    pause_parser.add_argument("--reason", default="provider pause requested from local control script")
    pause_parser.add_argument("--worker-mode", choices=["external", "embedded"], default="external")
    pause_parser.add_argument("--worker-poll-seconds", type=float, default=2.0)
    pause_parser.add_argument("--drain-timeout-seconds", type=float, default=12.0)
    pause_parser.add_argument("--session-id", default=None, help="When set, build a recovery packet before stopping the pod.")
    pause_parser.add_argument("--recovery-preset", choices=RECOVERY_PRESETS, default="master_archive")
    pause_parser.add_argument("--skip-recovery-check", action="store_true", help="Pause without building or requiring a recovery packet.")
    pause_parser.set_defaults(func=command_pause)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except RunPodProviderError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
