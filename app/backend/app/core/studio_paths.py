from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_output_root(output_root: str | Path) -> Path:
    candidate = Path(output_root).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root() / candidate
    return candidate.resolve()


def resolve_output_path(path: str | Path, *, output_root: str | Path) -> Path:
    root = resolve_output_root(output_root)
    raw = Path(path).expanduser()
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        for candidate in (repo_root() / raw, root / raw):
            if candidate not in candidates:
                candidates.append(candidate)

    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    raise ValueError("Studio file path must stay inside the configured output root.")
