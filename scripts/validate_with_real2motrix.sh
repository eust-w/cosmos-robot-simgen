#!/usr/bin/env bash
set -euo pipefail

package_path="${1:-outputs/smoke_demo/motrix_scene}"
real2motrix_dir="${REAL2MOTRIX_DIR:-../Real2Motrix}"
python_bin="${REAL2MOTRIX_PYTHON:-${real2motrix_dir}/.venv/bin/python}"

if [[ ! -x "${python_bin}" ]]; then
  echo "Real2Motrix Python not found: ${python_bin}" >&2
  exit 2
fi

REAL2MOTRIX_BACKEND="${real2motrix_dir}/backend" \
PACKAGE_PATH="${package_path}" \
PYTHONPATH="${real2motrix_dir}/backend${PYTHONPATH:+:${PYTHONPATH}}" \
"${python_bin}" - <<'PY'
import json
import os
from pathlib import Path

from app.pipeline.motrix.validate import validate_package

package = Path(os.environ["PACKAGE_PATH"]).expanduser().resolve()
if package.name != "motrix_scene" and (package / "motrix_scene").exists():
    package = package / "motrix_scene"
report = validate_package(package)
print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if report.get("valid") else 1)
PY
