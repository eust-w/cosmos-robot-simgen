#!/usr/bin/env bash
set -euo pipefail

repo="nvidia/Cosmos3-Nano"
target="${COSMOS_TARGET_DIR:-vendor/Cosmos3-Nano}"

python3 - <<'PY' >/dev/null 2>&1 || python3 -m pip install --user -U "huggingface_hub>=0.34,<1.0"
from importlib.metadata import version

parts = version("huggingface-hub").split(".")
major = int(parts[0])
minor = int(parts[1])
if major >= 1 or (major == 0 and minor < 34):
    raise SystemExit(1)
PY

if [[ "${COSMOS_PULL_FULL:-0}" == "1" ]]; then
  echo "Pulling full ${repo} checkpoint tree into ${target}."
  echo "This can be very large and may require accepted model terms plus enough local storage."
  COSMOS_REPO="${repo}" COSMOS_TARGET="${target}" python3 - <<'PY'
import os
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=os.environ["COSMOS_REPO"],
    local_dir=os.environ["COSMOS_TARGET"],
)
PY
else
  echo "Pulling lightweight ${repo} assets into ${target}."
  COSMOS_REPO="${repo}" COSMOS_TARGET="${target}" python3 - <<'PY'
import os
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=os.environ["COSMOS_REPO"],
    local_dir=os.environ["COSMOS_TARGET"],
    allow_patterns=["assets/**"],
)
PY
fi
