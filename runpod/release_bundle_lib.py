from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = SCRIPT_DIR / "release_bundle_manifest.json"


@dataclass(frozen=True)
class Manifest:
    official_artifact_name: str
    bundle_root: str
    compatible_workspace_inputs: tuple[str, ...]
    include_roots: tuple[str, ...]
    required_paths: tuple[str, ...]
    forbidden_globs: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    subject: str
    file_count: int
    total_bytes: int
    missing_paths: tuple[str, ...]
    forbidden_hits: tuple[str, ...]
    placeholder_workflows: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_paths and not self.forbidden_hits and not self.placeholder_workflows


@dataclass(frozen=True)
class BuildResult:
    artifact_path: str
    artifact_name: str
    bundle_root: str
    file_count: int
    total_bytes: int


def load_manifest(path: Path = MANIFEST_PATH) -> Manifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Manifest(
        official_artifact_name=data["official_artifact_name"],
        bundle_root=data["bundle_root"],
        compatible_workspace_inputs=tuple(data["compatible_workspace_inputs"]),
        include_roots=tuple(data["include_roots"]),
        required_paths=tuple(data["required_paths"]),
        forbidden_globs=tuple(data["forbidden_globs"]),
    )


def normalize_relpath(path: Path | str) -> str:
    if isinstance(path, Path):
        rel = path.as_posix()
    else:
        rel = path.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    while rel.startswith("/"):
        rel = rel[1:]
    return rel


def matches_glob(relpath: str, patterns: Iterable[str]) -> bool:
    relpath = normalize_relpath(relpath)
    return any(fnmatch.fnmatch(relpath, pattern) for pattern in patterns)


def iter_release_files(project_root: Path, manifest: Manifest) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    for include_root in manifest.include_roots:
        target = project_root / include_root
        if not target.exists():
            raise FileNotFoundError(f"required include root missing: {include_root}")

        if target.is_file():
            rel = normalize_relpath(target.relative_to(project_root))
            if rel not in seen and not matches_glob(rel, manifest.forbidden_globs):
                files.append(target)
                seen.add(rel)
            continue

        for child in sorted(target.rglob("*")):
            if not child.is_file():
                continue
            rel = normalize_relpath(child.relative_to(project_root))
            if rel in seen or matches_glob(rel, manifest.forbidden_globs):
                continue
            files.append(child)
            seen.add(rel)

    return sorted(files, key=lambda item: normalize_relpath(item.relative_to(project_root)))


def build_release_bundle(project_root: Path, manifest: Manifest, output_path: Path) -> BuildResult:
    files = iter_release_files(project_root, manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in files:
            rel = normalize_relpath(file_path.relative_to(project_root))
            archive.write(file_path, arcname=zip_entry_name(manifest, rel))
            file_count += 1
            total_bytes += file_path.stat().st_size

    return BuildResult(
        artifact_path=str(output_path.resolve()),
        artifact_name=manifest.official_artifact_name,
        bundle_root=manifest.bundle_root,
        file_count=file_count,
        total_bytes=total_bytes,
    )


def zip_entry_name(manifest: Manifest, relative_path: str) -> str:
    return f"{manifest.bundle_root}/{normalize_relpath(relative_path)}"


def strip_bundle_root(entry_name: str, bundle_root: str) -> str:
    entry_name = normalize_relpath(entry_name)
    prefix = f"{bundle_root}/"
    if not entry_name.startswith(prefix):
        raise ValueError(f"zip entry is outside bundle root: {entry_name}")
    rel = entry_name[len(prefix) :]
    parts = PurePosixPath(rel).parts
    if any(part in {"..", ""} for part in parts):
        raise ValueError(f"unsafe zip entry path: {entry_name}")
    return rel


def placeholder_workflows_from_reader(read_text: callable, required_paths: Iterable[str]) -> list[str]:
    placeholders: list[str] = []
    for relpath in required_paths:
        if not relpath.startswith("seed_bundle/api_workflows/"):
            continue
        try:
            data = json.loads(read_text(relpath))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("_placeholder"):
            placeholders.append(relpath)
    return placeholders


def verify_folder(project_root: Path, manifest: Manifest, artifact_root: Path) -> VerificationResult:
    root = artifact_root.resolve()
    relpaths: list[str] = []
    total_bytes = 0

    for file_path in iter_release_files(root, manifest):
        rel = normalize_relpath(file_path.relative_to(root))
        relpaths.append(rel)
        total_bytes += file_path.stat().st_size

    relset = set(relpaths)
    missing = sorted(path for path in manifest.required_paths if path not in relset)
    forbidden = sorted(path for path in relpaths if matches_glob(path, manifest.forbidden_globs))

    def read_text(relpath: str) -> str:
        return (root / relpath).read_text(encoding="utf-8")

    placeholders = placeholder_workflows_from_reader(read_text, manifest.required_paths)
    return VerificationResult(
        subject=str(root),
        file_count=len(relpaths),
        total_bytes=total_bytes,
        missing_paths=tuple(missing),
        forbidden_hits=tuple(forbidden),
        placeholder_workflows=tuple(sorted(placeholders)),
    )


def verify_zip(zip_path: Path, manifest: Manifest) -> VerificationResult:
    relpaths: list[str] = []
    total_bytes = 0

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            rel = strip_bundle_root(info.filename, manifest.bundle_root)
            relpaths.append(rel)
            total_bytes += info.file_size

        relset = set(relpaths)
        missing = sorted(path for path in manifest.required_paths if path not in relset)
        forbidden = sorted(path for path in relpaths if matches_glob(path, manifest.forbidden_globs))

        def read_text(relpath: str) -> str:
            entry_name = zip_entry_name(manifest, relpath)
            return archive.read(entry_name).decode("utf-8")

        placeholders = placeholder_workflows_from_reader(read_text, manifest.required_paths)

    return VerificationResult(
        subject=str(zip_path.resolve()),
        file_count=len(relpaths),
        total_bytes=total_bytes,
        missing_paths=tuple(missing),
        forbidden_hits=tuple(forbidden),
        placeholder_workflows=tuple(sorted(placeholders)),
    )


def verification_payload(result: VerificationResult) -> dict[str, Any]:
    return {
        "subject": result.subject,
        "file_count": result.file_count,
        "total_bytes": result.total_bytes,
        "missing_paths": list(result.missing_paths),
        "forbidden_hits": list(result.forbidden_hits),
        "placeholder_workflows": list(result.placeholder_workflows),
        "ok": result.ok,
    }


def build_release_bundle_preflight_report(project_root: Path, manifest: Manifest, output_path: Path) -> dict[str, Any]:
    build_result = build_release_bundle(project_root, manifest, output_path)
    source_result = verify_folder(project_root, manifest, project_root)
    zip_result = verify_zip(output_path, manifest)
    ok = source_result.ok and zip_result.ok
    summary = (
        "Release bundle preflight passed."
        if ok
        else "Release bundle preflight failed. Review missing paths, forbidden files, or placeholder workflows."
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root.resolve()),
        "artifact_path": build_result.artifact_path,
        "official_artifact_name": build_result.artifact_name,
        "bundle_root": build_result.bundle_root,
        "build": {
            "file_count": build_result.file_count,
            "total_bytes": build_result.total_bytes,
        },
        "source_verification": verification_payload(source_result),
        "zip_verification": verification_payload(zip_result),
        "ok": ok,
        "summary": summary,
    }


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"
