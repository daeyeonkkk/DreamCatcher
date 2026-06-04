#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DC_ROOT="${DC_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
else
  echo "ERROR: python or python3 not found"
  exit 1
fi

if [ -n "${COMFY_ROOT:-}" ] && [ -f "${COMFY_ROOT}/main.py" ]; then
  :
elif [ -f /workspace/runpod-slim/ComfyUI/main.py ]; then
  COMFY_ROOT=/workspace/runpod-slim/ComfyUI
elif [ -f /workspace/ComfyUI/main.py ]; then
  COMFY_ROOT=/workspace/ComfyUI
else
  echo "ERROR: Could not detect ComfyUI root. Set COMFY_ROOT manually."
  exit 1
fi

if [ ! -e /workspace/ComfyUI ] && [ "$COMFY_ROOT" = "/workspace/runpod-slim/ComfyUI" ]; then
  ln -sfn "$COMFY_ROOT" /workspace/ComfyUI
fi

COMFY_URL="${COMFY_URL:-http://127.0.0.1:8188}"
ENABLE_RAWPREP="${ENABLE_RAWPREP:-0}"
RAWPREP_ROOT="${RAWPREP_ROOT:-/workspace/rawprep}"
RAWPREP_TMP="${RAWPREP_TMP:-/workspace/.rawprep_tmp}"
RAWPREP_OUT="${RAWPREP_OUT:-$DC_ROOT/../outputs}"
APP_PYTHONPATH="${DC_ROOT}/backend:${DC_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [ -n "${SEED_ROOT:-}" ]; then
  :
elif [ -d "$(cd "$DC_ROOT/../seed_bundle" 2>/dev/null && pwd || true)" ]; then
  SEED_ROOT="$(cd "$DC_ROOT/../seed_bundle" && pwd)"
else
  SEED_ROOT="$DC_ROOT/seed_bundle"
fi

mkdir -p "$DC_ROOT/runtime" "$DC_ROOT/logs" "$DC_ROOT/workflows/runtime"
mkdir -p "$RAWPREP_ROOT" "$RAWPREP_TMP" "$RAWPREP_OUT"

pick_comfy_python() {
  local candidates=(
    "$COMFY_ROOT/.venv/bin/python"
    "$COMFY_ROOT/.venv-cu130/bin/python"
    "$COMFY_ROOT/.venv-cu128/bin/python"
  )
  local candidate=""
  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  candidate="$(find "$COMFY_ROOT" -maxdepth 2 -path '*/bin/python' -type f 2>/dev/null | head -n 1 || true)"
  if [ -n "$candidate" ]; then
    echo "$candidate"
    return 0
  fi
  echo "$PYTHON_BIN"
}

resolve_comfy_log() {
  if [ "$COMFY_ROOT" = "/workspace/runpod-slim/ComfyUI" ]; then
    echo "/workspace/runpod-slim/comfyui.log"
    return 0
  fi
  echo "$DC_ROOT/logs/comfy.log"
}

wait_for_comfy() {
  for i in $(seq 1 180); do
    if curl -fsS "$COMFY_URL/system_stats" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

echo "[env] DC_ROOT=$DC_ROOT"
echo "[env] COMFY_ROOT=$COMFY_ROOT"
echo "[env] SEED_ROOT=$SEED_ROOT"
echo "[env] PYTHON_BIN=$PYTHON_BIN"
echo "[env] ENABLE_RAWPREP=$ENABLE_RAWPREP"
echo "[env] RAWPREP_ROOT=$RAWPREP_ROOT"
echo "[env] RAWPREP_TMP=$RAWPREP_TMP"
echo "[env] RAWPREP_OUT=$RAWPREP_OUT"
echo "[env] APP_PYTHONPATH=$APP_PYTHONPATH"

echo "[1/7] Verify local seed bundle"
if [ ! -d "$SEED_ROOT" ]; then
  echo "ERROR: seed bundle not found at $SEED_ROOT"
  exit 1
fi
"$PYTHON_BIN" "$DC_ROOT/scripts/verify_seed_bundle.py" --seed-root "$SEED_ROOT"

echo "[2/7] Install minimal pinned custom nodes"
PYTHONPATH="$APP_PYTHONPATH" "$PYTHON_BIN" -m backend.app.core.custom_node_installer \
  --manifest "$DC_ROOT/custom_nodes/custom_node_manifest.yaml" \
  --comfy-root "$COMFY_ROOT" \
  --python-bin "$PYTHON_BIN"

echo "[3/7] Restart ComfyUI to load custom nodes"
pkill -f "python.*main.py.*8188" 2>/dev/null || true
sleep 3
COMFY_START_PY="$(pick_comfy_python)"
COMFY_LOG="$(resolve_comfy_log)"
nohup "$COMFY_START_PY" "$COMFY_ROOT/main.py" --listen 0.0.0.0 --port 8188 > "$COMFY_LOG" 2>&1 &

echo "[4/7] Wait for ComfyUI"
if ! wait_for_comfy; then
  echo "ERROR: ComfyUI did not become ready at $COMFY_URL"
  tail -n 120 /workspace/runpod-slim/comfyui.log 2>/dev/null || true
  tail -n 120 "$DC_ROOT/logs/comfy.log" 2>/dev/null || true
  exit 1
fi

echo "[5/7] Fetch node inventory"
PYTHONPATH="$APP_PYTHONPATH" "$PYTHON_BIN" -m backend.app.core.node_inventory \
  --base-url "$COMFY_URL" \
  --out "$DC_ROOT/runtime/object_info.json"

echo "[6/7] Materialize custom-node workflows only"
shopt -s nullglob
for template in "$DC_ROOT"/workflows/templates/*.template.json; do
  base="$(basename "$template" .template.json)"
  PYTHONPATH="$APP_PYTHONPATH" "$PYTHON_BIN" -m backend.app.core.workflow_materializer \
    --template "$template" \
    --alias-config "$DC_ROOT/custom_nodes/node_aliases.yaml" \
    --object-info "$DC_ROOT/runtime/object_info.json" \
    --out "$DC_ROOT/workflows/runtime/${base}.json"
done

echo "[7/7] Validate materialized runtime workflows"
for workflow in "$DC_ROOT"/workflows/runtime/*.json; do
  [ -e "$workflow" ] || continue
  PYTHONPATH="$APP_PYTHONPATH" "$PYTHON_BIN" -m backend.app.core.preflight_validator \
    --workflow "$workflow" \
    --object-info "$DC_ROOT/runtime/object_info.json"
done

if [ "$ENABLE_RAWPREP" = "1" ]; then
  echo "[rawprep] Validate DreamRAW-Tri v2 scaffold prerequisites"
  PYTHONPATH="$APP_PYTHONPATH" "$PYTHON_BIN" "$DC_ROOT/scripts/rawprep_healthcheck.py" \
    --allow-missing \
    --out "$DC_ROOT/runtime/rawprep_healthcheck.json"
else
  echo "[rawprep] Skipping TriRaw CLI validation (ENABLE_RAWPREP=0)"
fi

echo "[done] Native workflows come from seed_bundle/api_workflows and are ready when those 4 API exports are present."
