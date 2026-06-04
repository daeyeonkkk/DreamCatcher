from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import yaml


def run(cmd: list[str], cwd: str | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def repo_dir_from_url(repo: str) -> str:
    name = repo.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def ensure_repo(repo_url: str, ref: str, target_dir: Path) -> None:
    git_dir = target_dir / ".git"
    if git_dir.exists():
        run(["git", "fetch", "--all", "--tags"], cwd=str(target_dir))
    else:
        if target_dir.exists() and not git_dir.exists():
            shutil.rmtree(target_dir)
        run(["git", "clone", repo_url, str(target_dir)])

    if ref:
        run(["git", "checkout", ref], cwd=str(target_dir))
        try:
            run(["git", "pull", "--ff-only"], cwd=str(target_dir))
        except Exception:
            pass
    else:
        print(f"INFO: {target_dir.name} has no pinned ref yet; using current remote default branch.")


def maybe_install_requirements(target_dir: Path, python_bin: str) -> None:
    req = target_dir / "requirements.txt"
    if req.exists():
        run([python_bin, "-m", "pip", "install", "-r", str(req)])


def install_from_manifest(manifest_path: str, comfy_root: str, python_bin: str) -> None:
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    comfy_root_path = Path(comfy_root)
    custom_nodes_dir = comfy_root_path / "custom_nodes"
    custom_nodes_dir.mkdir(parents=True, exist_ok=True)

    core = manifest.get("comfy_core")
    if core:
        if (comfy_root_path / "main.py").exists():
            print(f"INFO: Using existing ComfyUI root at {comfy_root_path}; skipping comfy_core repo management.")
        else:
            ensure_repo(core["repo"], core.get("ref", ""), comfy_root_path)

    for item in manifest.get("custom_nodes", []):
        target_dir = custom_nodes_dir / repo_dir_from_url(item["repo"])
        ensure_repo(item["repo"], item.get("ref", ""), target_dir)
        if "pip" in item.get("install", ""):
            maybe_install_requirements(target_dir, python_bin=python_bin)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install pinned custom nodes for DreamCatcher.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--python-bin", default="python")
    args = parser.parse_args()
    install_from_manifest(args.manifest, args.comfy_root, args.python_bin)


if __name__ == "__main__":
    main()
