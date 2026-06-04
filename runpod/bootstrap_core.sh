#!/usr/bin/env bash
set -Eeuo pipefail

# DreamCatcher bootstrap core (RunPod ephemeral pod optimized)
# Usually invoked through /workspace/DreamCatcher/runpod/bootstrap.sh
# Direct usage:
#   bash /workspace/DreamCatcher/runpod/bootstrap_core.sh --profile frontier
#   bash /workspace/DreamCatcher/runpod/bootstrap_core.sh --download-qwen

export HF_TOKEN="${HF_TOKEN:-}"
export HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-1}"
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"
export PIP_ROOT_USER_ACTION="${PIP_ROOT_USER_ACTION:-ignore}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/opt/dreamcatcher-cache/pip}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/opt/dreamcatcher-cache/uv}"
export npm_config_cache="${npm_config_cache:-/opt/dreamcatcher-cache/npm}"
export DC_MODEL_PROFILE="${DC_MODEL_PROFILE:-}"
export DC_SERVE_FRONTEND="${DC_SERVE_FRONTEND:-}"
export DC_COMFY_PUBLIC="${DC_COMFY_PUBLIC:-}"
export DC_PREWARMED_IMAGE="${DC_PREWARMED_IMAGE:-}"
export DC_QWEN_JUDGE_MODEL="${DC_QWEN_JUDGE_MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
export DC_QWEN_JUDGE_MODEL_REPO="${DC_QWEN_JUDGE_MODEL_REPO:-Qwen/Qwen3.6-35B-A3B-FP8}"
export DC_QWEN_JUDGE_MODEL_REVISION="${DC_QWEN_JUDGE_MODEL_REVISION:-61a5771f218894aaacf97551e24a25b866750fc2}"
export DC_QWEN_JUDGE_BASE_URL="${DC_QWEN_JUDGE_BASE_URL:-http://127.0.0.1:8011/v1}"

WORKSPACE_ROOT="/workspace"
APP_ZIP_SEEDED="${WORKSPACE_ROOT}/DreamCatcher_seeded.zip"
APP_ZIP_BASE="${WORKSPACE_ROOT}/DreamCatcher.zip"
APP_ROOT="${WORKSPACE_ROOT}/DreamCatcher"
DC_ROOT="${APP_ROOT}/app"
BACKEND_ROOT="${DC_ROOT}/backend"
SEED_ROOT="${APP_ROOT}/seed_bundle"
REAL_COMFY_ROOT="/workspace/runpod-slim/ComfyUI"
LINK_COMFY_ROOT="/workspace/ComfyUI"
RAWPREP_ROOT="${RAWPREP_ROOT:-/workspace/rawprep}"
RAWPREP_TMP="${RAWPREP_TMP:-/workspace/.rawprep_tmp}"
RAWPREP_OUT="${RAWPREP_OUT:-/workspace/DreamCatcher/outputs}"
RUNPOD_TEMPLATE_CONSOLE_LABEL="${RUNPOD_TEMPLATE_CONSOLE_LABEL:-ComfyUI - CUDA 12.8}"
RUNPOD_TEMPLATE_PRIMARY_IMAGE="${RUNPOD_TEMPLATE_PRIMARY_IMAGE:-runpod/comfyui:1.4.1-cuda12.8}"
RUNPOD_TEMPLATE_FALLBACK_IMAGE="${RUNPOD_TEMPLATE_FALLBACK_IMAGE:-runpod/comfyui:1.3.0-cuda12.8}"
RUNPOD_TEMPLATE_FALLBACK_ALIAS="${RUNPOD_TEMPLATE_FALLBACK_ALIAS:-runpod/comfyui:cuda12.8}"
RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE="${RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE:-runpod/comfyui:1.4.1-cuda13.0}"
RUNPOD_TEMPLATE_PREWARMED_IMAGE="${RUNPOD_TEMPLATE_PREWARMED_IMAGE:-}"
PYTHON_BIN="python"
LOG_PREFIX="[DreamCatcher]"
LOG_FILE="${WORKSPACE_ROOT}/dreamcatcher_bootstrap.log"
BACKEND_LOG_FILE="${WORKSPACE_ROOT}/dreamcatcher_backend.log"
BACKEND_URL="http://127.0.0.1:8000/health"
BOOTSTRAP_SUMMARY_PATH="${APP_ROOT}/app/runtime/bootstrap_summary.json"
STORAGE_CONTRACT_PATH="${APP_ROOT}/app/runtime/runpod_storage_contract.json"
MODEL_BOOTSTRAP_CONTRACT_PATH="${APP_ROOT}/app/runtime/runpod_model_bootstrap_contract.json"
CUSTOM_NODE_CONTRACT_PATH="${APP_ROOT}/app/runtime/runpod_custom_node_contract.json"
PRIVATE_CONFIG_PATH="${APP_ROOT}/app/runtime/private_config.json"
QWEN_JUDGE_MODEL_PATH="${DC_QWEN_JUDGE_MODEL_PATH:-${APP_ROOT}/models/qwen_judge/Qwen3.6-35B-A3B-FP8}"
export DC_QWEN_JUDGE_MODEL_PATH="$QWEN_JUDGE_MODEL_PATH"

MODEL_PROFILE_CLI=""
REQUESTED_DOWNLOAD_BIREFNET=0
REQUESTED_DOWNLOAD_QWEN=0
REQUESTED_DOWNLOAD_QWEN_2512=0
REQUESTED_DOWNLOAD_QWEN_JUDGE=0
REQUESTED_DOWNLOAD_FLUX2_DEV=0
REQUESTED_DOWNLOAD_KLEIN=0
REQUESTED_DOWNLOAD_FILL=0
REQUESTED_DOWNLOAD_QWEN_LAYERED=0
REQUESTED_DOWNLOAD_Z_IMAGE=0
REQUESTED_DOWNLOAD_OMNIGEN2=0
DOWNLOAD_BIREFNET=0
DOWNLOAD_QWEN=0
DOWNLOAD_QWEN_2512=0
DOWNLOAD_QWEN_JUDGE=0
DOWNLOAD_FLUX2_DEV=0
DOWNLOAD_KLEIN=0
DOWNLOAD_FILL=0
DOWNLOAD_QWEN_LAYERED=0
DOWNLOAD_Z_IMAGE=0
DOWNLOAD_OMNIGEN2=0
DOWNLOAD_ALL=0
SKIP_PIP_REFRESH=0
SKIP_SETUP=0
FORCE_STAGING_REFRESH=0
FORCE_RESEED=0

