#!/usr/bin/env bash
set -euo pipefail

package_dir="${1:-outputs/smoke_demo/motrix_scene}"
real2motrix_dir="${REAL2MOTRIX_DIR:-../Real2Motrix}"
python_bin="${REAL2MOTRIX_PYTHON:-${real2motrix_dir}/.venv/bin/python}"
project_name="${REAL2MOTRIX_PROJECT_NAME:-Cosmos SimGen Smoke}"

if [[ ! -x "${python_bin}" ]]; then
  echo "Real2Motrix Python not found: ${python_bin}" >&2
  exit 2
fi

REAL2MOTRIX_DIR="${real2motrix_dir}" \
PACKAGE_DIR="${package_dir}" \
PROJECT_NAME="${project_name}" \
PYTHONPATH="${real2motrix_dir}/backend${PYTHONPATH:+:${PYTHONPATH}}" \
"${python_bin}" - <<'PY'
import json
import os
import shutil
from pathlib import Path

from app.database import Database, utc_now
from app.pipeline.motrix.package import zip_package
from app.pipeline.motrix.validate import validate_package
from app.services.asset_service import clear_project_assets, create_asset
from app.services.project_service import create_project, update_project_status
from app.settings import get_settings

real2motrix_dir = Path(os.environ["REAL2MOTRIX_DIR"]).resolve()
package_dir = Path(os.environ["PACKAGE_DIR"]).expanduser().resolve()
project_name = os.environ["PROJECT_NAME"]
settings = get_settings()
db = Database(settings.database_path)

if package_dir.name != "motrix_scene":
    package_dir = package_dir / "motrix_scene"
if not package_dir.exists():
    raise SystemExit(f"package not found: {package_dir}")

project = create_project(
    db,
    settings.data_dir,
    name=project_name,
    description="Imported from cosmos-robot-simgen for browser preview and validation.",
    source_type="mesh",
)
project_id = project["id"]
target_project_dir = settings.output_dir / project_id
target_package_dir = target_project_dir / "motrix_scene"
target_project_dir.mkdir(parents=True, exist_ok=True)
if target_package_dir.exists():
    shutil.rmtree(target_package_dir)
shutil.copytree(package_dir, target_package_dir)
zip_path = zip_package(target_package_dir)

report = validate_package(target_package_dir)
if not report.get("valid"):
    raise SystemExit(json.dumps(report, indent=2, ensure_ascii=False))

asset_manifest = json.loads((target_package_dir / "metadata" / "asset_manifest.json").read_text(encoding="utf-8"))
clear_project_assets(db, project_id)
create_asset(
    db,
    project_id,
    "motrix_package",
    zip_path,
    {
        "package_dir": str(target_package_dir),
        "validation": report.get("summary", {}),
    },
)
create_asset(
    db,
    project_id,
    "visual_mesh",
    target_package_dir / "meshes" / "scene_visual.obj",
    {
        "visual_faces": asset_manifest.get("visual_faces"),
        "bbox": asset_manifest.get("bbox"),
    },
)
create_asset(
    db,
    project_id,
    "collision_mesh",
    target_package_dir / "meshes" / "scene_collision.obj",
    {
        "collision_faces": asset_manifest.get("collision_faces"),
        "bbox": asset_manifest.get("bbox"),
    },
)
for item in asset_manifest.get("objects", []):
    object_id = item.get("id")
    if not object_id:
        continue
    metadata = {
        "object_id": object_id,
        "id": object_id,
        "label": item.get("label"),
        "visual_faces": item.get("visual_faces"),
        "collision_faces": item.get("collision_faces"),
        "bbox": item.get("bbox"),
    }
    create_asset(db, project_id, "object_visual_mesh", target_package_dir / item["visual_mesh"], metadata)
    create_asset(db, project_id, "object_collision_mesh", target_package_dir / item["collision_mesh"], metadata)

update_project_status(db, project_id, "completed")
db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utc_now(), project_id))

result = {
    "project_id": project_id,
    "project_name": project_name,
    "package_dir": str(target_package_dir),
    "zip": str(zip_path),
    "validation": report,
    "api_project_url": f"http://localhost:8000/api/projects/{project_id}",
    "frontend_url": "http://localhost:5173",
}
print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
PY
