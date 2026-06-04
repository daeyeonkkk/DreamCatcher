from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel

from .rawprep_contract import build_directory_layout
from .recipe_router import normalize_tool_key
from .studio_compare_advisor import rounded_compare_metrics, sample_image_metrics
from .studio_files import resolve_output_target
from .studio_paths import resolve_output_root


CompareWinnerRole = Literal["select", "candidate"]
CompareDecisionAction = Literal["keep_select", "accept_candidate", "manual"]
COMPARE_DECISION_PREFIX = "compare_decision_"
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompareDecisionRecord(BaseModel):
    decision_id: str
    occurred_at: str
    session_id: str
    output_root: str
    tool: str
    action: CompareDecisionAction = "manual"
    note: str | None = None
    select_path: str
    candidate_path: str
    winner_path: str
    loser_path: str
    winner_role: CompareWinnerRole
    select_metrics: dict[str, float]
    candidate_metrics: dict[str, float]
    winner_metrics: dict[str, float]
    loser_metrics: dict[str, float]
    winner_delta_vs_loser: dict[str, float]


def compare_decision_directory(session_id: str, *, output_root: str) -> Path:
    layout = build_directory_layout(output_root, session_id)
    directory = Path(layout.session_root) / "04_compare" / "decisions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def compare_decision_aggregate_path(*, output_root: str) -> Path:
    root = resolve_output_root(output_root)
    directory = root / "_compare_learning"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "compare_decisions.jsonl"


def build_compare_decision_record(
    *,
    session_id: str,
    output_root: str,
    tool: str,
    select_path: str,
    candidate_path: str,
    winner_path: str,
    action: CompareDecisionAction = "manual",
    note: str | None = None,
) -> CompareDecisionRecord:
    select_target = resolve_output_target(select_path, output_root=output_root)
    candidate_target = resolve_output_target(candidate_path, output_root=output_root)
    winner_target = resolve_output_target(winner_path, output_root=output_root)
    normalized_tool = normalize_tool_key(tool)

    if winner_target == select_target:
        winner_role: CompareWinnerRole = "select"
        loser_target = candidate_target
    elif winner_target == candidate_target:
        winner_role = "candidate"
        loser_target = select_target
    else:
        raise ValueError("winner_path must match either the Select or Candidate path.")

    select_metrics = sample_image_metrics(select_target)
    candidate_metrics = sample_image_metrics(candidate_target)
    winner_metrics = select_metrics if winner_role == "select" else candidate_metrics
    loser_metrics = candidate_metrics if winner_role == "select" else select_metrics
    occurred_at = utc_now_iso()
    decision_id = f"cmp_{occurred_at.replace(':', '').replace('-', '').replace('.', '')}_{winner_role}"
    winner_delta_vs_loser = {
        key: round(float(winner_metrics[key]) - float(loser_metrics[key]), 6)
        for key in winner_metrics
    }

    return CompareDecisionRecord(
        decision_id=decision_id,
        occurred_at=occurred_at,
        session_id=session_id,
        output_root=str(resolve_output_root(output_root)),
        tool=normalized_tool,
        action=action,
        note=(str(note).strip() or None) if note else None,
        select_path=str(select_target),
        candidate_path=str(candidate_target),
        winner_path=str(winner_target),
        loser_path=str(loser_target),
        winner_role=winner_role,
        select_metrics=rounded_compare_metrics(select_metrics),
        candidate_metrics=rounded_compare_metrics(candidate_metrics),
        winner_metrics=rounded_compare_metrics(winner_metrics),
        loser_metrics=rounded_compare_metrics(loser_metrics),
        winner_delta_vs_loser=winner_delta_vs_loser,
    )


def save_compare_decision(record: CompareDecisionRecord) -> CompareDecisionRecord:
    directory = compare_decision_directory(record.session_id, output_root=record.output_root)
    file_path = directory / f"{COMPARE_DECISION_PREFIX}{record.decision_id}.json"
    file_path.write_text(
        json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    aggregate_path = compare_decision_aggregate_path(output_root=record.output_root)
    with aggregate_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
    return record


def record_compare_decision(
    *,
    session_id: str,
    output_root: str,
    tool: str,
    select_path: str,
    candidate_path: str,
    winner_path: str,
    action: CompareDecisionAction = "manual",
    note: str | None = None,
) -> CompareDecisionRecord:
    record = build_compare_decision_record(
        session_id=session_id,
        output_root=output_root,
        tool=tool,
        select_path=select_path,
        candidate_path=candidate_path,
        winner_path=winner_path,
        action=action,
        note=note,
    )
    return save_compare_decision(record)


def _iter_compare_decision_files(roots: Iterable[str | Path]) -> Iterable[Path]:
    for root in roots:
        candidate = Path(root)
        if candidate.is_file() and candidate.name.startswith(COMPARE_DECISION_PREFIX) and candidate.suffix == ".json":
            yield candidate
            continue
        if not candidate.exists() or not candidate.is_dir():
            continue
        for current_root, dir_names, file_names in os.walk(candidate, onerror=lambda _exc: None):
            dir_names[:] = [
                item
                for item in dir_names
                if item not in SKIP_DIR_NAMES and not item.startswith(".tmp")
            ]
            current_path = Path(current_root)
            for file_name in file_names:
                if file_name.startswith(COMPARE_DECISION_PREFIX) and file_name.endswith(".json"):
                    yield current_path / file_name


def collect_compare_decisions(roots: Iterable[str | Path]) -> tuple[list[CompareDecisionRecord], dict[str, Any]]:
    items: list[CompareDecisionRecord] = []
    seen_ids: set[str] = set()
    discovered_files = 0
    duplicates = 0
    skipped: list[dict[str, str]] = []

    for path in _iter_compare_decision_files(roots):
        discovered_files += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = CompareDecisionRecord(**payload)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"path": str(path), "error": str(exc)})
            continue
        if record.decision_id in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(record.decision_id)
        items.append(record)

    summary = {
        "discovered_files": discovered_files,
        "unique_decisions": len(items),
        "duplicate_files": duplicates,
        "skipped_files": skipped,
        "tool_counts": _count_by(items, "tool"),
        "winner_role_counts": _count_by(items, "winner_role"),
    }
    return items, summary


def _count_by(items: Iterable[CompareDecisionRecord], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(getattr(item, field_name, "") or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts
