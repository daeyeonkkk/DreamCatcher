from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image
import tifffile

from .planner import TriRawFoundationPlan


RAWFUSION_ADAPTER_ID = "rawfusion_unet_external_v1"


@dataclass(frozen=True)
class TriRawLearnedAdapterResult:
    adapter_id: str = RAWFUSION_ADAPTER_ID
    status: str = "disabled"
    reason: str | None = None
    output_path: str | None = None
    preview_path: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _disabled(reason: str, **evidence: Any) -> TriRawLearnedAdapterResult:
    return TriRawLearnedAdapterResult(status="disabled", reason=reason, evidence=evidence)


def _unavailable(reason: str, **evidence: Any) -> TriRawLearnedAdapterResult:
    return TriRawLearnedAdapterResult(status="unavailable", reason=reason, evidence=evidence)


def _unsupported(reason: str, **evidence: Any) -> TriRawLearnedAdapterResult:
    return TriRawLearnedAdapterResult(status="unsupported", reason=reason, evidence=evidence)


def _image_to_uint8(array: np.ndarray) -> np.ndarray:
    array = np.asarray(array)
    if array.ndim == 2:
        array = np.stack([array, array, array], axis=-1)
    if array.ndim == 3 and array.shape[0] in {1, 3} and array.shape[-1] not in {1, 3}:
        array = np.moveaxis(array, 0, -1)
    if array.ndim == 3 and array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    array = array[..., :3].astype(np.float32)
    if array.size and float(np.max(array)) > 1.0:
        max_value = 65535.0 if float(np.max(array)) > 255.0 else 255.0
        array = array / max_value
    return np.clip(array * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)


def _read_rawfusion_frame(path: Path) -> np.ndarray:
    array = tifffile.imread(path)
    if array.ndim == 3:
        array = np.asarray(array[..., 0], dtype=np.float32)
    else:
        array = np.asarray(array, dtype=np.float32)
    if array.size and float(np.max(array)) > 1.0:
        max_value = 65535.0 if float(np.max(array)) > 255.0 else 255.0
        array = array / max_value
    return np.clip(array, 0.0, 1.0).astype(np.float32)


def _resolve_rawfusion_frame_path(path: Path) -> Path:
    if path.suffix.lower() in {".tif", ".tiff"}:
        return path
    for suffix in (".tif", ".tiff"):
        companion = path.with_suffix(suffix)
        if companion.is_file():
            return companion
    return path


def _pad_to_multiple(array: np.ndarray, multiple: int = 16) -> tuple[np.ndarray, tuple[int, int]]:
    height, width = array.shape[-2:]
    pad_h = (multiple - (height % multiple)) % multiple
    pad_w = (multiple - (width % multiple)) % multiple
    if pad_h == 0 and pad_w == 0:
        return array, (height, width)
    padded = np.pad(array, ((0, 0), (0, pad_h), (0, pad_w)), mode="edge")
    return padded.astype(np.float32), (height, width)


