#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from release_bundle_lib import PROJECT_ROOT, build_release_bundle, human_size, load_manifest


def main() -> None:
    manifest = load_manifest()
    default_output = PROJECT_ROOT / "Product" / manifest.official_artifact_name

    parser = argparse.ArgumentParser(description="Build the official DreamCatcher RunPod release bundle.")
    parser.add_argument(
        "--output",
        default=str(default_output),
        help="Output zip path. Defaults to Product/DreamCatcher.zip.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    result = build_release_bundle(PROJECT_ROOT, manifest, output_path)

    print(f"Built release bundle: {result.artifact_path}")
    print(f"Artifact name: {result.artifact_name}")
    print(f"Bundle root: {result.bundle_root}/")
    print(f"Included files: {result.file_count}")
    print(f"Payload size: {human_size(result.total_bytes)}")


if __name__ == "__main__":
    main()