load_private_runtime_config() {
  [[ -f "$PRIVATE_CONFIG_PATH" ]] || return 0

  local reader=""
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    reader="$PYTHON_BIN"
  elif command -v python >/dev/null 2>&1; then
    reader="python"
  elif command -v python3 >/dev/null 2>&1; then
    reader="python3"
  else
    return 0
  fi

  eval "$("$reader" - "$PRIVATE_CONFIG_PATH" <<'PY'
import json
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    payload = {}

if not isinstance(payload, dict):
    payload = {}

keys = (
    "HF_TOKEN",
    "HF_XET_HIGH_PERFORMANCE",
    "HF_HOME",
    "PIP_CACHE_DIR",
    "UV_CACHE_DIR",
    "npm_config_cache",
    "RUNPOD_API_TOKEN",
    "RUNPOD_API_KEY",
    "RUNPOD_POD_ID",
    "RUNPOD_BACKEND_URL",
    "RUNPOD_FRONTEND_URL",
    "RUNPOD_BACKEND_INTERNAL_PORT",
    "RUNPOD_FRONTEND_INTERNAL_PORT",
    "RUNPOD_BACKEND_HEALTH_PATH",
    "RUNPOD_API_BASE_URL",
    "RUNPOD_API_TIMEOUT_SECONDS",
    "RUNPOD_TEMPLATE_CONSOLE_LABEL",
    "RUNPOD_TEMPLATE_PRIMARY_IMAGE",
    "RUNPOD_TEMPLATE_FALLBACK_IMAGE",
    "RUNPOD_TEMPLATE_FALLBACK_ALIAS",
    "RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE",
    "RUNPOD_TEMPLATE_PREWARMED_IMAGE",
    "DC_MODEL_PROFILE",
    "DC_SERVE_FRONTEND",
    "DC_COMFY_PUBLIC",
    "DC_PREWARMED_IMAGE",
    "DC_QWEN_JUDGE_MODEL",
    "DC_QWEN_JUDGE_MODEL_REPO",
    "DC_QWEN_JUDGE_MODEL_REVISION",
    "DC_QWEN_JUDGE_MODEL_PATH",
    "DC_QWEN_JUDGE_BASE_URL",
)

for key in keys:
    value = payload.get(key)
    if value in (None, ""):
        continue
    quoted = shlex.quote(str(value))
    print(f'if [[ -z "${{{key}:-}}" ]]; then export {key}={quoted}; fi')
PY
  )"
}

usage() {
  cat <<USAGE
DreamCatcher bootstrap core

Options:
  --profile frontier      Select the single Frontier Studio profile (default: DC_MODEL_PROFILE or frontier)
  --profile core|pro|labs Legacy aliases for frontier; kept for one release with a warning
  --download-birefnet    Download BiRefNet-DIS5K cutout model to Pod
  --download-qwen        Download Qwen Image Edit 2511 model set to Pod
  --download-qwen-2512   Download Qwen Image 2512 model set to Pod
  --download-qwen-judge  Download Qwen3.6-35B-A3B-FP8 local judge to Pod
  --download-flux2-dev   Download FLUX.2 Dev model set to Pod
  --download-klein       Download FLUX.2 Klein 9B model set to Pod
  --download-fill        Download FLUX.1 Fill model set to Pod
  --download-qwen-layered Download Qwen Image Layered model set to Pod
  --download-z-image     Download Z-Image Turbo model set to Pod
  --download-omnigen2    Download OmniGen2 model set to Pod
  --download-all         Download all supported model sets
  --skip-pip-refresh     Skip ComfyUI requirements/template refresh step
  --skip-setup           Skip app/scripts/setup.sh execution
  --force-staging        Recreate seed_bundle/staging_templates guidance even if api_workflows already seeded
  --force-reseed         Overwrite an existing /workspace/DreamCatcher from the uploaded zip
  -h, --help             Show this help

Prewarm environment:
  RUNPOD_TEMPLATE_PREWARMED_IMAGE records the private runtime image used by the RunPod template
  DC_PREWARMED_IMAGE=runtime-v1 marks that the Pod booted from DreamCatcher's runtime prewarm image
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      [[ $# -ge 2 ]] || { echo "$LOG_PREFIX --profile requires frontier"; exit 1; }
      MODEL_PROFILE_CLI="$2"
      shift
      ;;
    --profile=*)
      MODEL_PROFILE_CLI="${1#*=}"
      ;;
    --download-birefnet) DOWNLOAD_BIREFNET=1; REQUESTED_DOWNLOAD_BIREFNET=1 ;;
    --download-qwen) DOWNLOAD_QWEN=1; REQUESTED_DOWNLOAD_QWEN=1 ;;
    --download-qwen-2512) DOWNLOAD_QWEN_2512=1; REQUESTED_DOWNLOAD_QWEN_2512=1 ;;
    --download-qwen-judge) DOWNLOAD_QWEN_JUDGE=1; REQUESTED_DOWNLOAD_QWEN_JUDGE=1 ;;
    --download-flux2-dev) DOWNLOAD_FLUX2_DEV=1; REQUESTED_DOWNLOAD_FLUX2_DEV=1 ;;
    --download-klein) DOWNLOAD_KLEIN=1; REQUESTED_DOWNLOAD_KLEIN=1 ;;
    --download-fill) DOWNLOAD_FILL=1; REQUESTED_DOWNLOAD_FILL=1 ;;
    --download-qwen-layered) DOWNLOAD_QWEN_LAYERED=1; REQUESTED_DOWNLOAD_QWEN_LAYERED=1 ;;
    --download-z-image) DOWNLOAD_Z_IMAGE=1; REQUESTED_DOWNLOAD_Z_IMAGE=1 ;;
    --download-omnigen2) DOWNLOAD_OMNIGEN2=1; REQUESTED_DOWNLOAD_OMNIGEN2=1 ;;
    --download-all) DOWNLOAD_ALL=1 ;;
    --skip-pip-refresh) SKIP_PIP_REFRESH=1 ;;
    --skip-setup) SKIP_SETUP=1 ;;
    --force-staging) FORCE_STAGING_REFRESH=1 ;;
    --force-reseed) FORCE_RESEED=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "$LOG_PREFIX unknown option: $1"; usage; exit 1 ;;
  esac
  shift
