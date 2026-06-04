#!/usr/bin/env bash
set -Eeuo pipefail

# Starts the local Qwen vision judge as an OpenAI-compatible service.
# Run after bootstrap when quality automation needs live VLM judgment.

MODEL_PATH="${DC_QWEN_JUDGE_MODEL_PATH:-/workspace/DreamCatcher/models/qwen_judge/Qwen3.6-35B-A3B-FP8}"
SERVED_MODEL="${DC_QWEN_JUDGE_MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
HOST="${DC_QWEN_JUDGE_HOST:-127.0.0.1}"
PORT="${DC_QWEN_JUDGE_PORT:-8011}"
MAX_MODEL_LEN="${DC_QWEN_JUDGE_MAX_MODEL_LEN:-32768}"
GPU_MEMORY_UTILIZATION="${DC_QWEN_JUDGE_GPU_MEMORY_UTILIZATION:-0.35}"

if [[ ! -f "${MODEL_PATH}/config.json" ]]; then
  echo "[DreamCatcher] Qwen judge model is missing: ${MODEL_PATH}" >&2
  echo "[DreamCatcher] Run bootstrap with --profile frontier or --download-qwen-judge first." >&2
  exit 1
fi

if ! python - <<'PY' >/dev/null 2>&1
import vllm  # noqa: F401
PY
then
  echo "[DreamCatcher] installing vLLM for local Qwen judge serving"
  python -m pip install --upgrade "vllm>=0.12.0,<0.13.0"
fi

echo "[DreamCatcher] starting Qwen judge ${SERVED_MODEL} on ${HOST}:${PORT}"
exec vllm serve "${MODEL_PATH}" \
  --served-model-name "${SERVED_MODEL}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}"
