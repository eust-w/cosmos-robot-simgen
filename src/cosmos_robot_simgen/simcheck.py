from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .validator import validate_package


def run_mujoco_check(path: Path) -> Dict[str, Any]:
    package_dir = _resolve_package_dir(path)
    if package_dir is None:
        return {
            "valid": False,
            "engine": "mujoco",
            "errors": ["package path must be a motrix_scene directory or project directory containing motrix_scene"],
            "package": str(path),
        }

    validation = validate_package(package_dir)
    if not validation["valid"]:
        return {
            "valid": False,
            "engine": "mujoco",
            "errors": validation["errors"],
            "package": str(package_dir),
        }

    try:
        import mujoco  # type: ignore
    except Exception as exc:
        return {
            "valid": False,
            "engine": "mujoco",
            "errors": [f"mujoco Python package is not installed or cannot be imported: {exc}"],
            "package": str(package_dir),
        }

    scene_xml = package_dir / "scene.xml"
    try:
        model = mujoco.MjModel.from_xml_path(str(scene_xml))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
    except Exception as exc:
        return {
            "valid": False,
            "engine": "mujoco",
            "errors": [f"MuJoCo failed to load or step scene.xml: {exc}"],
            "package": str(package_dir),
        }

    return {
        "valid": True,
        "engine": "mujoco",
        "errors": [],
        "package": str(package_dir),
        "summary": {
            "nbody": int(model.nbody),
            "ngeom": int(model.ngeom),
            "nmesh": int(model.nmesh),
            "nq": int(model.nq),
            "nv": int(model.nv),
        },
    }


def _resolve_package_dir(path: Path) -> Optional[Path]:
    path = Path(path).expanduser().resolve()
    if path.name == "motrix_scene":
        return path
    nested = path / "motrix_scene"
    if nested.exists():
        return nested.resolve()
    return None