done

require_hf_token_if_needed() {
  if [[ "$DOWNLOAD_QWEN" -eq 0 && "$DOWNLOAD_QWEN_2512" -eq 0 && "$DOWNLOAD_QWEN_JUDGE" -eq 0 && "$DOWNLOAD_FLUX2_DEV" -eq 0 && "$DOWNLOAD_KLEIN" -eq 0 && "$DOWNLOAD_FILL" -eq 0 && "$DOWNLOAD_QWEN_LAYERED" -eq 0 && "$DOWNLOAD_Z_IMAGE" -eq 0 && "$DOWNLOAD_OMNIGEN2" -eq 0 ]]; then
    return
  fi

  if [[ -z "$HF_TOKEN" ]]; then
    cat >&2 <<'TXT'
[DreamCatcher] ERROR: model download flags require HF_TOKEN.
Set it first in the RunPod terminal, for example:
  export HF_TOKEN=hf_xxx
Then rerun bootstrap with the desired --download-* flags.
TXT
    exit 1
  fi
}

log() {
  echo "$LOG_PREFIX $*" | tee -a "$LOG_FILE"
}

fail() {
  echo "$LOG_PREFIX ERROR: $*" | tee -a "$LOG_FILE" >&2
  exit 1
}

apply_model_profile() {
  if [[ -n "$MODEL_PROFILE_CLI" ]]; then
    export DC_MODEL_PROFILE="$MODEL_PROFILE_CLI"
  fi
  DC_MODEL_PROFILE="${DC_MODEL_PROFILE:-frontier}"
  DC_SERVE_FRONTEND="${DC_SERVE_FRONTEND:-1}"
  DC_COMFY_PUBLIC="${DC_COMFY_PUBLIC:-0}"

  case "$DC_MODEL_PROFILE" in
    core|pro|labs)
      log "legacy model profile '${DC_MODEL_PROFILE}' maps to the single Frontier Studio profile"
      DC_MODEL_PROFILE="frontier"
      ;&
    frontier)
      DOWNLOAD_BIREFNET=1
      DOWNLOAD_QWEN=1
      DOWNLOAD_QWEN_2512=1
      DOWNLOAD_QWEN_JUDGE=1
      DOWNLOAD_FLUX2_DEV=1
      DOWNLOAD_KLEIN=1
      DOWNLOAD_FILL=1
      DOWNLOAD_QWEN_LAYERED=1
      DOWNLOAD_Z_IMAGE=1
      DOWNLOAD_OMNIGEN2=1
      ;;
    "")
      ;;
    *)
      fail "unknown DC_MODEL_PROFILE=${DC_MODEL_PROFILE}; expected frontier"
      ;;
  esac

  if [[ "$DOWNLOAD_ALL" -eq 1 ]]; then
    DOWNLOAD_BIREFNET=1
    DOWNLOAD_QWEN=1
    DOWNLOAD_QWEN_2512=1
    DOWNLOAD_QWEN_JUDGE=1
    DOWNLOAD_FLUX2_DEV=1
    DOWNLOAD_KLEIN=1
    DOWNLOAD_FILL=1
    DOWNLOAD_QWEN_LAYERED=1
    DOWNLOAD_Z_IMAGE=1
    DOWNLOAD_OMNIGEN2=1
  fi

  QWEN_JUDGE_MODEL_PATH="${DC_QWEN_JUDGE_MODEL_PATH:-${APP_ROOT}/models/qwen_judge/Qwen3.6-35B-A3B-FP8}"
  export DC_QWEN_JUDGE_MODEL_PATH="$QWEN_JUDGE_MODEL_PATH"
  export DC_MODEL_PROFILE DC_SERVE_FRONTEND DC_COMFY_PUBLIC DC_QWEN_JUDGE_MODEL DC_QWEN_JUDGE_MODEL_REPO DC_QWEN_JUDGE_MODEL_REVISION DC_QWEN_JUDGE_MODEL_PATH DC_QWEN_JUDGE_BASE_URL
  log "model profile: ${DC_MODEL_PROFILE:-manual} (serve_frontend=${DC_SERVE_FRONTEND}, comfy_public=${DC_COMFY_PUBLIC})"
}

ensure_python() {
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    fail "python or python3 not found"
  fi
  log "python: $($PYTHON_BIN --version 2>&1)"
}

sha256_of() {
  "$PYTHON_BIN" - "$1" <<'PY'
from pathlib import Path
import hashlib
import sys

path = Path(sys.argv[1])
digest = hashlib.sha256()
with path.open("rb") as fh:
    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
}

pick_comfy_python() {
  local candidates=(
    "$REAL_COMFY_ROOT/.venv/bin/python"
    "$REAL_COMFY_ROOT/.venv-cu130/bin/python"
    "$REAL_COMFY_ROOT/.venv-cu128/bin/python"
  )
  local candidate=""
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  candidate="$(find "$REAL_COMFY_ROOT" -maxdepth 2 -path '*/bin/python' -type f 2>/dev/null | head -n 1 || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi
  echo "$PYTHON_BIN"
}

official_comfy_runtime_is_ready() {
  local comfy_python="$1"
  "$comfy_python" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required_modules = [
    "torch",
    "aiohttp",
    "yaml",
    "PIL",
    "numpy",
    "safetensors",
    "simpleeval",
]

missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
sys.exit(0 if not missing else 1)
PY
  "$comfy_python" -m pip check >/dev/null 2>&1
}

