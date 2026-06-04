#!/usr/bin/env bash
set -Eeuo pipefail

# DreamCatcher active RunPod bootstrap entrypoint.
# Enables TriRaw(rawprep) prerequisites and then delegates to bootstrap_core.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DC_ROOT="${DC_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
EMBEDDED_SMOKE_BUNDLE_PATH="${EMBEDDED_SMOKE_BUNDLE_PATH:-${DC_ROOT}/runpod_inputs/rawprep_runpod_smoke_sample_bundle.zip}"

resolve_python_bin() {
  if [ -n "${PYTHON_BIN:-}" ] && command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "${PYTHON_BIN}"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  return 1
}

extract_embedded_smoke_bundle() {
  if [ ! -f "${EMBEDDED_SMOKE_BUNDLE_PATH}" ]; then
    echo "[DreamCatcher] embedded smoke sample bundle not present; continuing with app-only bootstrap"
    return 0
  fi

  local pybin
  pybin="$(resolve_python_bin)"
  echo "[DreamCatcher] extracting embedded RunPod smoke sample bundle"
  DC_EMBEDDED_SMOKE_BUNDLE="${EMBEDDED_SMOKE_BUNDLE_PATH}" \
  DC_APP_ROOT="${DC_ROOT}" \
  "${pybin}" - <<'PY'
import os
from pathlib import Path
import zipfile

archive_path = Path(os.environ["DC_EMBEDDED_SMOKE_BUNDLE"])
app_root = Path(os.environ["DC_APP_ROOT"])
app_root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive_path, "r") as archive:
    archive.extractall(app_root)
PY
}

export ENABLE_RAWPREP="${ENABLE_RAWPREP:-1}"
export RAWPREP_ROOT="${RAWPREP_ROOT:-/workspace/rawprep}"
export RAWPREP_TMP="${RAWPREP_TMP:-/workspace/.rawprep_tmp}"
export RAWPREP_OUT="${RAWPREP_OUT:-/workspace/DreamCatcher/outputs}"

echo "[DreamCatcher] bootstrap wrapper"
echo "[DreamCatcher] ENABLE_RAWPREP=$ENABLE_RAWPREP"
echo "[DreamCatcher] RAWPREP_ROOT=$RAWPREP_ROOT"
echo "[DreamCatcher] RAWPREP_TMP=$RAWPREP_TMP"
echo "[DreamCatcher] RAWPREP_OUT=$RAWPREP_OUT"
echo "[DreamCatcher] EMBEDDED_SMOKE_BUNDLE_PATH=$EMBEDDED_SMOKE_BUNDLE_PATH"

extract_embedded_smoke_bundle

bash "${SCRIPT_DIR}/bootstrap_core.sh" "$@"
