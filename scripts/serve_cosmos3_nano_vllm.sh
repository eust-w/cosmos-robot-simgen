#!/usr/bin/env bash
set -euo pipefail

model="${COSMOS3_NANO_MODEL:-nvidia/Cosmos3-Nano}"
host="${COSMOS3_NANO_HOST:-127.0.0.1}"
port="${COSMOS3_NANO_PORT:-8000}"

echo "Experimental reasoner-only helper: this is NOT the video endpoint required by cosmos-simgen." >&2

if ! command -v vllm >/dev/null 2>&1; then
  echo "vllm is not on PATH. Install the NVIDIA/Cosmos-compatible vLLM stack on a CUDA host first." >&2
  exit 2
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi is not on PATH. Cosmos3 Nano local serving requires CUDA-class NVIDIA hardware." >&2
  exit 2
fi

exec vllm serve "${model}" \
  --hf-overrides '{"architectures": ["Cosmos3ReasonerForConditionalGeneration"]}' \
  --tensor-parallel-size "${COSMOS3_NANO_TENSOR_PARALLEL_SIZE:-1}" \
  --mm-encoder-tp-mode data \
  --async-scheduling \
  --media-io-kwargs '{"video": {"num_frames": -1}}' \
  --host "${host}" \
  --port "${port}"