find_workflow_template_dir() {
  local comfy_python="$1"
  "$comfy_python" - <<'PY'
from importlib.util import find_spec
from pathlib import Path
import sys

spec = find_spec("comfyui_workflow_templates_media_image")
if spec is None:
    raise SystemExit(1)

candidates = []
if spec.submodule_search_locations:
    candidates.extend(Path(path).resolve() / "templates" for path in spec.submodule_search_locations)
elif spec.origin:
    candidates.append(Path(spec.origin).resolve().parent / "templates")

for candidate in candidates:
    if candidate.is_dir():
        print(candidate)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

extract_zip_to_workspace() {
  local zip_path="$1"
  if command -v unzip >/dev/null 2>&1; then
    unzip -oq "$zip_path" -d "$WORKSPACE_ROOT"
    return 0
  fi

  log "unzip not found; using Python zipfile fallback"
  "$PYTHON_BIN" - "$zip_path" "$WORKSPACE_ROOT" <<'PY'
from pathlib import Path
import sys
import zipfile

zip_path = Path(sys.argv[1])
workspace_root = Path(sys.argv[2])
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(workspace_root)
PY
}

wipe_existing_app_root() {
  if [[ ! -e "$APP_ROOT" ]]; then
    return 0
  fi
  log "removing existing ${APP_ROOT} before reseed"
  rm -rf "$APP_ROOT"
}

prepare_workspace() {
  cd "$WORKSPACE_ROOT"

  local zip_to_use=""
  if [[ -f "$APP_ZIP_BASE" ]]; then
    zip_to_use="$APP_ZIP_BASE"
  elif [[ -f "$APP_ZIP_SEEDED" ]]; then
    zip_to_use="$APP_ZIP_SEEDED"
  fi

  if [[ -n "$zip_to_use" ]]; then
    mkdir -p "$APP_ROOT"
    local stamp_file="${APP_ROOT}/.seeded_zip.sha256"
    local new_sha current_sha=""
    new_sha="$(sha256_of "$zip_to_use")"
    [[ -f "$stamp_file" ]] && current_sha="$(cat "$stamp_file" 2>/dev/null || true)"

    if [[ "$FORCE_RESEED" -eq 1 ]]; then
      wipe_existing_app_root
      log "force reseed requested; unpacking $(basename "$zip_to_use") into a clean workspace"
      extract_zip_to_workspace "$zip_to_use"
      echo "$new_sha" > "$stamp_file"
    elif [[ -d "$APP_ROOT/app" && "$new_sha" == "$current_sha" ]]; then
      log "seeded zip unchanged; skipping unzip"
    elif [[ -d "$APP_ROOT/app" && -z "$current_sha" ]]; then
      log "workspace already present without stamp; trusting existing files and recording zip hash"
      echo "$new_sha" > "$stamp_file"
    elif [[ -d "$APP_ROOT/app" ]]; then
      log "workspace already present and zip hash changed; keeping existing files. Use --force-reseed to overwrite."
    else
      log "unpacking $(basename "$zip_to_use")"
      extract_zip_to_workspace "$zip_to_use"
      echo "$new_sha" > "$stamp_file"
    fi
  else
    log "zip not found; assuming ${APP_ROOT} already exists"
  fi

  [[ -d "$APP_ROOT/app" ]] || fail "${APP_ROOT}/app not found after workspace preparation."
}

normalize_comfy_root() {
  [[ -d "$REAL_COMFY_ROOT" ]] || fail "real ComfyUI root not found at $REAL_COMFY_ROOT"

  if [[ -d "$LINK_COMFY_ROOT" && ! -L "$LINK_COMFY_ROOT" ]]; then
    mv "$LINK_COMFY_ROOT" "${LINK_COMFY_ROOT}_wrongroot_$(date +%Y%m%d_%H%M%S)"
  fi
  ln -sfn "$REAL_COMFY_ROOT" "$LINK_COMFY_ROOT"

  export DC_ROOT SEED_ROOT COMFY_ROOT="$REAL_COMFY_ROOT" HF_HOME HF_TOKEN HF_XET_HIGH_PERFORMANCE PYTHON_BIN
  export RUNPOD_TEMPLATE_PREWARMED_IMAGE
  export PIP_CACHE_DIR UV_CACHE_DIR npm_config_cache
  export DC_MODEL_PROFILE DC_SERVE_FRONTEND DC_COMFY_PUBLIC DC_PREWARMED_IMAGE

  log "DC_ROOT=$DC_ROOT"
  log "SEED_ROOT=$SEED_ROOT"
  log "COMFY_ROOT=$COMFY_ROOT"
  log "LINK_COMFY_ROOT=$(readlink -f "$LINK_COMFY_ROOT")"
  if [[ -n "$DC_PREWARMED_IMAGE" ]]; then
    log "prewarmed image marker: $DC_PREWARMED_IMAGE"
  fi
}

seed_api_workflows_are_real() {
  local dir="${SEED_ROOT}/api_workflows"
  [[ -d "$dir" ]] || return 1

  local files=(
    "$dir/qwen_precision_edit.api.json"
    "$dir/flux2_dev_compose.api.json"
    "$dir/flux2_klein_preview.api.json"
    "$dir/flux_fill_replace.api.json"
  )

  local file=""
  for file in "${files[@]}"; do
    [[ -s "$file" ]] || return 1
    if grep -qiE 'placeholder|replace me|todo' "$file" 2>/dev/null; then
      return 1
    fi
  done
  return 0
}

refresh_comfy_runtime() {
  if [[ "$SKIP_PIP_REFRESH" -eq 1 ]]; then
    log "skipping pip refresh by option"
    return
  fi

  cd "$REAL_COMFY_ROOT"
  mkdir -p "$WORKSPACE_ROOT/.dreamcatcher_cache"
  local req_hash_file="$WORKSPACE_ROOT/.dreamcatcher_cache/comfy_requirements.sha256"
  local req_hash=""
  local comfy_python=""
  comfy_python="$(pick_comfy_python)"
  req_hash="$(sha256_of requirements.txt)"

  if [[ -f "$req_hash_file" && "$(cat "$req_hash_file" 2>/dev/null || true)" == "$req_hash" ]]; then
    log "ComfyUI requirements unchanged; skipping requirements reinstall"
  elif official_comfy_runtime_is_ready "$comfy_python"; then
    log "official ComfyUI runtime already looks healthy; recording requirements hash without reinstall"
    echo "$req_hash" > "$req_hash_file"
  else
    log "refreshing ComfyUI requirements with ${comfy_python}"
    "$comfy_python" -m ensurepip --upgrade >/dev/null 2>&1 || true
    "$comfy_python" -m pip install -r requirements.txt
    "$comfy_python" -m pip install simpleeval
    echo "$req_hash" > "$req_hash_file"
  fi

  if seed_api_workflows_are_real; then
    log "real API workflows already seeded; skipping workflow-template package refresh"
    return
  fi

  local tmpl_stamp="$WORKSPACE_ROOT/.dreamcatcher_cache/workflow_templates.ok"
  if [[ -f "$tmpl_stamp" ]]; then
    log "workflow template packages already prepared; skipping"
    return
  fi

  log "installing workflow-template packages for staging export only"
  "$comfy_python" -m pip install -U \
    comfyui-workflow-templates \
    comfyui-workflow-templates-core \
    comfyui-workflow-templates-media-image \
    comfyui-workflow-templates-media-api \
    comfyui-workflow-templates-media-video \
    comfyui-workflow-templates-media-other
  touch "$tmpl_stamp"
}

restart_comfy() {
  local comfy_python=""
  comfy_python="$(pick_comfy_python)"
  cd "$REAL_COMFY_ROOT"
  pkill -f "python.*main.py.*8188" || true
  sleep 3
  nohup "$comfy_python" main.py --listen 0.0.0.0 --port 8188 > /workspace/runpod-slim/comfyui.log 2>&1 &

  log "waiting for ComfyUI"
  for i in $(seq 1 90); do
    if curl -fsS http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
      log "ComfyUI ready"
      return 0
    fi
    sleep 2
  done

  tail -n 120 /workspace/runpod-slim/comfyui.log || true
  fail "ComfyUI did not become ready."
}

run_setup() {
  if [[ "$SKIP_SETUP" -eq 1 ]]; then
    log "skipping setup.sh by option"
    return
  fi

  cd "$DC_ROOT"
  log "running setup.sh"
  bash scripts/setup.sh 2>&1 | tee -a "$LOG_FILE"
}

prepare_staging_templates() {
  local staging_dir="${SEED_ROOT}/staging_templates"
  local comfy_python=""
  local src_base_img=""

  if seed_api_workflows_are_real && [[ "$FORCE_STAGING_REFRESH" -ne 1 ]]; then
    log "real API workflows already present; skipping staging template guidance"
    return
  fi

  comfy_python="$(pick_comfy_python)"
  src_base_img="$(find_workflow_template_dir "$comfy_python" || true)"

  mkdir -p "$staging_dir"
  if [[ -z "$src_base_img" || ! -d "$src_base_img" ]]; then
    log "workflow template package path not found; skipping staging template copy"
    return
  fi
  log "copying official templates to ${staging_dir}"

  cp "$src_base_img/image_qwen_image_edit_2511.json" "$staging_dir/" || true
  cp "$src_base_img/image_flux2_fp8.json" "$staging_dir/" || true
  cp "$src_base_img/image_flux2_klein_image_edit_9b_distilled.json" "$staging_dir/" || true
  cp "$src_base_img/flux_fill_inpaint_example.json" "$staging_dir/" || true

  log "staging templates prepared: $staging_dir"
  ls -lh "$staging_dir" || true
}

ensure_model_dirs() {
  mkdir -p "$REAL_COMFY_ROOT/models/vae"
  mkdir -p "$REAL_COMFY_ROOT/models/loras"
  mkdir -p "$REAL_COMFY_ROOT/models/diffusion_models"
  mkdir -p "$REAL_COMFY_ROOT/models/text_encoders"
  mkdir -p "$REAL_COMFY_ROOT/models/checkpoints"
  mkdir -p "$REAL_COMFY_ROOT/models/BiRefNet"
  mkdir -p "$(dirname "$QWEN_JUDGE_MODEL_PATH")"
}

download_if_missing() {
  local out="$1"
  local url="$2"
  local tmp="${out}.part"
  local wget_args=(-c --tries=20 --waitretry=2 -O "$tmp")
  if [[ -n "$HF_TOKEN" ]]; then
    wget_args+=("--header=Authorization: Bearer $HF_TOKEN")
  fi

  if [[ -s "$out" ]]; then
    log "exists: $out"
    return
  fi
  log "downloading $(basename "$out")"
  wget "${wget_args[@]}" "$url"
  mv -f "$tmp" "$out"
}

ensure_huggingface_hub() {
  if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import huggingface_hub  # noqa: F401
PY
  then
    return
  fi
  log "installing huggingface_hub for Qwen judge snapshot download"
  "$PYTHON_BIN" -m pip install --upgrade "huggingface_hub>=0.36.0,<1.0.0"
}

download_hf_snapshot() {
  local repo="$1"
  local revision="$2"
  local local_dir="$3"
  local sentinel="$local_dir/config.json"
  if [[ -s "$sentinel" ]]; then
    log "exists: $local_dir"
    return
  fi
  ensure_huggingface_hub
  mkdir -p "$local_dir"
  log "downloading Hugging Face snapshot ${repo}@${revision}"
  "$PYTHON_BIN" - "$repo" "$revision" "$local_dir" <<'PY'
import os
import sys
from huggingface_hub import snapshot_download

repo_id, revision, local_dir = sys.argv[1:4]
snapshot_download(
    repo_id=repo_id,
    revision=revision,
    local_dir=local_dir,
    local_dir_use_symlinks=False,
    token=os.environ.get("HF_TOKEN") or None,
)
PY
}

download_birefnet() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/BiRefNet/model.safetensors" \
    "https://huggingface.co/ZhengPeng7/BiRefNet-DIS5K/resolve/8d0803f8dee999ceb31c20092bb53b6021aeec13/model.safetensors"
}

