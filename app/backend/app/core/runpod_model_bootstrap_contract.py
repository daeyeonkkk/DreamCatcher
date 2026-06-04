from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


RUNPOD_TEMPLATE_PRIMARY_IMAGE = "runpod/comfyui:1.4.1-cuda12.8"
RUNPOD_TEMPLATE_ALIAS_IMAGE = "runpod/comfyui:cuda12.8"
RUNPOD_TEMPLATE_FALLBACK_IMAGE = "runpod/comfyui:1.3.0-cuda12.8"
RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE = "runpod/comfyui:1.4.1-cuda13.0"
RUNPOD_PREWARM_DOCKERFILE = "runpod/prewarm/Dockerfile.runtime"
RUNPOD_PREWARM_BUILD_SCRIPT = "runpod/build_prewarmed_image.ps1"
RUNPOD_RECOMMENDED_GPU_SERVER = "RTX PRO 6000"
RUNPOD_RECOMMENDED_GPU_VRAM = "96GB"
RUNPOD_CONTAINER_DISK_GB = 80
RUNPOD_VOLUME_DISK_DEFAULT_GB = 400
RUNPOD_VOLUME_DISK_FULL_FRONTIER_QWEN_GB = 500
FRONTIER_PROFILE_ID = "frontier"
LEGACY_PROFILE_ALIASES = {
    "core": FRONTIER_PROFILE_ID,
    "pro": FRONTIER_PROFILE_ID,
    "labs": FRONTIER_PROFILE_ID,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _default_workspace_root() -> Path:
    return _resolve_path("/workspace")


def _default_app_root(workspace_root: Path) -> Path:
    return _resolve_path(workspace_root / "DreamCatcher")


def _default_comfy_root() -> Path:
    return _resolve_path("/workspace/runpod-slim/ComfyUI")


class RunPodModelSet(BaseModel):
    model_set_id: str
    cli_flag: str | None = None
    label: str
    summary: str
    task_tags: list[str] = Field(default_factory=list)
    frontier_default: bool = False
    bootstrap_supported: bool = True
    integration_status: str = "ready"
    min_vram_class: str = "24GB"
    requires_hf_token: bool = True
    license_note: str = "Requires accepted upstream model terms where applicable."
    research_refs: list[str] = Field(default_factory=list)
    data_refs: list[str] = Field(default_factory=list)
    target_paths: list[str] = Field(default_factory=list)


class RunPodModelProfile(BaseModel):
    profile_id: str
    label: str
    summary: str
    model_set_ids: list[str] = Field(default_factory=list)
    min_vram_class: str
    requires_hf_token: bool = True
    license_note: str
    bootstrap_command: str


class RunPodTemplatePolicy(BaseModel):
    template_type: str = "private_nvidia_gpu_pod"
    recommended_gpu_server: str = RUNPOD_RECOMMENDED_GPU_SERVER
    recommended_gpu_vram: str = RUNPOD_RECOMMENDED_GPU_VRAM
    image_primary: str
    compatibility_alias: str
    fallback_image: str
    cuda13_experimental_image: str
    prewarmed_image_candidate: str | None = None
    prewarmed_image_policy: str = (
        "Optional runtime-only optimization after repeated RTX PRO 6000 smoke evidence; "
        "DreamCatcher.zip remains the source of truth and model weights are not baked by default."
    )
    prewarmed_build_artifacts: dict[str, str] = Field(default_factory=dict)
    prewarmed_content_scope: list[str] = Field(default_factory=list)
    storage_policy: str = "ephemeral_session_local"
    container_disk_gb: int = RUNPOD_CONTAINER_DISK_GB
    volume_disk_default_gb: int = RUNPOD_VOLUME_DISK_DEFAULT_GB
    volume_disk_full_frontier_qwen_gb: int = RUNPOD_VOLUME_DISK_FULL_FRONTIER_QWEN_GB
    network_volume_policy: str = "disabled_by_default"
    persistent_model_cache_policy: str = "disabled"
    long_term_outputs_policy: str = "external_or_local_only"
    upload_artifact: str = "DreamCatcher.zip"
    workspace: dict[str, str]
    ports: dict[str, str]
    required_env: dict[str, str]
    gpu_selection_policy: str


class RunPodBootstrapSessionPolicy(BaseModel):
    mode: str = "ephemeral_zip_pod"
    default_profile: str
    frontier_bootstrap_scope: str
    startup_policy: list[str]
    end_of_session_policy: list[str]
    persistent_volume_policy: str
    recovery_contract: str


class RunPodModelBootstrapChecks(BaseModel):
    explicit_selection_recorded: bool = False
    only_requested_sets_selected: bool = False
    profile_selection_recorded: bool = False
    no_global_default_download_all: bool = False
    download_all_requested: bool = False
    comfy_models_root_present: bool = False
    ephemeral_session_policy_recorded: bool = False


class RunPodModelBootstrapContract(BaseModel):
    created_at: str
    workspace_root: str
    app_root: str
    comfy_root: str
    comfy_models_root: str
    artifact_path: str
    default_strategy: str = "frontier_ephemeral_bootstrap"
    download_scope_status: str = "lazy_on_demand"
    model_profile: str | None = None
    legacy_profile_alias: str | None = None
    profile_metadata: RunPodModelProfile | None = None
    selected_model_sets: list[str] = Field(default_factory=list)
    selected_download_flags: list[str] = Field(default_factory=list)
    frontier_research_model_sets: list[str] = Field(default_factory=list)
    available_model_sets: list[RunPodModelSet] = Field(default_factory=list)
    available_model_profiles: list[RunPodModelProfile] = Field(default_factory=list)
    template_policy: RunPodTemplatePolicy
    bootstrap_session_policy: RunPodBootstrapSessionPolicy
    checks: RunPodModelBootstrapChecks
    issues: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ok: bool = False


MODEL_SET_REGISTRY: tuple[RunPodModelSet, ...] = (
    RunPodModelSet(
        model_set_id="birefnet_dis5k",
        cli_flag="--download-birefnet",
        label="BiRefNet-DIS5K",
        summary="Cutout and matting path for high-quality local background isolation.",
        task_tags=["cutout", "mask"],
        frontier_default=True,
        min_vram_class="16GB",
        requires_hf_token=False,
        license_note="Public Hugging Face model; keep the upstream license in release notes.",
        target_paths=["models/BiRefNet/model.safetensors"],
    ),
    RunPodModelSet(
        model_set_id="qwen",
        cli_flag="--download-qwen",
        label="Qwen Image Edit 2511",
        summary="Precision retouch, text edit, identity-preserving edit, and multi-reference edit path.",
        task_tags=["precision_edit", "retouch", "text_edit"],
        frontier_default=True,
        min_vram_class="24GB",
        license_note="HF token required; confirm Qwen-Image-Edit model terms before bootstrap.",
        research_refs=["https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511"],
        target_paths=[
            "models/vae/qwen_image_vae.safetensors",
            "models/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
            "models/diffusion_models/qwen_image_edit_2511_bf16.safetensors",
            "models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="qwen_image_2512",
        cli_flag="--download-qwen-2512",
        label="Qwen Image 2512",
        summary="Frontier text-to-image upgrade for realism, natural detail, and bilingual text rendering.",
        task_tags=["text_to_image", "text_rendering", "synthesis"],
        frontier_default=True,
        min_vram_class="32GB",
        license_note="HF token required; upstream Qwen terms apply.",
        research_refs=["https://docs.comfy.org/tutorials/image/qwen/qwen-image-2512"],
        target_paths=[
            "models/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors",
            "models/loras/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors",
            "models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
            "models/vae/qwen_image_vae.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="qwen_judge",
        cli_flag="--download-qwen-judge",
        label="Qwen3.6-35B-A3B-FP8 Judge",
        summary="Local vision-language judge for quality inspection, retry instructions, golden regression review, and tuning proposals.",
        task_tags=["quality_judge", "vlm", "automation", "code_tuning"],
        frontier_default=True,
        min_vram_class="48GB",
        requires_hf_token=False,
        license_note="Apache-2.0; keep local-only as the no-cloud-fallback quality judge.",
        research_refs=["https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8"],
        target_paths=[
            "models/qwen_judge/Qwen3.6-35B-A3B-FP8/config.json",
            "models/qwen_judge/Qwen3.6-35B-A3B-FP8/model.safetensors.index.json",
        ],
    ),
    RunPodModelSet(
        model_set_id="flux2_dev",
        cli_flag="--download-flux2-dev",
        label="FLUX.2 Dev FP8",
        summary="Heavy composition path for backgrounds, multi-reference subject control, and product-grade generation.",
        task_tags=["composition", "reference", "generation"],
        frontier_default=True,
        min_vram_class="48GB",
        license_note="HF token required; BFL gated license acceptance may be required.",
        research_refs=["https://docs.comfy.org/tutorials/flux/flux-2-dev"],
        target_paths=[
            "models/vae/flux2-vae.safetensors",
            "models/diffusion_models/flux2_dev_fp8mixed.safetensors",
            "models/text_encoders/mistral_3_small_flux2_fp8.safetensors",
            "models/loras/Flux2TurboComfyv2.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="klein",
        cli_flag="--download-klein",
        label="FLUX.2 Klein FP8",
        summary="Fast preview, relight, object edit, and low-latency iteration path.",
        task_tags=["preview", "relight", "fast_edit"],
        frontier_default=True,
        min_vram_class="24GB",
        license_note="HF token required; upstream FLUX.2 terms apply.",
        research_refs=["https://docs.comfy.org/tutorials/flux/flux-2-klein"],
        target_paths=[
            "models/vae/flux2-vae.safetensors",
            "models/diffusion_models/flux-2-klein-9b-fp8.safetensors",
            "models/text_encoders/qwen_3_8b_fp8mixed.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="fill",
        cli_flag="--download-fill",
        label="FLUX.1 Fill dev",
        summary="Inpaint, outpaint, and object replacement path for repair workflows.",
        task_tags=["fill", "inpaint", "outpaint"],
        frontier_default=True,
        min_vram_class="24GB",
        license_note="HF token required; BFL gated license acceptance may be required.",
        target_paths=[
            "models/vae/ae.safetensors",
            "models/diffusion_models/flux1-fill-dev.safetensors",
            "models/text_encoders/clip_l.safetensors",
            "models/text_encoders/t5xxl_fp16.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="qwen_layered",
        cli_flag="--download-qwen-layered",
        label="Qwen Image Layered",
        summary="Layer decomposition model for object-isolated RGBA editing and recursive layer workflows.",
        task_tags=["layered_edit", "mask", "object_isolation"],
        frontier_default=True,
        min_vram_class="48GB",
        license_note="HF token required; upstream Qwen terms apply.",
        research_refs=[
            "https://docs.comfy.org/tutorials/image/qwen/qwen-image-layered",
            "https://arxiv.org/abs/2512.15603",
        ],
        target_paths=[
            "models/diffusion_models/qwen_image_layered_fp8mixed.safetensors",
            "models/vae/qwen_image_layered_vae.safetensors",
            "models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="z_image_turbo",
        cli_flag="--download-z-image",
        label="Z-Image Turbo",
        summary="Efficient fast generation branch with strong photorealism and bilingual text rendering.",
        task_tags=["fast_generation", "text_rendering", "low_vram"],
        frontier_default=True,
        min_vram_class="24GB",
        license_note="HF token required and upstream Z-Image terms apply.",
        research_refs=[
            "https://docs.comfy.org/tutorials/image/z-image/z-image-turbo",
            "https://arxiv.org/abs/2511.22699",
        ],
        target_paths=[
            "models/diffusion_models/z_image_turbo_nvfp4.safetensors",
            "models/text_encoders/qwen_3_4b_fp8_mixed.safetensors",
            "models/vae/ae.safetensors",
            "models/loras/z_image_turbo_distill_patch_lora_bf16.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="omnigen2",
        cli_flag="--download-omnigen2",
        label="OmniGen2",
        summary="Unified multimodal generation/editing path for image understanding, edits, and composition.",
        task_tags=["multimodal", "image_edit", "composition"],
        frontier_default=True,
        min_vram_class="48GB",
        license_note="HF token required and upstream OmniGen2 terms apply.",
        research_refs=["https://docs.comfy.org/tutorials/image/omnigen/omnigen2"],
        target_paths=[
            "models/diffusion_models/omnigen2_fp16.safetensors",
            "models/text_encoders/qwen_2.5_vl_fp16.safetensors",
            "models/vae/ae.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="longcat_image_edit_turbo",
        cli_flag=None,
        label="LongCat Image Edit Turbo",
        summary="Fast 8-step image edit candidate; diffusers path is verified, Comfy-native packaging is still needed.",
        task_tags=["fast_edit", "research"],
        frontier_default=False,
        bootstrap_supported=False,
        integration_status="workflow_needed",
        min_vram_class="48GB",
        license_note="HF token required; do not make default until a Comfy workflow and packaging path are verified.",
        research_refs=["https://huggingface.co/meituan-longcat/LongCat-Image-Edit-Turbo"],
        target_paths=[
            "models/longcat/model_index.json",
            "models/longcat/transformer/diffusion_pytorch_model.safetensors",
            "models/longcat/vae/diffusion_pytorch_model.safetensors",
        ],
    ),
    RunPodModelSet(
        model_set_id="flux1_kontext_dev",
        cli_flag=None,
        label="FLUX.1 Kontext-dev",
        summary="Reference/edit candidate retained in Frontier research tracking until workflow export is pinned.",
        task_tags=["reference_edit", "research"],
        frontier_default=False,
        bootstrap_supported=False,
        integration_status="license_review",
        min_vram_class="48GB",
        license_note="BFL gated license acceptance may be required; smoke before enabling bootstrap.",
        research_refs=["https://docs.comfy.org/tutorials/flux/flux-1-kontext-dev"],
    ),
    RunPodModelSet(
        model_set_id="tri_raw_frontier",
        cli_flag=None,
        label="TriRaw Frontier RAW Merge",
        summary="Research track for learned RAW burst HDR, alignment, denoise, and restoration.",
        task_tags=["raw_burst_merge", "hdr", "denoise", "research"],
        frontier_default=False,
        bootstrap_supported=False,
        integration_status="research_spike",
        min_vram_class="80GB",
        requires_hf_token=False,
        license_note="Research and dataset licenses must be reviewed before downloading code or training data.",
        research_refs=[
            "https://arxiv.org/abs/2505.12089",
            "https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/html/Qiu_Recursive_Multi-Exposure_Alignment_with_Spatiotemporal_Decoupling_for_Efficient_Burst_HDR_CVPRW_2025_paper.html",
            "https://github.com/Eve-ctr/RawFusion",
            "https://arxiv.org/abs/2404.10358",
        ],
        data_refs=[
            "NTIRE 2025 Efficient Burst HDR and Restoration",
            "RAWIR / NTIRE 2025 RAW Image Restoration",
            "BracketIRE",
        ],
    ),
)

_MODEL_SETS_BY_ID = {item.model_set_id: item for item in MODEL_SET_REGISTRY}

FRONTIER_DEFAULT_MODEL_SET_IDS = [
    item.model_set_id
    for item in MODEL_SET_REGISTRY
    if item.frontier_default and item.bootstrap_supported
]

MODEL_PROFILE_REGISTRY: tuple[RunPodModelProfile, ...] = (
    RunPodModelProfile(
        profile_id=FRONTIER_PROFILE_ID,
        label="Frontier Studio",
        summary=(
            "Single aggressive Studio stack: cutout, precision edit, layered edit, composition, "
            "preview/relight, fill, fast generation, multimodal edit, RAW frontier tracking, "
            "and local Qwen quality judgment."
        ),
        model_set_ids=FRONTIER_DEFAULT_MODEL_SET_IDS,
        min_vram_class="48GB",
        license_note=(
            "HF token required; BFL gated licenses must be accepted for FLUX paths. "
            "Operational RunPod target is RTX PRO 6000 96GB; use 500GB volume disk when Full Frontier plus Qwen judge is enabled."
        ),
        bootstrap_command="./runpod/bootstrap_core.sh --profile frontier",
    ),
)

_MODEL_PROFILES_BY_ID = {item.profile_id: item for item in MODEL_PROFILE_REGISTRY}


def default_model_bootstrap_contract_path(app_root: str | Path) -> Path:
    return _resolve_path(Path(app_root) / "app" / "runtime" / "runpod_model_bootstrap_contract.json")


def list_runpod_model_sets() -> list[RunPodModelSet]:
    return list(MODEL_SET_REGISTRY)


def list_runpod_model_profiles() -> list[RunPodModelProfile]:
    return list(MODEL_PROFILE_REGISTRY)


def build_runpod_template_policy() -> RunPodTemplatePolicy:
    prewarmed_candidate = os.getenv("RUNPOD_TEMPLATE_PREWARMED_IMAGE") or None
    return RunPodTemplatePolicy(
        image_primary=os.getenv("RUNPOD_TEMPLATE_PRIMARY_IMAGE", RUNPOD_TEMPLATE_PRIMARY_IMAGE),
        compatibility_alias=os.getenv("RUNPOD_TEMPLATE_FALLBACK_ALIAS", RUNPOD_TEMPLATE_ALIAS_IMAGE),
        fallback_image=os.getenv("RUNPOD_TEMPLATE_FALLBACK_IMAGE", RUNPOD_TEMPLATE_FALLBACK_IMAGE),
        cuda13_experimental_image=os.getenv(
            "RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE",
            RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE,
        ),
        prewarmed_image_candidate=prewarmed_candidate,
        prewarmed_build_artifacts={
            "dockerfile": RUNPOD_PREWARM_DOCKERFILE,
            "windows_build_script": RUNPOD_PREWARM_BUILD_SCRIPT,
        },
        prewarmed_content_scope=[
            "Node.js runtime and npm tarball cache",
            "Python/uv/pip dependency cache",
            "optional ComfyUI custom nodes when explicitly built with PREWARM_CUSTOM_NODES=1",
            "empty workspace/cache directories for the ephemeral Pod layout",
            "no HF_TOKEN, user outputs, or default model weights",
        ],
        workspace={
            "app": "/workspace/DreamCatcher",
            "comfyui": "/workspace/runpod-slim/ComfyUI",
            "outputs": "/workspace/DreamCatcher/outputs",
            "hf_cache": "/workspace/.cache/huggingface",
        },
        ports={
            "studio": "8000/http",
            "comfy_admin": "8188/http; expose only when needed",
            "ssh": "22/tcp",
        },
        required_env={
            "HF_TOKEN": "required during bootstrap",
            "DC_MODEL_PROFILE": os.getenv("DC_MODEL_PROFILE", FRONTIER_PROFILE_ID),
            "DC_SERVE_FRONTEND": os.getenv("DC_SERVE_FRONTEND", "1"),
            "DC_COMFY_PUBLIC": os.getenv("DC_COMFY_PUBLIC", "0"),
        },
        gpu_selection_policy=(
            "Use RTX PRO 6000 96GB as the fixed DreamCatcher RunPod target. "
            "Do not silently downgrade; any exception must be an explicit operator decision."
        ),
    )


def build_runpod_bootstrap_session_policy(default_profile: str | None = None) -> RunPodBootstrapSessionPolicy:
    profile = _normalize_model_profile(default_profile or os.getenv("DC_MODEL_PROFILE", FRONTIER_PROFILE_ID))[0]
    return RunPodBootstrapSessionPolicy(
        default_profile=profile or FRONTIER_PROFILE_ID,
        frontier_bootstrap_scope=(
            "Full Frontier: download executable Comfy/model sets by default; keep research datasets and unverified adapters explicit."
        ),
        startup_policy=[
            "Start from a fresh Pod.",
            "Select RTX PRO 6000 96GB.",
            "Set container disk to 80GB.",
            "Set volume disk to 400GB by default, or 500GB when Full Frontier plus Qwen judge is enabled.",
            "Keep Network Volume disabled.",
            "Upload DreamCatcher.zip.",
            "Optionally use a private runtime-prewarmed image after live smoke; DreamCatcher.zip remains required.",
            "Bootstrap --profile frontier for the single aggressive Studio stack.",
            "Use direct --download-* flags only for surgical refreshes or future research/data packs.",
            "Serve the built Studio through FastAPI on port 8000 when DC_SERVE_FRONTEND=1.",
            "Keep ComfyUI behind Studio; expose port 8188 only for administration.",
        ],
        end_of_session_policy=[
            "Export final images and packages.",
            "Download or transfer /workspace/DreamCatcher/outputs.",
            "Preserve bootstrap_summary.json and smoke evidence when needed.",
            "Stop and terminate the Pod after artifact recovery.",
        ],
        persistent_volume_policy=(
            "Network Volume and persistent model cache are disabled by default; long-term outputs live in external or local storage only."
        ),
        recovery_contract="A future session must bootstrap from DreamCatcher.zip alone after Pod termination.",
    )


def build_runpod_model_profiles_payload() -> dict[str, Any]:
    profile_payloads: list[dict[str, Any]] = []
    for profile in MODEL_PROFILE_REGISTRY:
        profile_payload = profile.model_dump()
        profile_payload["model_sets"] = [
            _MODEL_SETS_BY_ID[model_set_id].model_dump() for model_set_id in profile.model_set_ids
        ]
        profile_payloads.append(profile_payload)

    default_profile, _legacy_alias = _normalize_model_profile(os.getenv("DC_MODEL_PROFILE", FRONTIER_PROFILE_ID))
    return {
        "default_profile": default_profile or FRONTIER_PROFILE_ID,
        "profiles": profile_payloads,
        "available_model_sets": [item.model_dump() for item in MODEL_SET_REGISTRY],
    }


def _normalize_model_profile(model_profile: str | None) -> tuple[str | None, str | None]:
    if model_profile is None or model_profile == "":
        return None, None
    normalized = model_profile.lower().strip()
    if normalized in LEGACY_PROFILE_ALIASES:
        return LEGACY_PROFILE_ALIASES[normalized], normalized
    if normalized not in _MODEL_PROFILES_BY_ID:
        allowed = ", ".join(sorted([*_MODEL_PROFILES_BY_ID, *LEGACY_PROFILE_ALIASES]))
        raise ValueError(f"Unknown RunPod model profile '{model_profile}'. Expected one of: {allowed}.")
    return normalized, None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _supported_model_set_ids() -> list[str]:
    return [item.model_set_id for item in MODEL_SET_REGISTRY if item.bootstrap_supported]


def build_runpod_model_bootstrap_contract(
    *,
    workspace_root: str | Path = "/workspace",
    app_root: str | Path | None = None,
    comfy_root: str | Path = "/workspace/runpod-slim/ComfyUI",
    model_profile: str | None = None,
    download_birefnet: bool = False,
    download_qwen: bool = False,
    download_qwen_2512: bool = False,
    download_qwen_judge: bool = False,
    download_flux2_dev: bool = False,
    download_klein: bool = False,
    download_fill: bool = False,
    download_qwen_layered: bool = False,
    download_z_image: bool = False,
    download_omnigen2: bool = False,
    download_all: bool = False,
    artifact_path: str | Path | None = None,
) -> RunPodModelBootstrapContract:
    resolved_workspace_root = _resolve_path(workspace_root)
    resolved_app_root = _resolve_path(app_root or _default_app_root(resolved_workspace_root))
    resolved_comfy_root = _resolve_path(comfy_root or _default_comfy_root())
    resolved_comfy_models_root = _resolve_path(resolved_comfy_root / "models")
    resolved_artifact_path = _resolve_path(artifact_path or default_model_bootstrap_contract_path(resolved_app_root))

    normalized_profile, legacy_alias = _normalize_model_profile(model_profile)
    profile_metadata = _MODEL_PROFILES_BY_ID.get(normalized_profile) if normalized_profile else None
    requested_ids: list[str] = []
    if profile_metadata:
        requested_ids.extend(profile_metadata.model_set_ids)

    direct_flag_map = {
        "birefnet_dis5k": bool(download_birefnet),
        "qwen": bool(download_qwen),
        "qwen_image_2512": bool(download_qwen_2512),
        "qwen_judge": bool(download_qwen_judge),
        "flux2_dev": bool(download_flux2_dev),
        "klein": bool(download_klein),
        "fill": bool(download_fill),
        "qwen_layered": bool(download_qwen_layered),
        "z_image_turbo": bool(download_z_image),
        "omnigen2": bool(download_omnigen2),
    }
    requested_ids.extend([model_set_id for model_set_id, enabled in direct_flag_map.items() if enabled])
    if download_all:
        requested_ids = _supported_model_set_ids()

    selected_model_sets = _dedupe(requested_ids)
    selected_download_flags = [
        item.cli_flag
        for item in MODEL_SET_REGISTRY
        if item.model_set_id in selected_model_sets and item.cli_flag is not None
    ]
    selected_download_flags = [flag for flag in selected_download_flags if flag is not None]

    if download_all:
        download_scope_status = "download_all"
    elif normalized_profile and any(direct_flag_map.values()):
        download_scope_status = "profile_plus_requested"
    elif normalized_profile:
        download_scope_status = f"profile:{normalized_profile}"
    elif selected_model_sets:
        download_scope_status = "requested_only"
    else:
        download_scope_status = "lazy_on_demand"

    expected_selected_ids = _supported_model_set_ids() if download_all else selected_model_sets
    unsupported_selected_ids = [
        model_set_id
        for model_set_id in selected_model_sets
        if model_set_id in _MODEL_SETS_BY_ID and not _MODEL_SETS_BY_ID[model_set_id].bootstrap_supported
    ]

    template_policy = build_runpod_template_policy()
    session_policy = build_runpod_bootstrap_session_policy(normalized_profile or None)
    checks = RunPodModelBootstrapChecks(
        explicit_selection_recorded=True,
        only_requested_sets_selected=selected_model_sets == expected_selected_ids,
        profile_selection_recorded=normalized_profile is not None,
        no_global_default_download_all=not download_all,
        download_all_requested=bool(download_all),
        comfy_models_root_present=resolved_comfy_models_root.exists(),
        ephemeral_session_policy_recorded=session_policy.mode == "ephemeral_zip_pod",
    )

    issues: list[str] = []
    recommended_actions: list[str] = []
    if unsupported_selected_ids:
        issues.append(
            "Unsupported Frontier research model sets were selected for bootstrap: "
            + ", ".join(unsupported_selected_ids)
        )
    if legacy_alias:
        recommended_actions.append(
            f"Legacy profile '{legacy_alias}' was mapped to the single Frontier profile; update scripts to --profile frontier."
        )
    if download_all:
        recommended_actions.append(
            "download_all selected every bootstrap-supported Frontier model set; recover outputs before Pod termination."
        )
    elif selected_model_sets:
        recommended_actions.append(
            "Bootstrap will fetch the selected Frontier model sets; recover outputs before Pod termination."
        )
    else:
        recommended_actions.append(
            "No model set was selected by the contract builder; pass --profile frontier or direct --download-* flags."
        )
    recommended_actions.append(
        "Run on RTX PRO 6000 96GB with 80GB container disk and 400GB volume disk; use 500GB volume disk when Full Frontier plus Qwen judge is enabled."
    )
    recommended_actions.append(
        "Keep Network Volume and persistent model cache disabled; recover outputs to external/local storage before termination."
    )
    if template_policy.prewarmed_image_candidate:
        recommended_actions.append(
            "A runtime-prewarmed image candidate is recorded; still upload DreamCatcher.zip and validate outputs/evidence before termination."
        )
    else:
        recommended_actions.append(
            "Use the official RunPod ComfyUI image until RTX PRO 6000 smoke evidence justifies a private runtime-prewarmed image."
        )
    frontier_research_model_sets = [
        item.model_set_id
        for item in MODEL_SET_REGISTRY
        if not item.bootstrap_supported or item.integration_status != "ready"
    ]

    ok = (
        checks.explicit_selection_recorded
        and checks.only_requested_sets_selected
        and checks.ephemeral_session_policy_recorded
        and not unsupported_selected_ids
    )
    return RunPodModelBootstrapContract(
        created_at=utc_now_iso(),
        workspace_root=str(resolved_workspace_root),
        app_root=str(resolved_app_root),
        comfy_root=str(resolved_comfy_root),
        comfy_models_root=str(resolved_comfy_models_root),
        artifact_path=str(resolved_artifact_path),
        download_scope_status=download_scope_status,
        model_profile=normalized_profile,
        legacy_profile_alias=legacy_alias,
        profile_metadata=profile_metadata,
        selected_model_sets=selected_model_sets,
        selected_download_flags=selected_download_flags,
        frontier_research_model_sets=frontier_research_model_sets,
        available_model_sets=list(MODEL_SET_REGISTRY),
        available_model_profiles=list(MODEL_PROFILE_REGISTRY),
        template_policy=template_policy,
        bootstrap_session_policy=session_policy,
        checks=checks,
        issues=issues,
        recommended_actions=recommended_actions,
        ok=ok,
    )


def write_runpod_model_bootstrap_contract(
    *,
    artifact_path: str | Path | None = None,
    **kwargs: Any,
) -> RunPodModelBootstrapContract:
    contract = build_runpod_model_bootstrap_contract(artifact_path=artifact_path, **kwargs)
    path = Path(contract.artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return contract


def load_runpod_model_bootstrap_contract(path: str | Path) -> RunPodModelBootstrapContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunPodModelBootstrapContract(**payload)
