#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from release_bundle_lib import VerificationResult, human_size, load_manifest, verify_folder, verify_zip


def print_result(result: VerificationResult) -> None:
    print(f"Verified: {result.subject}")
    print(f"Files: {result.file_count}")
    print(f"Payload size: {human_size(result.total_bytes)}")

    if result.missing_paths:
        print("Missing required paths:")
        for path in result.missing_paths:
            print(f" - {path}")

    if result.forbidden_hits:
        print("Forbidden paths found:")
        for path in result.forbidden_hits:
            print(f" - {path}")

    if result.placeholder_workflows:
        print("Placeholder API workflows found:")
        for path in result.placeholder_workflows:
            print(f" - {path}")

    if result.ok:
        print("Release bundle verification passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a DreamCatcher RunPod release folder or zip artifact.")
    parser.add_argument("--artifact", required=True, help="Path to the project folder or the release zip.")
    args = parser.parse_args()

    manifest = load_manifest()
    artifact = Path(args.artifact).expanduser().resolve()
    if not artifact.exists():
        raise SystemExit(f"Artifact not found: {artifact}")

    if artifact.is_dir():
        result = verify_folder(artifact, manifest, artifact)
    elif artifact.suffix.lower() == ".zip":
        result = verify_zip(artifact, manifest)
    else:
        raise SystemExit("Artifact must be a directory or a .zip file.")

    print_result(result)
    if not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