download_qwen() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/qwen_image_vae.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/vae/qwen_image_vae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors" \
    "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/d74eba145674fd7e31b949324e148e21e7118abd/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/qwen_image_edit_2511_bf16.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/83ae44f23af827155718b906c7dcc195a37c60b4/split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
}

download_qwen_2512() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/loras/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors" \
    "https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/a52649c9d0f6e1a248bff13f0df33bb8a2abdb52/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/qwen_image_vae.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/vae/qwen_image_vae.safetensors"
}

download_qwen_judge() {
  ensure_model_dirs
  download_hf_snapshot \
    "$DC_QWEN_JUDGE_MODEL_REPO" \
    "$DC_QWEN_JUDGE_MODEL_REVISION" \
    "$QWEN_JUDGE_MODEL_PATH"
}

download_flux2_dev() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/flux2-vae.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-dev/resolve/03d6521e6f6a47396b3f951cbea50f7e6c2f482e/split_files/vae/flux2-vae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/flux2_dev_fp8mixed.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-dev/resolve/03d6521e6f6a47396b3f951cbea50f7e6c2f482e/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/mistral_3_small_flux2_fp8.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-dev/resolve/03d6521e6f6a47396b3f951cbea50f7e6c2f482e/split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/loras/Flux2TurboComfyv2.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-dev/resolve/03d6521e6f6a47396b3f951cbea50f7e6c2f482e/split_files/loras/Flux2TurboComfyv2.safetensors"
}

