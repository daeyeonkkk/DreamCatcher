from __future__ import annotations

import json
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal

from PIL import Image
from pydantic import BaseModel, Field

from app.raw_engine_v2.isp.planner import (
    DreamISPHandoffPlan,
    build_dreamisp_handoff_plan,
    materialize_dreamisp_handoff_plan,
)
from app.raw_engine_v2.isp.runtime import materialize_dreamisp_lite_render
from app.raw_engine_v2.single_raw.planner import (
    SingleRawFoundationPlan,
    SingleRawModePreference,
    build_single_raw_foundation_plan,
    materialize_single_raw_foundation_plan,
)

from .rawprep_contract import (
    RawPrepBracketRequest,
    RawPrepJobRequest,
    RawPrepRestorationGoal,
    build_directory_layout,
    default_session_id,
)
from .raw_restoration_policy import DEFAULT_RAW_RESTORATION_GOAL
from .rawprep_runner import detect_rawprep_tools
from .studio_catalog import StudioCatalogSummary, catalog_summary, load_session_catalog
from .studio_paths import resolve_output_root


StudioEntryPreference = Literal["auto", "rawprep", "direct_edit"]
StudioEntryMode = Literal["rawprep_bracket", "direct_edit_raw", "direct_edit_image"]
StudioAssetKind = Literal["raw", "image", "unknown"]

RAW_SUFFIXES = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".erf",
    ".nef",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".sr2",
}

