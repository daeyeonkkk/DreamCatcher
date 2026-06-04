from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Dict, List
from uuid import uuid4

from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from .comfy_client import ComfyClient
from .rawprep_contract import build_directory_layout, default_session_id
from .recipe_router import choose_recipe, is_ai_capable_tool, normalize_tool_key
from .studio_edit_linkage import build_or_update_session_edit_linkage
from .studio_paths import resolve_output_path, resolve_output_root as shared_resolve_output_root


PREVIEWABLE_SUFFIXES = {".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
DEFAULT_COMFY_READINESS_TTL_SECONDS = 5.0
EXPAND_CANVAS_HORIZONTAL_RATIO = 0.16
EXPAND_CANVAS_VERTICAL_RATIO = 0.16
EXPAND_CANVAS_MIN_HORIZONTAL_MARGIN = 96
EXPAND_CANVAS_MIN_VERTICAL_MARGIN = 72
EXPAND_CANVAS_MAX_HORIZONTAL_MARGIN = 640
EXPAND_CANVAS_MAX_VERTICAL_MARGIN = 512
_comfy_readiness_cache: Dict[str, tuple[float, bool, str | None]] = {}


class StudioJobRequest(BaseModel):
    tool: str
    seed_root: str | None = None
    session_id: str | None = None
    output_root: str = "outputs"
    source_path: str | None = None
    prompt: str | None = None


class StudioJobOutput(BaseModel):
    label: str
    path: str
    origin: str
    kind: str = "image"
    linked_mask_path: str | None = None
    alpha_extracted: bool = False


class StudioJobRecord(BaseModel):
    job_id: str
    recipe_id: str | None = None
    selection_profile: str | None = None
    session_id: str
    tool: str
    output_root: str
    session_root: str
    job_root: str
    execution_engine: str = "comfy-workflow"
    workflow_source: str
    workflow_path: str
    model_family: str | None = None
    maturity: str | None = None
    license: str | None = None
    workflow_exists: bool
    execution_ready: bool = False
    availability_error: str | None = None
    prompt: str | None = None
    source_path: str | None = None
    prepared_input_path: str | None = None
    prepared_workflow_path: str | None = None
    comfy_prompt_id: str | None = None
    status: str
    current_step: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    warm_models: List[str] = Field(default_factory=list)
    cold_models: List[str] = Field(default_factory=list)
    watch_models: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    public_priors: List[Dict[str, Any]] = Field(default_factory=list)
    bootstrap_rules: List[str] = Field(default_factory=list)
    community_takeaways: List[str] = Field(default_factory=list)
    runtime_prior_bundle: Dict[str, Any] | None = None
    runtime_prior_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    frontier_dataset_activation: Dict[str, Any] | None = None
    frontier_dataset_items: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    outputs: List[StudioJobOutput] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def app_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_seed_root(seed_root: str | None) -> Path:
    if seed_root:
        candidate = Path(seed_root)
        if not candidate.is_absolute():
            candidate = app_root().parent / seed_root
        return candidate.resolve()
    return (app_root().parent / "seed_bundle").resolve()


def resolve_output_root(output_root: str) -> Path:
    return shared_resolve_output_root(output_root)


def ensure_session_source(path: str, *, output_root: Path) -> Path:
    try:
        target = resolve_output_path(path, output_root=output_root)
    except ValueError as exc:
        raise ValueError("Studio job source must stay inside the configured output root.") from exc
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Studio job source does not exist: {target}")
    if target.suffix.lower() not in PREVIEWABLE_SUFFIXES:
        raise ValueError("Studio AI jobs currently require a raster source such as TIFF, JPG, PNG, or WebP.")
    return target


def comfy_root() -> Path | None:
    env_root = os.getenv("COMFY_ROOT")
    if env_root and Path(env_root).joinpath("main.py").exists():
        return Path(env_root).resolve()
    for candidate in (Path("/workspace/runpod-slim/ComfyUI"), Path("/workspace/ComfyUI")):
        if candidate.joinpath("main.py").exists():
            return candidate.resolve()
    return None


def comfy_input_dir() -> Path | None:
    env_dir = os.getenv("COMFY_INPUT_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    root = comfy_root()
    return root / "input" if root else None


def comfy_output_dir() -> Path | None:
    env_dir = os.getenv("COMFY_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    root = comfy_root()
    return root / "output" if root else None


def comfy_base_url() -> str:
    return os.getenv("COMFY_URL", "http://127.0.0.1:8188")


def comfy_readiness_cache_ttl_seconds() -> float:
    raw_value = os.getenv("DREAMCATCHER_COMFY_READINESS_TTL_SECONDS")
    if raw_value is None:
        return DEFAULT_COMFY_READINESS_TTL_SECONDS
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_COMFY_READINESS_TTL_SECONDS


def clear_comfy_readiness_cache(base_url: str | None = None) -> None:
    if base_url is None:
        _comfy_readiness_cache.clear()
        return
    _comfy_readiness_cache.pop(base_url, None)


def check_comfy_readiness(*, base_url: str, use_cache: bool = True) -> tuple[bool, str | None]:
    ttl_seconds = comfy_readiness_cache_ttl_seconds()
    cache_entry = _comfy_readiness_cache.get(base_url)
    now = monotonic()
    if (
        use_cache
        and ttl_seconds > 0
        and cache_entry is not None
        and now - cache_entry[0] < ttl_seconds
    ):
        return cache_entry[1], cache_entry[2]

    try:
        client = ComfyClient(base_url)
        client.system_stats()
    except Exception:
        result = (False, f"AI 백엔드가 아직 준비되지 않았습니다. {base_url}의 ComfyUI를 먼저 켜 주세요.")
    else:
        result = (True, None)

    _comfy_readiness_cache[base_url] = (now, result[0], result[1])
    return result


def job_root_for(session_root: Path, job_id: str) -> Path:
    return session_root / "03_ai" / "jobs" / job_id


def record_path_for(job_root: Path) -> Path:
    return job_root / "studio_job.json"


def index_path_for(output_root: Path) -> Path:
    return output_root / "studio_job_index.json"


def save_job_record(record: StudioJobRecord) -> None:
    record.updated_at = utc_now_iso()
    output_root = resolve_output_root(record.output_root)
    job_root = resolve_output_path(record.job_root, output_root=output_root)
    job_root.mkdir(parents=True, exist_ok=True)
    record_path = record_path_for(job_root)
    record_path.write_text(json.dumps(dump_model(record), ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = index_path_for(output_root)
    index_payload: Dict[str, Dict[str, str]] = {}
    if index_path.exists():
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    index_payload[record.job_id] = {
        "session_id": record.session_id,
        "session_root": record.session_root,
        "job_root": record.job_root,
        "state_path": str(record_path),
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_job_error(record: StudioJobRecord, message: str, *, current_step: str = "error") -> StudioJobRecord:
    record.status = "error"
    record.current_step = current_step
    record.error = message
    record.finished_at = utc_now_iso()
    save_job_record(record)
    return record


def mark_job_cancelled(record: StudioJobRecord, *, note: str | None = None) -> StudioJobRecord:
    record.status = "cancelled"
    record.current_step = "cancelled"
    record.error = None
    record.finished_at = utc_now_iso()
    if note:
        record.notes.append(note)
    save_job_record(record)
    return record


def load_job_record(job_id: str, *, output_root: str) -> StudioJobRecord:
    output_root_path = resolve_output_root(output_root)
    index_path = index_path_for(output_root_path)
    if not index_path.exists():
        raise FileNotFoundError(f"Studio job index was not found under: {output_root_path}")
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    job_payload = index_payload.get(job_id)
    if not job_payload:
        raise FileNotFoundError(f"Studio job was not found: {job_id}")
    state_path = resolve_output_path(job_payload["state_path"], output_root=output_root_path)
    if not state_path.exists():
        raise FileNotFoundError(f"Studio job state file is missing: {state_path}")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["output_root"] = str(resolve_output_root(payload.get("output_root", str(output_root_path))))
    for key in ("session_root", "job_root", "prepared_input_path", "prepared_workflow_path", "source_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = str(resolve_output_path(value, output_root=payload["output_root"]))
    outputs = payload.get("outputs")
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, dict):
                path = output.get("path")
                if isinstance(path, str) and path.strip():
                    output["path"] = str(resolve_output_path(path, output_root=payload["output_root"]))
    return StudioJobRecord(**payload)


def build_job_record(request: StudioJobRequest) -> StudioJobRecord:
    seed_root = resolve_seed_root(request.seed_root)
    recipe = choose_recipe(request.tool, seed_root=str(seed_root))
    session_id = request.session_id or default_session_id()
    output_root = resolve_output_root(request.output_root)
    layout = build_directory_layout(str(output_root), session_id)
    session_root = Path(layout.session_root).resolve()
    job_id = str(uuid4())
    job_root = job_root_for(session_root, job_id)
    notes = [recipe.notes]
    if request.source_path:
        notes.append("Studio job uses the current editable raster source as the ComfyUI input image.")
    if recipe.bootstrap_rules:
        notes.extend(recipe.bootstrap_rules)
    record = StudioJobRecord(
        job_id=job_id,
        recipe_id=recipe.recipe_id,
        selection_profile=recipe.selection_profile,
        session_id=session_id,
        tool=request.tool,
        output_root=str(output_root),
        session_root=str(session_root),
        job_root=str(job_root),
        execution_engine=recipe.execution_engine,
        workflow_source=recipe.workflow_source,
        workflow_path=recipe.workflow_path,
        model_family=recipe.model_family,
        maturity=recipe.maturity,
        license=recipe.license,
        workflow_exists=Path(recipe.workflow_path).exists(),
        prompt=request.prompt,
        source_path=request.source_path,
        status="planned",
        current_step="planned",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        warm_models=recipe.warm_models,
        cold_models=recipe.cold_models,
        watch_models=recipe.watch_models,
        references=recipe.references,
        public_priors=recipe.public_priors,
        bootstrap_rules=recipe.bootstrap_rules,
        community_takeaways=recipe.community_takeaways,
        runtime_prior_bundle=recipe.runtime_prior_bundle,
        runtime_prior_artifacts=recipe.runtime_prior_artifacts,
        frontier_dataset_activation=recipe.frontier_dataset_activation,
        frontier_dataset_items=recipe.frontier_dataset_items,
        notes=notes,
    )
    return assess_job_readiness(record)


def assess_job_readiness(record: StudioJobRecord, *, use_cache: bool = True) -> StudioJobRecord:
    normalized_tool = record.tool.strip()
    if not is_ai_capable_tool(normalized_tool):
        record.execution_ready = False
        record.availability_error = "이 도구는 검토 또는 출력 단계이므로 ComfyUI 작업을 제출하지 않습니다."
        return record
    if not record.workflow_exists:
        record.execution_ready = False
        record.availability_error = f"워크플로 파일이 없습니다: {record.workflow_path}"
        return record
    ready, availability_error = check_comfy_readiness(base_url=comfy_base_url(), use_cache=use_cache)
    if not ready:
        record.execution_ready = False
        record.availability_error = availability_error
        return record
    record.execution_ready = True
    record.availability_error = None
    return record


def append_job_note(record: StudioJobRecord, note: str) -> None:
    if note not in record.notes:
        record.notes.append(note)


def effective_prompt_text(record: StudioJobRecord) -> str:
    prompt_text = (record.prompt or "").strip()
    if prompt_text:
        return prompt_text
    if normalize_tool_key(record.tool) == "expandCanvas":
        return "Extend the existing photo naturally beyond the current frame while preserving the subject, lighting, perspective, and edge continuity."
    return ""


def build_expand_canvas_plan(*, width: int, height: int) -> Dict[str, Any]:
    horizontal_margin = min(
        EXPAND_CANVAS_MAX_HORIZONTAL_MARGIN,
        max(EXPAND_CANVAS_MIN_HORIZONTAL_MARGIN, int(round(width * EXPAND_CANVAS_HORIZONTAL_RATIO))),
    )
    vertical_margin = min(
        EXPAND_CANVAS_MAX_VERTICAL_MARGIN,
        max(EXPAND_CANVAS_MIN_VERTICAL_MARGIN, int(round(height * EXPAND_CANVAS_VERTICAL_RATIO))),
    )
    return {
        "mode": "balanced_outpaint_border_v1",
        "source_size": {
            "width": width,
            "height": height,
        },
        "target_size": {
            "width": width + (horizontal_margin * 2),
            "height": height + (vertical_margin * 2),
        },
        "margins": {
            "left": horizontal_margin,
            "right": horizontal_margin,
            "top": vertical_margin,
            "bottom": vertical_margin,
        },
        "source_inset": {
            "x": horizontal_margin,
            "y": vertical_margin,
        },
        "mask_strategy": "transparent_border_from_alpha",
        "recommended_prompt": "Extend the existing photo naturally beyond the current frame while preserving the subject, lighting, perspective, and edge continuity.",
        "notes": [
            "Prepared RGBA canvas keeps the original frame opaque and marks the padded border as the inpaint region.",
            "The current implementation expands all sides with a balanced border so the same workflow can produce a 화면 확장 candidate without a separate outpaint engine.",
        ],
    }


def prepare_expand_canvas_source(source: Path, *, prepared_dir: Path, record: StudioJobRecord) -> Path:
    prepared_path = prepared_dir / "source.png"
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        base_rgb = image.convert("RGB")
        plan = build_expand_canvas_plan(width=base_rgb.width, height=base_rgb.height)
        target_width = int(plan["target_size"]["width"])
        target_height = int(plan["target_size"]["height"])
        inset_x = int(plan["source_inset"]["x"])
        inset_y = int(plan["source_inset"]["y"])
        source_rgba = base_rgb.convert("RGBA")
        canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        canvas.paste(source_rgba, (inset_x, inset_y))
        canvas.save(prepared_path, format="PNG")

    plan_path = prepared_dir / "expand_canvas_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    append_job_note(
        record,
        f"화면 확장 입력을 {plan['target_size']['width']}x{plan['target_size']['height']} 캔버스로 준비하고, 주변 투명 영역을 인페인트 마스크로 사용합니다.",
    )
    if not (record.prompt or "").strip():
        append_job_note(record, "작업 메모가 비어 있어 화면 확장 기본 프롬프트를 사용합니다.")
    return prepared_path


def prepare_source_image(record: StudioJobRecord) -> Path:
    if not record.source_path:
        raise ValueError("Studio job execution requires a source image.")
    source = ensure_session_source(record.source_path, output_root=Path(record.output_root))
    prepared_dir = Path(record.job_root) / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    if normalize_tool_key(record.tool) == "expandCanvas":
        prepared_path = prepare_expand_canvas_source(source, prepared_dir=prepared_dir, record=record)
    else:
        prepared_path = prepared_dir / "source.png"
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(prepared_path, format="PNG")
    record.prepared_input_path = str(prepared_path)
    save_job_record(record)
    return prepared_path


def stage_comfy_input(prepared_path: Path, *, record: StudioJobRecord) -> str:
    input_dir = comfy_input_dir()
    if not input_dir:
        raise RuntimeError("ComfyUI input directory is not configured. Set COMFY_ROOT or COMFY_INPUT_DIR.")
    input_dir.mkdir(parents=True, exist_ok=True)
    staged_name = f"dreamcatcher_{record.session_id}_{record.job_id}.png"
    staged_path = input_dir / staged_name
    shutil.copy2(prepared_path, staged_path)
    return staged_name


def patch_workflow_payload(record: StudioJobRecord, *, staged_input_name: str) -> Dict[str, Any]:
    workflow_path = Path(record.workflow_path)
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file is missing: {workflow_path}")
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    prompt_text = effective_prompt_text(record)
    for node in payload.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        class_type = node.get("class_type")
        if class_type == "LoadImage" and isinstance(inputs.get("image"), str):
            inputs["image"] = staged_input_name
        if class_type == "SaveImage":
            inputs["filename_prefix"] = f"DreamCatcher_{record.session_id}_{record.job_id[:8]}"
        if prompt_text:
            if class_type == "CLIPTextEncode" and isinstance(inputs.get("text"), str):
                inputs["text"] = prompt_text
            if "prompt" in inputs and isinstance(inputs.get("prompt"), str):
                inputs["prompt"] = prompt_text

    prepared_workflow = Path(record.job_root) / "prepared_workflow.json"
    prepared_workflow.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    record.prepared_workflow_path = str(prepared_workflow)
    save_job_record(record)
    return payload


def comfy_history_outputs(history_payload: Dict[str, Any], *, prompt_id: str) -> List[Dict[str, Any]]:
    prompt_key = prompt_id if prompt_id in history_payload else next(iter(history_payload.keys()), None)
    if not prompt_key:
        return []
    prompt_payload = history_payload.get(prompt_key, {})
    outputs = prompt_payload.get("outputs", {})
    records: List[Dict[str, Any]] = []
    if not isinstance(outputs, dict):
        return records
    for node_payload in outputs.values():
        if not isinstance(node_payload, dict):
            continue
        images = node_payload.get("images", [])
        if not isinstance(images, list):
            continue
        for image in images:
            if isinstance(image, dict):
                records.append(image)
    return records


def studio_output_label(tool: str, *, index: int) -> str:
    normalized_tool = normalize_tool_key(tool)
    labels = {
        "removeBg": "배경 제거",
        "replaceBg": "배경 교체",
        "relight": "조명 보정",
        "replaceObject": "오브젝트 편집",
        "expandCanvas": "화면 확장",
        "retouch": "리터치",
        "enhance": "품질 개선",
        "finish": "마무리 단계",
        "compare": "비교 보기",
    }
    label = labels.get(normalized_tool, normalized_tool or "AI 결과")
    return f"{label} 결과 {index}"


def studio_output_kind(tool: str) -> str:
    normalized_tool = normalize_tool_key(tool)
    if normalized_tool == "removeBg":
        return "background_cutout"
    if normalized_tool in {"replaceBg", "replaceObject", "expandCanvas"}:
        return "generated_candidate"
    return "adjustment_result"


def tool_supports_mask_reuse(tool: str) -> bool:
    return normalize_tool_key(tool) in {"removeBg", "replaceBg", "replaceObject"}


def extract_reusable_mask(source_path: Path, *, destination_path: Path) -> Path | None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source_path) as image:
            if image.mode == "P" and "transparency" in image.info:
                working = image.convert("RGBA")
            else:
                working = image.copy()
            if "A" not in working.getbands():
                return None
            alpha = working.getchannel("A").convert("L")
            extrema = alpha.getextrema()
            if extrema is None or extrema[0] == extrema[1]:
                return None
            alpha.save(destination_path, format="PNG")
            return destination_path
    except OSError:
        destination_path.unlink(missing_ok=True)
        return None


def collect_job_outputs(record: StudioJobRecord, *, prompt_id: str, history_payload: Dict[str, Any]) -> List[StudioJobOutput]:
    output_dir = comfy_output_dir()
    if not output_dir:
        raise RuntimeError("ComfyUI output directory is not configured. Set COMFY_ROOT or COMFY_OUTPUT_DIR.")
    result_dir = Path(record.session_root) / "03_ai" / "results" / record.job_id
    result_dir.mkdir(parents=True, exist_ok=True)

    outputs: List[StudioJobOutput] = []
    output_kind = studio_output_kind(record.tool)
    for index, image in enumerate(comfy_history_outputs(history_payload, prompt_id=prompt_id), start=1):
        filename = image.get("filename")
        if not filename:
            continue
        subfolder = image.get("subfolder") or ""
        source = (output_dir / subfolder / filename).resolve()
        if not source.exists():
            continue
        destination = result_dir / f"{index:02d}_{Path(filename).name}"
        shutil.copy2(source, destination)
        linked_mask_path: str | None = None
        if tool_supports_mask_reuse(record.tool):
            mask_path = extract_reusable_mask(
                destination,
                destination_path=result_dir / f"{index:02d}_{Path(filename).stem}__mask.png",
            )
            if mask_path is not None:
                linked_mask_path = str(mask_path)
        outputs.append(
            StudioJobOutput(
                label=studio_output_label(record.tool, index=index),
                path=str(destination),
                origin=str(source),
                kind=output_kind,
                linked_mask_path=linked_mask_path,
                alpha_extracted=linked_mask_path is not None,
            )
        )
    return outputs


def execute_studio_job(record: StudioJobRecord) -> StudioJobRecord:
    try:
        if not record.execution_ready:
            record.status = "blocked"
            record.current_step = "backend_unavailable"
            record.error = record.availability_error or "ComfyUI is not ready for this tool."
            save_job_record(record)
            return record
        if not record.source_path:
            record.status = "blocked"
            record.current_step = "waiting_for_source"
            record.error = "Studio AI execution requires a source raster file."
            save_job_record(record)
            return record
        if not record.workflow_exists:
            record.status = "blocked"
            record.current_step = "missing_workflow"
            record.error = f"Workflow file is missing: {record.workflow_path}"
            save_job_record(record)
            return record

        record.status = "running"
        record.current_step = "preparing_input"
        record.started_at = utc_now_iso()
        save_job_record(record)

        prepared_path = prepare_source_image(record)
        staged_input_name = stage_comfy_input(prepared_path, record=record)
        workflow_payload = patch_workflow_payload(record, staged_input_name=staged_input_name)

        record.current_step = "submitting_to_comfyui"
        save_job_record(record)

        client = ComfyClient(comfy_base_url())
        client.system_stats()
        submit_response = client.submit_prompt(workflow_payload, client_id=f"dreamcatcher-{record.job_id}")
        prompt_id = submit_response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return a prompt_id for the submitted job.")

        record.status = "submitted"
        record.current_step = "submitted"
        record.comfy_prompt_id = str(prompt_id)
        save_job_record(record)
        return record
    except Exception as exc:
        return mark_job_error(record, str(exc), current_step=record.current_step or "execution_failed")


def refresh_studio_job(record: StudioJobRecord) -> StudioJobRecord:
    if record.status not in {"submitted", "running"} or not record.comfy_prompt_id:
        return record

    try:
        client = ComfyClient(comfy_base_url())
        history_payload = client.history(record.comfy_prompt_id)
        if not history_payload:
            record.status = "running"
            record.current_step = "waiting_for_history"
            save_job_record(record)
            return record

        outputs = collect_job_outputs(record, prompt_id=record.comfy_prompt_id, history_payload=history_payload)
        if not outputs:
            history_key = record.comfy_prompt_id if record.comfy_prompt_id in history_payload else next(iter(history_payload.keys()), None)
            history_entry = history_payload.get(history_key or "", {})
            status_payload = history_entry.get("status", {}) if isinstance(history_entry, dict) else {}
            messages = history_entry.get("messages", []) if isinstance(history_entry, dict) else []
            if isinstance(status_payload, dict) and status_payload.get("status_str") in {"error", "failed"}:
                error_text = status_payload.get("completed", False) and "ComfyUI finished without image outputs."
                return mark_job_error(record, str(error_text or "ComfyUI reported an error."), current_step="comfy_failed")
            if messages:
                return mark_job_error(record, "ComfyUI completed without exportable image outputs.", current_step="no_outputs")
            record.status = "running"
            record.current_step = "waiting_for_outputs"
            save_job_record(record)
            return record

        record.outputs = outputs
        record.status = "done"
        record.current_step = "done"
        record.finished_at = utc_now_iso()
        save_job_record(record)
        try:
            build_or_update_session_edit_linkage(
                record.session_id,
                output_root=record.output_root,
                current_source_path=record.source_path,
                active_tool=record.tool,
                studio_job_record=record,
            )
        except Exception as exc:  # pragma: no cover - linkage sync must not hide a successful AI result
            record.notes.append(f"DreamGen linkage sync failed after output collection: {exc}")
            save_job_record(record)
        return record
    except Exception as exc:
        return mark_job_error(record, str(exc), current_step=record.current_step or "refresh_failed")


def cancel_studio_job(job_id: str, *, output_root: str) -> StudioJobRecord:
    record = load_job_record(job_id, output_root=output_root)
    if record.status in {"done", "error", "blocked", "cancelled"}:
        return record

    if not record.comfy_prompt_id or record.status in {"planned", "queued"}:
        cancelled = mark_job_cancelled(record, note="Studio job was cancelled before ComfyUI execution started.")
        from .studio_queue import cancel_pending_entry

        cancel_pending_entry(
            task_type="studio",
            job_id=record.job_id,
            output_root=record.output_root,
            detail="Studio job was cancelled before ComfyUI execution started.",
        )
        return cancelled

    client = ComfyClient(comfy_base_url())
    queue_cancelled = False
    interrupt_sent = False
    errors: list[str] = []

    try:
        queue_response = client.manage_queue(delete=[record.comfy_prompt_id])
        deleted = queue_response.get("deleted")
        queue_cancelled = isinstance(deleted, list) and record.comfy_prompt_id in deleted
    except Exception as exc:
        errors.append(str(exc))

    try:
        client.interrupt(record.comfy_prompt_id)
        interrupt_sent = True
    except Exception as exc:
        errors.append(str(exc))

    if not queue_cancelled and not interrupt_sent:
        raise RuntimeError("Unable to cancel the active ComfyUI job. " + " | ".join(errors))

    return mark_job_cancelled(record, note="Studio job was cancelled by the user.")


def retry_studio_job(job_id: str, *, output_root: str) -> StudioJobRecord:
    record = load_job_record(job_id, output_root=output_root)
    if record.status in {"queued", "running", "submitted"}:
        raise RuntimeError("The studio job is still active and cannot be retried yet.")

    record = assess_job_readiness(record, use_cache=False)
    record.status = "planned"
    record.current_step = "planned"
    record.error = None
    record.started_at = None
    record.finished_at = None
    record.outputs = []
    record.prepared_input_path = None
    record.prepared_workflow_path = None
    record.comfy_prompt_id = None
    record.notes.append("Studio job was retried from the saved session state.")
    save_job_record(record)
    return record