download_klein() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/flux2-vae.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/flux-2-klein-9b-fp8.safetensors" \
    "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/902d9d510b51533e07729f19211414a3648b77d2/flux-2-klein-9b-fp8.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_3_8b_fp8mixed.safetensors" \
    "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors"
}

download_fill() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/ae.safetensors" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/ae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/flux1-fill-dev.safetensors" \
    "https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev/resolve/main/flux1-fill-dev.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/clip_l.safetensors" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/t5xxl_fp16.safetensors" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors"
}

download_qwen_layered() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/qwen_image_layered_fp8mixed.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/5d93d59c0e34488b94dee03ad33337f7ee997f97/split_files/diffusion_models/qwen_image_layered_fp8mixed.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/qwen_image_layered_vae.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image-Layered_ComfyUI/resolve/5d93d59c0e34488b94dee03ad33337f7ee997f97/split_files/vae/qwen_image_layered_vae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/c232bcb51c1523899c62d6dcaa960b2627668de5/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
}

download_z_image() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/z_image_turbo_nvfp4.safetensors" \
    "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/2f862278568d3f0a83167a16e5f11094da6dee72/split_files/diffusion_models/z_image_turbo_nvfp4.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_3_4b_fp8_mixed.safetensors" \
    "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/2f862278568d3f0a83167a16e5f11094da6dee72/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/ae.safetensors" \
    "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/2f862278568d3f0a83167a16e5f11094da6dee72/split_files/vae/ae.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/loras/z_image_turbo_distill_patch_lora_bf16.safetensors" \
    "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/2f862278568d3f0a83167a16e5f11094da6dee72/split_files/loras/z_image_turbo_distill_patch_lora_bf16.safetensors"
}

download_omnigen2() {
  ensure_model_dirs
  download_if_missing \
    "$REAL_COMFY_ROOT/models/diffusion_models/omnigen2_fp16.safetensors" \
    "https://huggingface.co/Comfy-Org/Omnigen2_ComfyUI_repackaged/resolve/a81dac8cc06b983eb865d1c345fa12c00616fb7d/split_files/diffusion_models/omnigen2_fp16.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/text_encoders/qwen_2.5_vl_fp16.safetensors" \
    "https://huggingface.co/Comfy-Org/Omnigen2_ComfyUI_repackaged/resolve/a81dac8cc06b983eb865d1c345fa12c00616fb7d/split_files/text_encoders/qwen_2.5_vl_fp16.safetensors"
  download_if_missing \
    "$REAL_COMFY_ROOT/models/vae/ae.safetensors" \
    "https://huggingface.co/Comfy-Org/Omnigen2_ComfyUI_repackaged/resolve/a81dac8cc06b983eb865d1c345fa12c00616fb7d/split_files/vae/ae.safetensors"
}

ensure_backend_requirements() {
  mkdir -p "$WORKSPACE_ROOT/.dreamcatcher_cache"
  local req_hash_file="$WORKSPACE_ROOT/.dreamcatcher_cache/backend_requirements.sha256"
  local requirements_file="$BACKEND_ROOT/requirements-lock.txt"
  local req_hash=""
  if [[ ! -f "$requirements_file" ]]; then
    requirements_file="$BACKEND_ROOT/requirements.txt"
  fi
  req_hash="$(sha256_of "$requirements_file")"

  if [[ -f "$req_hash_file" && "$(cat "$req_hash_file" 2>/dev/null || true)" == "$req_hash" ]] && \
     "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required_modules = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "requests",
    "yaml",
    "httpx",
    "PIL",
    "numpy",
    "tifffile",
    "rawpy",
    "cv2",
    "multipart",
]
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
sys.exit(0 if not missing else 1)
PY
  then
    log "backend requirements unchanged; skipping reinstall"
    return
  fi

  log "installing backend requirements"
  "$PYTHON_BIN" -m pip install -r "$requirements_file"
  echo "$req_hash" > "$req_hash_file"
}

restart_backend() {
  cd "$BACKEND_ROOT"
  pkill -f "uvicorn app.main:app" || true
  sleep 2
  nohup "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG_FILE" 2>&1 &
}

ensure_backend_running() {
  ensure_backend_requirements
  restart_backend

  log "waiting for backend"
  for i in $(seq 1 60); do
    if curl -fsS "$BACKEND_URL" >/dev/null 2>&1; then
      log "backend ready"
      return 0
    fi
    sleep 2
  done

  tail -n 120 "$BACKEND_LOG_FILE" || true
  fail "backend did not become ready."
}

log_frontend_runtime_status() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    log "node: $(node --version 2>/dev/null)"
    log "npm: $(npm --version 2>/dev/null)"
    return
  fi
  log "node/npm not found on Pod"
}

