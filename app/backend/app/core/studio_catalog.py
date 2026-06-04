from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .rawprep_contract import build_directory_layout
from .studio_paths import resolve_output_root


CatalogPickStatus = Literal["unreviewed", "selected", "rejected", "hold"]
CatalogReviewStatus = Literal[
    "intake",
    "culling",
    "proofing",
    "client_review",
    "print_ready",
    "delivered",
    "archived",
]


class StudioCatalogMetadata(BaseModel):
    session_id: str
    output_root: str
    rating: int = 0
    pick_status: CatalogPickStatus = "unreviewed"
    review_status: CatalogReviewStatus = "intake"
    color_tag: str | None = None
    keywords: list[str] = Field(default_factory=list)
    notes: str | None = None
    proofing_profile: str | None = None
    print_profile: str | None = None
    client_collection: str | None = None
    updated_at: str


class StudioCatalogUpdate(BaseModel):
    session_id: str
    output_root: str = "outputs"
    rating: int | None = None
    pick_status: CatalogPickStatus | None = None
    review_status: CatalogReviewStatus | None = None
    color_tag: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    proofing_profile: str | None = None
    print_profile: str | None = None
    client_collection: str | None = None


class StudioCatalogBatchUpdate(BaseModel):
    output_root: str = "outputs"
    session_ids: list[str] = Field(default_factory=list)
    rating: int | None = None
    pick_status: CatalogPickStatus | None = None
    review_status: CatalogReviewStatus | None = None
    color_tag: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    proofing_profile: str | None = None
    print_profile: str | None = None
    client_collection: str | None = None


class StudioCatalogSummary(BaseModel):
    rating: int = 0
    pick_status: CatalogPickStatus = "unreviewed"
    review_status: CatalogReviewStatus = "intake"
    color_tag: str | None = None
    keywords: list[str] = Field(default_factory=list)
    notes_preview: str | None = None
    proofing_profile: str | None = None
    print_profile: str | None = None
    client_collection: str | None = None
    updated_at: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_keywords(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized[:24]


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp_rating(value: int | None) -> int:
    if value is None:
        return 0
    return max(0, min(5, int(value)))


def summarize_catalog_notes(value: str | None, *, max_length: int = 120) -> str | None:
    text = _normalize_optional_text(value)
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def session_catalog_path(session_id: str, *, output_root: str = "outputs") -> Path:
    layout = build_directory_layout(output_root, session_id)
    session_root = Path(layout.session_root)
    if not session_root.exists() or not session_root.is_dir():
        raise FileNotFoundError(f"Studio session does not exist: {session_root}")
    return session_root / "session_catalog.json"


def _default_metadata(session_id: str, *, output_root: str) -> StudioCatalogMetadata:
    return StudioCatalogMetadata(
        session_id=session_id,
        output_root=str(resolve_output_root(output_root)),
        updated_at=utc_now_iso(),
    )


def load_session_catalog(session_id: str, *, output_root: str = "outputs") -> StudioCatalogMetadata:
    path = session_catalog_path(session_id, output_root=output_root)
    if not path.exists() or not path.is_file():
        return _default_metadata(session_id, output_root=output_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = StudioCatalogMetadata(**payload)
    except Exception:
        return _default_metadata(session_id, output_root=output_root)
    metadata.output_root = str(resolve_output_root(output_root))
    return metadata


def save_session_catalog(metadata: StudioCatalogMetadata) -> StudioCatalogMetadata:
    path = session_catalog_path(metadata.session_id, output_root=metadata.output_root)
    metadata.output_root = str(resolve_output_root(metadata.output_root))
    metadata.updated_at = utc_now_iso()
    path.write_text(json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def update_session_catalog(
    session_id: str,
    *,
    output_root: str = "outputs",
    rating: int | None = None,
    pick_status: CatalogPickStatus | None = None,
    review_status: CatalogReviewStatus | None = None,
    color_tag: str | None = None,
    keywords: list[str] | None = None,
    notes: str | None = None,
    proofing_profile: str | None = None,
    print_profile: str | None = None,
    client_collection: str | None = None,
) -> StudioCatalogMetadata:
    metadata = load_session_catalog(session_id, output_root=output_root)
    if rating is not None:
        metadata.rating = _clamp_rating(rating)
    if pick_status is not None:
        metadata.pick_status = pick_status
    if review_status is not None:
        metadata.review_status = review_status
    if color_tag is not None:
        metadata.color_tag = _normalize_optional_text(color_tag)
    if keywords is not None:
        metadata.keywords = _normalize_keywords(keywords)
    if notes is not None:
        metadata.notes = _normalize_optional_text(notes)
    if proofing_profile is not None:
        metadata.proofing_profile = _normalize_optional_text(proofing_profile)
    if print_profile is not None:
        metadata.print_profile = _normalize_optional_text(print_profile)
    if client_collection is not None:
        metadata.client_collection = _normalize_optional_text(client_collection)
    return save_session_catalog(metadata)


def batch_update_session_catalogs(
    session_ids: list[str],
    *,
    output_root: str = "outputs",
    rating: int | None = None,
    pick_status: CatalogPickStatus | None = None,
    review_status: CatalogReviewStatus | None = None,
    color_tag: str | None = None,
    keywords: list[str] | None = None,
    notes: str | None = None,
    proofing_profile: str | None = None,
    print_profile: str | None = None,
    client_collection: str | None = None,
) -> list[StudioCatalogMetadata]:
    updated: list[StudioCatalogMetadata] = []
    seen: set[str] = set()
    for session_id in session_ids:
        normalized = str(session_id).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        updated.append(
            update_session_catalog(
                normalized,
                output_root=output_root,
                rating=rating,
                pick_status=pick_status,
                review_status=review_status,
                color_tag=color_tag,
                keywords=keywords,
                notes=notes,
                proofing_profile=proofing_profile,
                print_profile=print_profile,
                client_collection=client_collection,
            )
        )
    return updated


def catalog_summary(metadata: StudioCatalogMetadata | None) -> StudioCatalogSummary:
    if metadata is None:
        return StudioCatalogSummary()
    return StudioCatalogSummary(
        rating=metadata.rating,
        pick_status=metadata.pick_status,
        review_status=metadata.review_status,
        color_tag=metadata.color_tag,
        keywords=list(metadata.keywords),
        notes_preview=summarize_catalog_notes(metadata.notes),
        proofing_profile=metadata.proofing_profile,
        print_profile=metadata.print_profile,
        client_collection=metadata.client_collection,
        updated_at=metadata.updated_at,
    )
