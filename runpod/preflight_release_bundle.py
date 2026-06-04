#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_bundle_lib import PROJECT_ROOT, build_release_bundle_preflight_report, load_manifest


def main() -> None:
    manifest = load_manifest()
    default_output = PROJECT_ROOT / "Product" / manifest.official_artifact_name

    parser = argparse.ArgumentParser(
        description="Build Product/DreamCatcher.zip and verify both the source tree and the zip artifact in one preflight pass."
    )
    parser.add_argument(
        "--output",
        default=str(default_output),
        help="Output zip path. Defaults to Product/DreamCatcher.zip.",
    )
    parser.add_argument(
        "--report-out",
        help="Optional JSON path for the structured preflight report. Use this only when you intentionally want a temporary verification artifact.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    report = build_release_bundle_preflight_report(PROJECT_ROOT, manifest, output_path)
    payload = json.dumps(report, indent=2, ensure_ascii=False)

    if args.report_out:
        report_path = Path(args.report_out).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")

    print(payload)
    if not bool(report.get("ok")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