ensure_node_runtime() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    log "installing node/npm for backend-served Studio build"
    apt-get update
    apt-get install -y nodejs npm
    return
  fi
  fail "DC_SERVE_FRONTEND=1 requires node/npm to build app/frontend"
}

build_frontend_if_requested() {
  if [[ "$DC_SERVE_FRONTEND" != "1" ]]; then
    log "DC_SERVE_FRONTEND=${DC_SERVE_FRONTEND}; skipping frontend build"
    return
  fi

  local frontend_root="${DC_ROOT}/frontend"
  [[ -f "$frontend_root/package.json" ]] || fail "frontend package.json not found: $frontend_root"

  ensure_node_runtime
  log_frontend_runtime_status
  log "building Studio frontend for FastAPI static serving"
  if [[ -f "$frontend_root/package-lock.json" ]]; then
    npm ci --prefix "$frontend_root"
  else
    npm install --prefix "$frontend_root"
  fi
  npm run build --prefix "$frontend_root"
}

verify_bootstrap_runtime_contract() {
  local comfy_python=""
  comfy_python="$(pick_comfy_python)"
  local workflow_dir="${DC_ROOT}/workflows/runtime"
  local rawprep_healthcheck_path="${DC_ROOT}/runtime/rawprep_healthcheck.json"
  local single_raw_healthcheck_path="${DC_ROOT}/runtime/single_raw_healthcheck.json"
  local bootstrap_cache_root="${WORKSPACE_ROOT}/.dreamcatcher_cache"

  log "verifying bootstrap runtime contract"
  curl -fsS http://127.0.0.1:8188/system_stats >/dev/null || fail "ComfyUI healthcheck failed."
  curl -fsS "$BACKEND_URL" >/dev/null || fail "backend healthcheck failed."
  curl -fsS http://127.0.0.1:8000/api/rawprep/health >/dev/null || fail "rawprep health endpoint failed."
  PYTHONPATH="$DC_ROOT/backend" "$PYTHON_BIN" "$DC_ROOT/scripts/single_raw_healthcheck.py" \
    --out "$single_raw_healthcheck_path"
  [[ -d "$workflow_dir" ]] || fail "runtime workflow directory not found: $workflow_dir"
  find "$workflow_dir" -maxdepth 1 -type f | grep -q . || fail "runtime workflow directory is empty: $workflow_dir"
  [[ -f "$rawprep_healthcheck_path" ]] || fail "rawprep healthcheck output not found: $rawprep_healthcheck_path"
  [[ -f "$single_raw_healthcheck_path" ]] || fail "single raw healthcheck output not found: $single_raw_healthcheck_path"
  PYTHONPATH="$DC_ROOT/backend" "$PYTHON_BIN" "$DC_ROOT/scripts/runpod_storage_contract.py" \
    --workspace-root "$WORKSPACE_ROOT" \
    --app-root "$APP_ROOT" \
    --comfy-root "$REAL_COMFY_ROOT" \
    --hf-home "$HF_HOME" \
    --bootstrap-cache-root "$bootstrap_cache_root" \
    --workflow-runtime-root "$workflow_dir" \
    --workflow-staging-root "$SEED_ROOT/staging_templates" \
    --rawprep-root "$RAWPREP_ROOT" \
    --rawprep-tmp-root "$RAWPREP_TMP" \
    --output-root "$RAWPREP_OUT" \
    --out "$STORAGE_CONTRACT_PATH" \
    --require-ok >/dev/null
  [[ -f "$STORAGE_CONTRACT_PATH" ]] || fail "storage contract output not found: $STORAGE_CONTRACT_PATH"
  PYTHONPATH="$DC_ROOT/backend" "$PYTHON_BIN" "$DC_ROOT/scripts/runpod_model_bootstrap_contract.py" \
    --workspace-root "$WORKSPACE_ROOT" \
    --app-root "$APP_ROOT" \
    --comfy-root "$REAL_COMFY_ROOT" \
    --profile "$DC_MODEL_PROFILE" \
    $([[ "$REQUESTED_DOWNLOAD_BIREFNET" -eq 1 ]] && printf '%s ' --download-birefnet) \
    $([[ "$REQUESTED_DOWNLOAD_QWEN" -eq 1 ]] && printf '%s ' --download-qwen) \
    $([[ "$REQUESTED_DOWNLOAD_QWEN_2512" -eq 1 ]] && printf '%s ' --download-qwen-2512) \
    $([[ "$REQUESTED_DOWNLOAD_QWEN_JUDGE" -eq 1 ]] && printf '%s ' --download-qwen-judge) \
    $([[ "$REQUESTED_DOWNLOAD_FLUX2_DEV" -eq 1 ]] && printf '%s ' --download-flux2-dev) \
    $([[ "$REQUESTED_DOWNLOAD_KLEIN" -eq 1 ]] && printf '%s ' --download-klein) \
    $([[ "$REQUESTED_DOWNLOAD_FILL" -eq 1 ]] && printf '%s ' --download-fill) \
    $([[ "$REQUESTED_DOWNLOAD_QWEN_LAYERED" -eq 1 ]] && printf '%s ' --download-qwen-layered) \
    $([[ "$REQUESTED_DOWNLOAD_Z_IMAGE" -eq 1 ]] && printf '%s ' --download-z-image) \
    $([[ "$REQUESTED_DOWNLOAD_OMNIGEN2" -eq 1 ]] && printf '%s ' --download-omnigen2) \
    $([[ "$DOWNLOAD_ALL" -eq 1 ]] && printf '%s ' --download-all) \
    --out "$MODEL_BOOTSTRAP_CONTRACT_PATH" >/dev/null
  [[ -f "$MODEL_BOOTSTRAP_CONTRACT_PATH" ]] || fail "model bootstrap contract output not found: $MODEL_BOOTSTRAP_CONTRACT_PATH"
  PYTHONPATH="$DC_ROOT/backend" "$PYTHON_BIN" "$DC_ROOT/scripts/runpod_custom_node_contract.py" \
    --workspace-root "$WORKSPACE_ROOT" \
    --app-root "$APP_ROOT" \
    --comfy-root "$REAL_COMFY_ROOT" \
    --manifest-path "$DC_ROOT/custom_nodes/custom_node_manifest.yaml" \
    --object-info-path "$DC_ROOT/runtime/object_info.json" \
    --workflow-root "$DC_ROOT/workflows/runtime" \
    --out "$CUSTOM_NODE_CONTRACT_PATH" >/dev/null
  [[ -f "$CUSTOM_NODE_CONTRACT_PATH" ]] || fail "custom node contract output not found: $CUSTOM_NODE_CONTRACT_PATH"

  mkdir -p "$(dirname "$BOOTSTRAP_SUMMARY_PATH")"
  PYTHONPATH="$DC_ROOT/backend" "$PYTHON_BIN" "$DC_ROOT/scripts/runpod_bootstrap_summary.py" \
    --summary-out "$BOOTSTRAP_SUMMARY_PATH" \
    --workflow-dir "$workflow_dir" \
    --rawprep-healthcheck-path "$rawprep_healthcheck_path" \
    --single-raw-healthcheck-path "$single_raw_healthcheck_path" \
    --backend-url "$BACKEND_URL" \
    --comfy-root "$REAL_COMFY_ROOT" \
    --comfy-python "$comfy_python" \
    --console-label "$RUNPOD_TEMPLATE_CONSOLE_LABEL" \
    --primary-image "$RUNPOD_TEMPLATE_PRIMARY_IMAGE" \
    --fallback-pinned-image "$RUNPOD_TEMPLATE_FALLBACK_IMAGE" \
    --fallback-alias-image "$RUNPOD_TEMPLATE_FALLBACK_ALIAS" \
    --storage-contract-path "$STORAGE_CONTRACT_PATH" \
    --model-bootstrap-contract-path "$MODEL_BOOTSTRAP_CONTRACT_PATH" \
    --custom-node-contract-path "$CUSTOM_NODE_CONTRACT_PATH" >/dev/null
  log "bootstrap summary written: $BOOTSTRAP_SUMMARY_PATH"
}