def _load_rawfusion_unet(repo_path: Path) -> type[Any]:
    module_path = repo_path / "models" / "Model_0_unet.py"
    spec = importlib.util.spec_from_file_location("dreamcatcher_external_rawfusion_unet", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load RawFusion model file: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.UNet


def _load_state_dict(torch: Any, checkpoint_path: Path) -> dict[str, Any]:
    checkpoint = torch.load(str(checkpoint_path), map_location="cpu")
    if isinstance(checkpoint, dict) and isinstance(checkpoint.get("state_dict"), dict):
        checkpoint = checkpoint["state_dict"]
    if not isinstance(checkpoint, dict):
        raise ValueError("RawFusion checkpoint did not contain a state dict")
    normalized: dict[str, Any] = {}
    for key, value in checkpoint.items():
        normalized[str(key).removeprefix("module.")] = value
    return normalized


def _materialize_rawfusion_candidate(
    plan: TriRawFoundationPlan,
    *,
    repo_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    preview_path: Path,
) -> TriRawLearnedAdapterResult:
    if len(plan.source_paths) != 9:
        return _unsupported(
            "rawfusion_requires_nine_frames",
            frame_count=len(plan.source_paths),
            accepted_frame_count=9,
        )

    source_paths = [_resolve_rawfusion_frame_path(Path(path)) for path in plan.source_paths]
    non_tiff = [str(path) for path in source_paths if path.suffix.lower() not in {".tif", ".tiff"}]
    if non_tiff:
        return _unsupported(
            "rawfusion_requires_nine_tiff_raw_frames_or_companions",
            unsupported_paths=non_tiff,
        )
    if not repo_path.is_dir():
        return _unavailable("rawfusion_repo_missing", repo_path=str(repo_path))
    if not (repo_path / "models" / "Model_0_unet.py").is_file():
        return _unavailable("rawfusion_model_code_missing", repo_path=str(repo_path))
    if not checkpoint_path.is_file():
        return _unavailable("rawfusion_checkpoint_missing", checkpoint_path=str(checkpoint_path))

    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:
        return _unavailable("torch_missing_for_rawfusion_adapter", error=str(exc))

    frames = [_read_rawfusion_frame(path) for path in source_paths]
    shapes = {frame.shape for frame in frames}
    if len(shapes) != 1:
        return _unsupported("rawfusion_frame_shapes_mismatch", shapes=sorted(str(shape) for shape in shapes))

    stacked = np.stack(frames, axis=0).astype(np.float32)
    stacked, original_size = _pad_to_multiple(stacked, multiple=16)
    device_preference = os.environ.get("DC_RAWFUSION_DEVICE", "auto").strip().lower()
    device_name = "cuda" if device_preference == "auto" and torch.cuda.is_available() else device_preference
    if device_name not in {"cpu", "cuda"}:
        device_name = "cpu"
    if device_name == "cuda" and not torch.cuda.is_available():
        device_name = "cpu"
    device = torch.device(device_name)

    try:
        model_cls = _load_rawfusion_unet(repo_path)
        model = model_cls()
        state_dict = _load_state_dict(torch, checkpoint_path)
        model.load_state_dict(state_dict, strict=True)
        model.to(device)
        model.eval()
        tensor = torch.from_numpy(stacked[None, ...]).to(device)
        with torch.no_grad():
            prediction = torch.clamp(model(tensor), 0.0, 1.0)[0].detach().cpu().numpy()
    except Exception as exc:
        return _unavailable("rawfusion_inference_failed", error=str(exc))

    original_h, original_w = original_size
    prediction = prediction[:, :original_h, :original_w]
    output_rgb = np.moveaxis(prediction, 0, -1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(output_path, np.clip(output_rgb * 65535.0 + 0.5, 0.0, 65535.0).astype(np.uint16), photometric="rgb")
    Image.fromarray(_image_to_uint8(output_rgb), mode="RGB").save(preview_path, format="JPEG", quality=95)

    return TriRawLearnedAdapterResult(
        status="materialized",
        reason="rawfusion_candidate_ready",
        output_path=str(output_path),
        preview_path=str(preview_path),
        evidence={
            "repo_path": str(repo_path),
            "checkpoint_path": str(checkpoint_path),
            "device": device_name,
            "frame_count": len(source_paths),
            "input_shape": list(frames[0].shape),
            "output_shape": list(output_rgb.shape),
        },
    )


def materialize_tri_raw_learned_adapter(
    plan: TriRawFoundationPlan,
    *,
    output_path: Path,
    preview_path: Path,
) -> TriRawLearnedAdapterResult:
    adapter = os.environ.get("DC_TRIRAW_LEARNED_ADAPTER", "").strip().lower()
    if adapter not in {"rawfusion", "rawfusion_unet"}:
        return _disabled(
            "set_DC_TRIRAW_LEARNED_ADAPTER_rawfusion_to_enable",
            configured_adapter=adapter or None,
        )

    repo_value = os.environ.get("DC_RAWFUSION_REPO", "").strip()
    if not repo_value:
        return _unavailable("DC_RAWFUSION_REPO_not_set")
    repo_path = Path(repo_value)
    checkpoint_value = os.environ.get("DC_RAWFUSION_CKPT", "").strip()
    checkpoint_path = Path(checkpoint_value) if checkpoint_value else repo_path / "model_zoo" / "Ckpt_0_Organizer_team.pth"
    return _materialize_rawfusion_candidate(
        plan,
        repo_path=repo_path,
        checkpoint_path=checkpoint_path,
        output_path=output_path,
        preview_path=preview_path,
    )
