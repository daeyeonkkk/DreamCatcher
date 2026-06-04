import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNPOD_ROOT = PROJECT_ROOT / "runpod"
if str(RUNPOD_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNPOD_ROOT))

from release_bundle_lib import Manifest, build_release_bundle_preflight_report  # noqa: E402


def _write_minimal_release_tree(root: Path) -> None:
    (root / "PROJECT_FOUNDATION").mkdir(parents=True, exist_ok=True)
    (root / "Product").mkdir(parents=True, exist_ok=True)
    (root / "runpod").mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_FOUNDATION" / "README.md").write_text("# Foundation\n", encoding="utf-8")
    (root / "Product" / "README.md").write_text("# Product\n", encoding="utf-8")
    (root / "runpod" / "bootstrap.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "README.md").write_text("# DreamCatcher\n", encoding="utf-8")


def _minimal_manifest(*, require_missing_path: bool = False) -> Manifest:
    required_paths = [
        "PROJECT_FOUNDATION/README.md",
        "Product/README.md",
        "runpod/bootstrap.sh",
        "README.md",
    ]
    if require_missing_path:
        required_paths.append("Product/BUILD_MANUAL.md")
    return Manifest(
        official_artifact_name="DreamCatcher.zip",
        bundle_root="DreamCatcher",
        compatible_workspace_inputs=("DreamCatcher", "DreamCatcher.zip"),
        include_roots=("PROJECT_FOUNDATION", "Product", "runpod", "README.md"),
        required_paths=tuple(required_paths),
        forbidden_globs=("**/__pycache__/**", "**/*.pyc", "DreamCatcher.zip", "Product/DreamCatcher.zip"),
    )


def test_release_bundle_preflight_builds_and_verifies_zip(tmp_path):
    _write_minimal_release_tree(tmp_path)
    manifest = _minimal_manifest()

    report = build_release_bundle_preflight_report(tmp_path, manifest, tmp_path / "DreamCatcher.zip")

    assert report["ok"] is True
    assert report["artifact_path"].endswith("DreamCatcher.zip")
    assert Path(report["artifact_path"]).exists()
    assert report["build"]["file_count"] == 4
    assert report["source_verification"]["ok"] is True
    assert report["zip_verification"]["ok"] is True


def test_release_bundle_preflight_surfaces_missing_required_paths(tmp_path):
    _write_minimal_release_tree(tmp_path)
    manifest = _minimal_manifest(require_missing_path=True)

    report = build_release_bundle_preflight_report(tmp_path, manifest, tmp_path / "DreamCatcher.zip")

    assert report["ok"] is False
    assert "Product/BUILD_MANUAL.md" in report["source_verification"]["missing_paths"]
    assert "Product/BUILD_MANUAL.md" in report["zip_verification"]["missing_paths"]