print_next_steps() {
  cat <<TXT

====================================================================
DreamCatcher bootstrap complete.

Runtime status:
  - ComfyUI should be reachable at http://127.0.0.1:8188
  - Studio is served by FastAPI at http://127.0.0.1:8000 when DC_SERVE_FRONTEND=1
  - backend health is available at http://127.0.0.1:8000/health
  - SingleRaw sensor decode runtime is checked and saved to /workspace/DreamCatcher/app/runtime/single_raw_healthcheck.json
  - storage separation contract is saved to /workspace/DreamCatcher/app/runtime/runpod_storage_contract.json
  - rawprep tool readiness is reported separately; bootstrap still succeeds while dreamcatcher-raw-engine-v2 is still scaffolded
  - bootstrap contract summary is saved to /workspace/DreamCatcher/app/runtime/bootstrap_summary.json
  - active model profile: ${DC_MODEL_PROFILE}
  - recommended RunPod image: ${RUNPOD_TEMPLATE_PRIMARY_IMAGE}
  - fallback RunPod image: ${RUNPOD_TEMPLATE_FALLBACK_IMAGE} (or quick alias ${RUNPOD_TEMPLATE_FALLBACK_ALIAS})
  - CUDA 13 image remains experimental until live smoke: ${RUNPOD_TEMPLATE_CUDA13_EXPERIMENTAL_IMAGE}

Recommended for RunPod ephemeral pod usage:
  1) Recover /workspace/DreamCatcher/outputs before ending the session.
  2) Save /workspace/DreamCatcher/app/runtime/bootstrap_summary.json if smoke evidence is needed.
  3) Stop and terminate the Pod after artifact recovery.
  4) Start the next session from a fresh Pod plus DreamCatcher.zip.

Seed/workflow guard:
  - seed_bundle/api_workflows must contain real ComfyUI API exports.
  - Placeholder workflows are bootstrap blockers and must be fixed before release.

Optional model download flags for this script:
  --profile frontier
  --profile core|pro|labs    (legacy aliases for frontier)
  --download-birefnet
  --download-qwen
  --download-qwen-2512
  --download-qwen-judge
  --download-flux2-dev
  --download-klein
  --download-fill
  --download-qwen-layered
  --download-z-image
  --download-omnigen2
  --download-all

Useful logs:
  /workspace/dreamcatcher_bootstrap.log
  /workspace/dreamcatcher_backend.log
  /workspace/runpod-slim/comfyui.log
====================================================================
TXT
}

main() {
  ensure_python
  mkdir -p "$(dirname "$LOG_FILE")"
  : > "$LOG_FILE"
  prepare_workspace
  load_private_runtime_config
  apply_model_profile
  require_hf_token_if_needed
  normalize_comfy_root
  refresh_comfy_runtime
  run_setup
  prepare_staging_templates

  if [[ "$DOWNLOAD_BIREFNET" -eq 1 ]]; then
    download_birefnet
  fi
  if [[ "$DOWNLOAD_QWEN" -eq 1 ]]; then
    download_qwen
  fi
  if [[ "$DOWNLOAD_QWEN_2512" -eq 1 ]]; then
    download_qwen_2512
  fi
  if [[ "$DOWNLOAD_QWEN_JUDGE" -eq 1 ]]; then
    download_qwen_judge
  fi
  if [[ "$DOWNLOAD_FLUX2_DEV" -eq 1 ]]; then
    download_flux2_dev
  fi
  if [[ "$DOWNLOAD_KLEIN" -eq 1 ]]; then
    download_klein
  fi
  if [[ "$DOWNLOAD_FILL" -eq 1 ]]; then
    download_fill
  fi
  if [[ "$DOWNLOAD_QWEN_LAYERED" -eq 1 ]]; then
    download_qwen_layered
  fi
  if [[ "$DOWNLOAD_Z_IMAGE" -eq 1 ]]; then
    download_z_image
  fi
  if [[ "$DOWNLOAD_OMNIGEN2" -eq 1 ]]; then
    download_omnigen2
  fi

  if ! curl -fsS http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
    restart_comfy
  fi

  build_frontend_if_requested
  ensure_backend_running
  verify_bootstrap_runtime_contract
  print_next_steps
}

main "$@"