IMAGE_SUFFIXES = {
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
PREVIEWABLE_SUFFIXES = IMAGE_SUFFIXES


class StudioAsset(BaseModel):
    source_path: str
    staged_path: str
    file_name: str
    suffix: str
    kind: StudioAssetKind


class StudioIntakeRequest(BaseModel):
    session_id: str | None = None
    output_root: str = "outputs"
    asset_paths: List[str] = Field(..., min_length=1)
    entry_preference: StudioEntryPreference = "auto"
    camera_profile: str = "auto"
    quality_preset: Literal["safe", "balanced"] = "balanced"
    single_raw_mode_preference: SingleRawModePreference = "auto"
    restoration_goal: RawPrepRestorationGoal = DEFAULT_RAW_RESTORATION_GOAL


class StudioIntakePlan(BaseModel):
    session_id: str
    session_root: str
    manifest_path: str
    entry_mode: StudioEntryMode
    entry_preference: StudioEntryPreference
    rawprep_optional: bool
    alternate_modes: List[str] = Field(default_factory=list)
    staged_assets: List[StudioAsset] = Field(default_factory=list)
    editable_asset_path: str | None = None
    single_raw_plan: Dict[str, Any] | None = None
    dreamisp_plan: Dict[str, Any] | None = None
    rawprep_request: Dict[str, Any] | None = None
    notes: List[str] = Field(default_factory=list)


class StudioSessionSummary(BaseModel):
    session_id: str
    output_root: str
    session_root: str
    entry_mode: StudioEntryMode
    staged_asset_count: int
    primary_file_name: str | None = None
    editable_asset_path: str | None = None
    source_preview_path: str | None = None
    result_preview_path: str | None = None
    rawprep_job_id: str | None = None
    rawprep_status: str | None = None
    studio_job_id: str | None = None
    studio_status: str | None = None
    studio_current_step: str | None = None
    studio_tool: str | None = None
    prompt_preview: str | None = None
    catalog: StudioCatalogSummary = Field(default_factory=StudioCatalogSummary)
    last_updated_at: str


def dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_asset_kind(path: str | Path) -> StudioAssetKind:
    suffix = Path(path).suffix.lower()
    if suffix in RAW_SUFFIXES:
        return "raw"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    return "unknown"


def validate_asset_paths(asset_paths: List[str]) -> List[Path]:
    resolved: List[Path] = []
    for raw_path in asset_paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Input asset does not exist: {candidate}")
        resolved.append(candidate)
    return resolved


def discover_companion_raster(path: Path) -> Path | None:
    if classify_asset_kind(path) != "raw":
        return None
    for suffix in sorted(IMAGE_SUFFIXES):
        sibling = path.with_suffix(suffix)
        if sibling.is_file():
            return sibling
    return None


def normalize_intake_assets(assets: List[Path]) -> tuple[List[Path], Dict[str, Path], List[str]]:
    raw_assets = [asset for asset in assets if classify_asset_kind(asset) == "raw"]
    image_assets = [asset for asset in assets if classify_asset_kind(asset) == "image"]
    unknown_assets = [asset for asset in assets if classify_asset_kind(asset) == "unknown"]
    if unknown_assets:
        joined = ", ".join(asset.name for asset in unknown_assets)
        raise ValueError(f"DreamCatcher intake does not support these file types yet: {joined}")

    if not raw_assets:
        return image_assets, {}, []

    companions: Dict[str, Path] = {}
    extras: List[str] = []
    raw_keys = {asset.stem.lower() for asset in raw_assets}
    explicit_companion_count = 0
    sibling_companion_count = 0
    for image in image_assets:
        key = image.stem.lower()
        if key in raw_keys and key not in companions:
            companions[key] = image
            explicit_companion_count += 1
        else:
            extras.append(image.name)
    if extras:
        raise ValueError(
            "RAW와 함께 올린 래스터 파일은 같은 basename의 companion JPG/TIFF만 허용됩니다: "
            + ", ".join(extras)
        )
    for raw_asset in raw_assets:
        key = raw_asset.stem.lower()
        if key in companions:
            continue
        sibling = discover_companion_raster(raw_asset)
        if sibling is None:
            continue
        companions[key] = sibling
        sibling_companion_count += 1
    notes: List[str] = []
    if companions:
        if sibling_companion_count and explicit_companion_count:
            notes.append("RAW와 함께 전달된 companion raster를 우선 쓰고, 비어 있는 경우에는 같은 폴더의 sibling preview를 자동으로 연결합니다.")
        elif sibling_companion_count:
            notes.append("RAW와 같은 폴더의 sibling preview를 자동으로 찾아 직접 보정 기준 파일로 연결합니다.")
        else:
            notes.append("RAW와 같은 basename의 companion raster를 찾아 직접 보정 기준 파일로 사용합니다.")
        return raw_assets, companions, notes
    return raw_assets, companions, notes


def resolve_entry_mode(
    assets: List[Path],
    *,
    entry_preference: StudioEntryPreference,
) -> tuple[StudioEntryMode, bool, List[str], List[str]]:
    kinds = [classify_asset_kind(path) for path in assets]
    notes: List[str] = []

    if entry_preference == "rawprep":
        if len(assets) == 3 and all(kind == "raw" for kind in kinds):
            notes.append("3장 RAW 브라켓을 감지했습니다. DreamCatcher는 TriRaw 미리보기 런타임으로 먼저 진입하고, 직접 RAW 검토는 대체 경로로 남겨 둡니다.")
            return "rawprep_bracket", True, ["direct_edit_raw"], notes
        raise ValueError("TriRaw 진입은 RAW 파일 3장이 정확히 필요합니다.")

    if entry_preference == "direct_edit":
        if len(assets) == 1 and kinds[0] == "raw":
            return "direct_edit_raw", False, [], notes
        if len(assets) == 1 and kinds[0] == "image":
            return "direct_edit_image", False, [], notes
        if len(assets) == 3 and all(kind == "raw" for kind in kinds):
            notes.append("3장 RAW 브라켓은 TriRaw를 건너뛰고 가운데 RAW를 직접 검토용 대체 경로로 엽니다.")
            return "direct_edit_raw", True, ["rawprep_bracket"], notes
        raise ValueError("직접 보정은 현재 RAW 또는 이미지 1장, 혹은 직접 검토로 우회하는 3장 RAW 세트만 지원합니다.")

    if len(assets) == 3 and all(kind == "raw" for kind in kinds):
        notes.append("3장 RAW 브라켓을 감지했습니다. DreamCatcher는 TriRaw 미리보기 런타임으로 시작하고 직접 RAW 검토도 대체 경로로 남겨 둡니다.")
        return "rawprep_bracket", True, ["direct_edit_raw"], notes
    if len(assets) == 1 and kinds[0] == "raw":
        return "direct_edit_raw", False, [], notes
    if len(assets) == 1 and kinds[0] == "image":
        return "direct_edit_image", False, [], notes

    raise ValueError("DreamCatcher intake currently supports one RAW/image, or a three-RAW bracket set.")


def selected_direct_edit_index(assets: List[Path]) -> int:
    if len(assets) == 3:
        return 1
    return 0


def build_single_raw_intake_plan(
    assets: List[Path],
    staged_assets: List[StudioAsset],
    *,
    session_root: Path,
    entry_mode: StudioEntryMode,
    editable_asset_path: str | None,
    quality_preset: Literal["safe", "balanced"] = "balanced",
    single_raw_mode_preference: SingleRawModePreference = "auto",
) -> tuple[SingleRawFoundationPlan | None, str | None, List[str]]:
    if entry_mode != "direct_edit_raw" or not staged_assets:
        return None, editable_asset_path, []

    selected_index = selected_direct_edit_index(assets)
    if selected_index >= len(staged_assets):
        return None, editable_asset_path, []

    selected_staged = staged_assets[selected_index]
    if selected_staged.kind != "raw":
        return None, editable_asset_path, []

    foundation_plan = build_single_raw_foundation_plan(
        selected_staged.staged_path,
        session_root=session_root,
        quality_preset=quality_preset,
        mode_preference=single_raw_mode_preference,
    )
    notes = [
        "SingleRaw v2 foundation plan was generated for this direct RAW session.",
        f"DreamCatcher mapped the direct RAW quality preset '{quality_preset}' and mode preference '{single_raw_mode_preference}' to the SingleRaw {foundation_plan.resolved_mode} mode policy.",
    ]

    foundation_plan = materialize_single_raw_foundation_plan(
        foundation_plan,
        source_preview_path=editable_asset_path if editable_asset_path and is_previewable_path(editable_asset_path) else None,
    )
    notes.append("SingleRaw foundation manifest, report, diagnostics를 01_single_raw 아래에 기록했습니다.")

    if foundation_plan.materialized_preview_path:
        editable_asset_path = foundation_plan.materialized_preview_path
        notes.append("구조화된 SingleRaw 미리보기, report, diagnostics를 01_single_raw 아래에 실제 산출물로 만들었습니다.")

    localized_notes = [
        "이 direct RAW 세션용 SingleRaw v2 기본 계획을 만들었습니다.",
        f"직접 RAW 품질 프리셋 '{quality_preset}'와 모드 선택 '{single_raw_mode_preference}'를 SingleRaw {foundation_plan.resolved_mode} 모드 정책으로 연결했습니다.",
        "SingleRaw 기본 계획 manifest, report, diagnostics를 01_single_raw 아래에 기록했습니다.",
    ]
    if foundation_plan.materialized_preview_path:
        localized_notes.append("구조화된 SingleRaw 미리보기, report, diagnostics를 01_single_raw 아래 실제 산출물로 만들었습니다.")
    notes = localized_notes
    return foundation_plan, editable_asset_path, notes


def build_single_raw_dreamisp_plan(
    foundation_plan: SingleRawFoundationPlan | None,
    *,
    session_root: Path,
    editable_asset_path: str | None,
) -> tuple[DreamISPHandoffPlan | None, str | None, List[str]]:
    if foundation_plan is None:
        return None, editable_asset_path, []

    scene_linear_path = foundation_plan.scene_linear.get("materialized_path")
    if not isinstance(scene_linear_path, str) or not scene_linear_path.strip():
        return None, editable_asset_path, []
    if not Path(scene_linear_path).is_file():
        return None, editable_asset_path, []

    preview_path = first_previewable_path(foundation_plan.materialized_preview_path, editable_asset_path)
    dreamisp_plan = build_dreamisp_handoff_plan(
        session_root=session_root,
        source_stage="single_raw",
        source_item_key=foundation_plan.item_key,
        source_engine_key=foundation_plan.engine_key,
        source_engine_version=foundation_plan.engine_version,
        scene_linear_path=scene_linear_path,
        preview_path=preview_path,
        source_report_path=foundation_plan.report_path,
        source_diagnostics_manifest_path=foundation_plan.diagnostics_manifest_path,
    )
    dreamisp_plan = materialize_dreamisp_handoff_plan(dreamisp_plan)
    dreamisp_plan = materialize_dreamisp_lite_render(dreamisp_plan)

    next_editable_asset_path = editable_asset_path
    recommended_source_path = first_previewable_path(
        dreamisp_plan.render_preview_path,
        dreamisp_plan.recommended_editable_source_path,
        editable_asset_path,
    )
    if isinstance(recommended_source_path, str) and recommended_source_path.strip():
        next_editable_asset_path = recommended_source_path

    notes = [
        "DreamISP handoff plan, render state, report를 02_manual 아래에 기록했습니다.",
        "DreamISP-lite는 장면 선형 마스터를 건드리지 않고 02_manual 아래에 편집용 미리보기를 렌더했습니다.",
    ]
    notes = [
        "DreamISP handoff plan, render state, report를 02_manual 아래에 기록했습니다.",
        "DreamISP-lite가 장면 선형 마스터를 바탕으로 02_manual 아래 편집용 미리보기를 렌더했습니다.",
    ]
    return dreamisp_plan, next_editable_asset_path, notes


def stage_assets(
    assets: List[Path],
    *,
    layout_session_root: Path,
    input_dir: Path,
    entry_mode: StudioEntryMode,
    companion_assets: Dict[str, Path],
) -> List[StudioAsset]:
    staged_assets: List[StudioAsset] = []
    relative_dir = "bracket_01" if entry_mode == "rawprep_bracket" else "direct_edit"
    target_dir = input_dir / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    for source in assets:
        destination = target_dir / source.name
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        companion = companion_assets.get(source.stem.lower())
        if companion and companion.is_file():
            companion_destination = target_dir / companion.name
            if companion.resolve() != companion_destination.resolve():
                shutil.copy2(companion, companion_destination)
        staged_assets.append(
            StudioAsset(
                source_path=str(source),
                staged_path=str(destination),
                file_name=source.name,
                suffix=source.suffix.lower(),
                kind=classify_asset_kind(source),
            )
        )
    return staged_assets


def resolve_companion_raster(raw_asset: Path, companion_assets: Dict[str, Path]) -> Path | None:
    companion = companion_assets.get(raw_asset.stem.lower())
    if companion and companion.is_file():
        return companion
    return discover_companion_raster(raw_asset)


def extract_embedded_raw_preview(raw_path: Path, output_path: Path) -> Path | None:
    tool_status = detect_rawprep_tools(["exiftool"])
    exiftool = tool_status.get("exiftool")
    if not exiftool or not exiftool.available or not exiftool.resolved_path:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for tag in ("JpgFromRaw", "PreviewImage", "OtherImage", "ThumbnailImage"):
        try:
            result = subprocess.run(
                [str(exiftool.resolved_path), "-b", f"-{tag}", str(raw_path)],
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not result.stdout:
            continue
        output_path.write_bytes(result.stdout)
        try:
            with Image.open(output_path) as preview:
                preview.verify()
        except Exception:
            output_path.unlink(missing_ok=True)
            continue
        return output_path
    output_path.unlink(missing_ok=True)
    return None


def prepare_editable_asset(
    assets: List[Path],
    staged_assets: List[StudioAsset],
    *,
    input_dir: Path,
    companion_assets: Dict[str, Path],
) -> tuple[str | None, List[str]]:
    if not staged_assets:
        return None, []

    selected_index = selected_direct_edit_index(assets)
    selected_source = assets[selected_index]
    selected_staged = staged_assets[selected_index]
    if selected_staged.kind != "raw":
        return selected_staged.staged_path, []

    notes: List[str] = []
    proxy_dir = input_dir / "direct_edit_proxy"
    companion = resolve_companion_raster(selected_source, companion_assets)
    if companion:
        companion_target = proxy_dir / companion.name
        if companion.resolve() != companion_target.resolve():
            companion_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(companion, companion_target)
        notes.append("직접 보정 경로를 위해 RAW의 companion raster를 기준 소스로 준비했습니다.")
        return str(companion_target), notes

    extracted = extract_embedded_raw_preview(Path(selected_staged.staged_path), proxy_dir / f"{selected_source.stem}__embedded_preview.jpg")
    if extracted:
        notes.append("ExifTool로 RAW 내장 프리뷰를 추출해 직접 보정용 기준 소스를 준비했습니다.")
        return str(extracted), notes

    return selected_staged.staged_path, notes


def build_studio_intake_plan(request: StudioIntakeRequest) -> StudioIntakePlan:
    validated_assets = validate_asset_paths(request.asset_paths)
    assets, companion_assets, normalization_notes = normalize_intake_assets(validated_assets)
    session_id = request.session_id or default_session_id()
    layout = build_directory_layout(request.output_root, session_id)
    session_root = Path(layout.session_root)
    input_dir = Path(layout.input_dir)
    entry_mode, rawprep_optional, alternate_modes, notes = resolve_entry_mode(
        assets,
        entry_preference=request.entry_preference,
    )
    staged_assets = stage_assets(
        assets,
        layout_session_root=session_root,
        input_dir=input_dir,
        entry_mode=entry_mode,
        companion_assets=companion_assets,
    )

    editable_asset_path, editable_notes = prepare_editable_asset(
        assets,
        staged_assets,
        input_dir=input_dir,
        companion_assets=companion_assets,
    )
    single_raw_plan, editable_asset_path, single_raw_notes = build_single_raw_intake_plan(
        assets,
        staged_assets,
        session_root=session_root,
        entry_mode=entry_mode,
        editable_asset_path=editable_asset_path,
        quality_preset=request.quality_preset,
        single_raw_mode_preference=request.single_raw_mode_preference,
    )
    dreamisp_plan, editable_asset_path, dreamisp_notes = build_single_raw_dreamisp_plan(
        single_raw_plan,
        session_root=session_root,
        editable_asset_path=editable_asset_path,
    )
    notes = [*normalization_notes, *notes, *editable_notes, *single_raw_notes, *dreamisp_notes]

    rawprep_request = None
    if len(staged_assets) == 3 and all(asset.kind == "raw" for asset in staged_assets):
        rawprep_request = dump_model(
            RawPrepJobRequest(
                session_id=session_id,
                output_root=request.output_root,
                quality_preset=request.quality_preset,
                camera_profile=request.camera_profile,
                restoration_goal=request.restoration_goal,
                groups=[
                    RawPrepBracketRequest(
                        bracket_id="bracket_01",
                        raw_files=[asset.staged_path for asset in staged_assets],
                        reference_policy="auto",
                    )
                ],
            )
        )
        notes.append("TriRaw request contract was generated from the three-RAW bracket and is ready to run under rawprep.")

    manifest_path = session_root / "studio_intake.json"
    plan = StudioIntakePlan(
        session_id=session_id,
        session_root=str(session_root),
        manifest_path=str(manifest_path),
        entry_mode=entry_mode,
        entry_preference=request.entry_preference,
        rawprep_optional=rawprep_optional,
        alternate_modes=alternate_modes,
        staged_assets=staged_assets,
        editable_asset_path=editable_asset_path,
        single_raw_plan=dump_model(single_raw_plan) if single_raw_plan is not None else None,
        dreamisp_plan=dump_model(dreamisp_plan) if dreamisp_plan is not None else None,
        rawprep_request=rawprep_request,
        notes=notes,
    )
    write_json(manifest_path, dump_model(plan))
    return plan


def load_studio_intake_plan(session_id: str, *, output_root: str = "outputs") -> StudioIntakePlan:
    layout = build_directory_layout(output_root, session_id)
    manifest_path = Path(layout.session_root) / "studio_intake.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Studio intake manifest was not found: {manifest_path}")
    return StudioIntakePlan(**read_json(manifest_path))


def try_read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return read_json(path)
    except (json.JSONDecodeError, OSError):
        return None


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def is_previewable_path(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).suffix.lower() in PREVIEWABLE_SUFFIXES


def first_previewable_path(*paths: str | None) -> str | None:
    for path in paths:
        if is_previewable_path(path):
            return path
    return None


def summarize_prompt(value: Any, *, max_length: int = 96) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def rawprep_result_preview_path(payload: Dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    group_reports = payload.get("group_reports")
    if isinstance(group_reports, list):
        for report in group_reports:
            if not isinstance(report, dict):
                continue
            dreamisp_handoff = report.get("dreamisp_handoff")
            if not isinstance(dreamisp_handoff, dict):
                continue
            preview_path = first_previewable_path(
                dreamisp_handoff.get("render_preview_path"),
                dreamisp_handoff.get("recommended_editable_source_path"),
            )
            if preview_path:
                return preview_path

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list):
        artifact_paths: list[str | None] = []
        for kind in ("preview", "scene_linear"):
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                if artifact.get("kind") != kind:
                    continue
                if artifact.get("exists") is False:
                    continue
                artifact_paths.append(artifact.get("path"))
        preview_path = first_previewable_path(*artifact_paths)
        if preview_path:
            return preview_path

    if isinstance(group_reports, list):
        for report in group_reports:
            if not isinstance(report, dict):
                continue
            preview_path = first_previewable_path(report.get("recommended_artifact"))
            if preview_path:
                return preview_path
    return None


def latest_studio_output_preview_path(payload: Dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        return None
    for output in reversed(outputs):
        if not isinstance(output, dict):
            continue
        preview_path = first_previewable_path(output.get("path"))
        if preview_path:
            return preview_path
    return None


def latest_studio_job_payload(session_root: Path) -> tuple[Dict[str, Any] | None, Path | None]:
    jobs_root = session_root / "03_ai" / "jobs"
    if not jobs_root.exists():
        return None, None

    candidates = sorted(
        jobs_root.glob("*/studio_job.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for candidate in candidates:
        payload = try_read_json(candidate)
        if isinstance(payload, dict):
            return payload, candidate
    return None, None


def list_recent_studio_sessions(output_root: str = "outputs", *, limit: int = 8) -> List[StudioSessionSummary]:
    root = resolve_output_root(output_root)
    if not root.exists() or not root.is_dir():
        return []

    summaries: list[tuple[int, StudioSessionSummary]] = []
    for manifest_path in root.glob("*/studio_intake.json"):
        payload = try_read_json(manifest_path)
        if not isinstance(payload, dict):
            continue
        try:
            plan = StudioIntakePlan(**payload)
        except Exception:
            continue

        session_root = manifest_path.parent
        rawprep_path = session_root / "rawprep_job.json"
        rawprep_payload = try_read_json(rawprep_path)
        studio_payload, studio_path = latest_studio_job_payload(session_root)
        try:
            session_catalog = load_session_catalog(plan.session_id, output_root=str(root))
        except FileNotFoundError:
            session_catalog = None
        source_preview_path = first_previewable_path(
            plan.editable_asset_path,
            *(asset.staged_path for asset in plan.staged_assets),
        )
        result_preview_path = first_previewable_path(
            latest_studio_output_preview_path(studio_payload),
            rawprep_result_preview_path(rawprep_payload),
        )

        timestamps = [manifest_path.stat().st_mtime]
        if rawprep_path.exists():
            timestamps.append(rawprep_path.stat().st_mtime)
        if studio_path and studio_path.exists():
            timestamps.append(studio_path.stat().st_mtime)
        last_updated = max(timestamps)

        summaries.append(
            (
                int(last_updated * 1_000_000),
                StudioSessionSummary(
                    session_id=plan.session_id,
                    output_root=str(root),
                    session_root=str(session_root),
                    entry_mode=plan.entry_mode,
                    staged_asset_count=len(plan.staged_assets),
                    primary_file_name=plan.staged_assets[0].file_name if plan.staged_assets else None,
                    editable_asset_path=plan.editable_asset_path,
                    source_preview_path=source_preview_path,
                    result_preview_path=result_preview_path,
                    rawprep_job_id=rawprep_payload.get("job_id") if isinstance(rawprep_payload, dict) else None,
                    rawprep_status=rawprep_payload.get("status") if isinstance(rawprep_payload, dict) else None,
                    studio_job_id=studio_payload.get("job_id") if isinstance(studio_payload, dict) else None,
                    studio_status=studio_payload.get("status") if isinstance(studio_payload, dict) else None,
                    studio_current_step=studio_payload.get("current_step") if isinstance(studio_payload, dict) else None,
                    studio_tool=studio_payload.get("tool") if isinstance(studio_payload, dict) else None,
                    prompt_preview=summarize_prompt(studio_payload.get("prompt")) if isinstance(studio_payload, dict) else None,
                    catalog=catalog_summary(session_catalog),
                    last_updated_at=iso_from_timestamp(last_updated),
                ),
            )
        )

    summaries.sort(key=lambda item: item[0], reverse=True)
    return [summary for _, summary in summaries[: max(1, limit)]]
