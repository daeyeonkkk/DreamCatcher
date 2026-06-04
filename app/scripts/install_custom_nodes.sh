#!/usr/bin/env bash
set -euo pipefail

DC_ROOT="${DC_ROOT:-/workspace/dreamcatcher_impl_v4}"
COMFY_ROOT="${COMFY_ROOT:-/workspace/ComfyUI}"
PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" "$DC_ROOT/backend/app/core/custom_node_installer.py" \
  --manifest "$DC_ROOT/custom_nodes/custom_node_manifest.yaml" \
  --comfy-root "$COMFY_ROOT" \
  --python-bin "$PYTHON_BIN"
