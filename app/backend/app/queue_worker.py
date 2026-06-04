from __future__ import annotations

import argparse

from .core.studio_queue import external_worker_output_roots, run_external_worker_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DreamCatcher durable queue worker")
    parser.add_argument(
        "--output-root",
        action="append",
        dest="output_roots",
        help="Output root to watch for queued jobs. Repeat to watch multiple roots.",
    )
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between queue polls.")
    parser.add_argument("--once", action="store_true", help="Process the current queue once and exit.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_roots = args.output_roots or external_worker_output_roots("outputs")
    run_external_worker_service(
        output_roots,
        poll_interval_seconds=max(0.25, float(args.poll_interval)),
        once=bool(args.once),
    )


if __name__ == "__main__":
    main()
