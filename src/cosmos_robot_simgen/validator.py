from __future__ import annotations

import json
import math
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set

from .models import validate_task_dict


REQUIRED_PACKAGE_FILES = [
    "scene.xml",
    "scene.urdf",
    "scene.json",
    "metadata/asset_manifest.json",
    "metadata/scene_manifest.json",
    "metadata/object_manifest.json",
    "metadata/semantic.json",
    "metadata/generation_report.json",
    "metadata/validation_report.json",
    "raw/source_info.json",
    "meshes/scene_visual.obj",
    "meshes/scene_collision.obj",
]


def validate_package(path: Path) -> Dict[str, object]:
    package_dir = _resolve_package_dir(path)
    errors: List[str] = []
    warnings: List[str] = []

    if package_dir is None:
        return {
            "valid": False,
            "errors": ["package path must be a motrix_scene directory or a project directory containing motrix_scene"],
            "warnings": [],
            "package": str(path),
            "zip": None,
            "required_files": REQUIRED_PACKAGE_FILES,
        }

    for relative_path in REQUIRED_PACKAGE_FILES:
        _check_file(package_dir / relative_path, relative_path, errors)

    scene_json = _load_json(package_dir / "scene.json", errors, "scene.json")
    asset_manifest = _load_json(package_dir / "metadata" / "asset_manifest.json", errors, "metadata/asset_manifest.json")
    object_manifest = _load_json(package_dir / "metadata" / "object_manifest.json", errors, "metadata/object_manifest.json")

    mjcf_root = _parse_xml(package_dir / "scene.xml", "scene.xml", errors)
    urdf_root = _parse_xml(package_dir / "scene.urdf", "scene.urdf", errors)

    mesh_refs: Set[str] = set()
    if mjcf_root is not None:
        _collect_mjcf_mesh_refs(mjcf_root, mesh_refs, errors)
    if urdf_root is not None:
        _collect_urdf_mesh_refs(urdf_root, mesh_refs, errors)
    if scene_json:
        _check_scene_json(scene_json, mesh_refs, errors)
    if asset_manifest:
        _check_asset_manifest(package_dir, asset_manifest, mesh_refs, errors, warnings)
    if object_manifest:
        _check_object_manifest(object_manifest, errors)

    for ref in sorted(mesh_refs):
        candidate = _resolve_relative(package_dir, ref, errors)
        if candidate:
            _check_obj(candidate, ref, errors)

    zip_path = package_dir.parent / "motrix_scene.zip"
    _check_zip(zip_path, errors)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "package": str(package_dir),
        "zip": str(zip_path),
        "required_files": REQUIRED_PACKAGE_FILES,
    }


def _resolve_package_dir(path: Path) -> Optional[Path]:
    path = Path(path).expanduser().resolve()
    if path.name == "motrix_scene":
        return path
    nested = path / "motrix_scene"
    if nested.exists():
        return nested.resolve()
    return None


def _check_file(path: Path, label: str, errors: List[str]) -> None:
    if not path.exists():
        errors.append(f"missing {label}")
    elif path.is_file() and path.stat().st_size == 0:
        errors.append(f"empty {label}")


def _load_json(path: Path, errors: List[str], label: str) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid json {label}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label} must contain a JSON object")
        return {}
    return data


def _parse_xml(path: Path, label: str, errors: List[str]) -> Optional[ET.Element]:
    if not path.exists():
        return None
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        errors.append(f"invalid xml {label}: {exc}")
        return None


def _collect_mjcf_mesh_refs(root: ET.Element, mesh_refs: Set[str], errors: List[str]) -> None:
    meshdir = "meshes"
    compiler = root.find("compiler")
    if compiler is not None and compiler.attrib.get("meshdir"):
        meshdir = compiler.attrib["meshdir"]
        _check_relative(meshdir, errors, "MJCF meshdir")
    for mesh in root.findall(".//mesh"):
        ref = mesh.attrib.get("file")
        if ref:
            _check_relative(ref, errors, "MJCF mesh")
            mesh_refs.add(str(PurePosixPath(meshdir) / ref))


def _collect_urdf_mesh_refs(root: ET.Element, mesh_refs: Set[str], errors: List[str]) -> None:
    for mesh in root.findall(".//mesh"):
        ref = mesh.attrib.get("filename") or mesh.attrib.get("file")
        if ref:
            _check_relative(ref, errors, "URDF mesh")
            mesh_refs.add(ref)


def _check_scene_json(scene_json: Dict[str, Any], mesh_refs: Set[str], errors: List[str]) -> None:
    if scene_json.get("type") != "motrix_scene_package":
        errors.append("scene.json type must be motrix_scene_package")
    for key in ("entry", "metadata"):
        value = scene_json.get(key)
        if isinstance(value, str):
            _check_relative(value, errors, f"scene.json {key}")
    entries = scene_json.get("entries", {})
    if isinstance(entries, dict):
        for key, value in entries.items():
            if isinstance(value, str):
                _check_relative(value, errors, f"scene.json entries.{key}")
    assets = scene_json.get("assets", {})
    if isinstance(assets, dict):
        _collect_scene_asset_refs(assets, mesh_refs, errors, "scene.json assets")


def _check_asset_manifest(
    package_dir: Path,
    asset_manifest: Dict[str, Any],
    mesh_refs: Set[str],
    errors: List[str],
    warnings: List[str],
) -> None:
    if asset_manifest.get("coordinate_system") != "motrix_world":
        errors.append("asset_manifest coordinate_system must be motrix_world")
    if asset_manifest.get("unit") != "meter":
        errors.append("asset_manifest unit must be meter")
    scene = asset_manifest.get("scene", {})
    if isinstance(scene, dict):
        for key in ("visual_mesh", "collision_mesh"):
            value = scene.get(key)
            if isinstance(value, str):
                _check_relative(value, errors, f"asset_manifest scene {key}")
                mesh_refs.add(value)
    for key in ("visual_mesh", "collision_mesh"):
        value = asset_manifest.get(key)
        if isinstance(value, str):
            _check_relative(value, errors, f"asset_manifest {key}")
            mesh_refs.add(value)

    objects = asset_manifest.get("objects", [])
    if isinstance(objects, list):
        for index, item in enumerate(objects):
            if not isinstance(item, dict):
                errors.append(f"asset_manifest objects[{index}] must be an object")
                continue
            for key in ("visual_mesh", "collision_mesh"):
                value = item.get(key)
                if isinstance(value, str):
                    _check_relative(value, errors, f"asset_manifest objects[{index}] {key}")
                    mesh_refs.add(value)

    task = asset_manifest.get("task")
    if isinstance(task, dict):
        try:
            validate_task_dict(task)
        except Exception as exc:
            errors.append(f"invalid asset_manifest task: {exc}")
    else:
        errors.append("asset_manifest task is required")

    _check_bbox(asset_manifest, errors)
    _check_cosmos_artifacts(package_dir, asset_manifest, errors, warnings)


def _check_object_manifest(object_manifest: Dict[str, Any], errors: List[str]) -> None:
    objects = object_manifest.get("objects")
    count = object_manifest.get("count")
    if not isinstance(objects, list):
        errors.append("object_manifest objects must be a list")
        return
    if count != len(objects):
        errors.append("object_manifest count must match objects length")


def _collect_scene_asset_refs(value: Any, mesh_refs: Set[str], errors: List[str], label: str) -> None:
    if isinstance(value, str):
        _check_relative(value, errors, label)
        if "mesh" in label:
            mesh_refs.add(value)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            next_label = f"{label} {key}"
            if isinstance(item, str):
                _check_relative(item, errors, next_label)
                if "mesh" in key:
                    mesh_refs.add(item)
            elif isinstance(item, dict):
                _collect_scene_asset_refs(item, mesh_refs, errors, next_label)
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    _collect_scene_asset_refs(child, mesh_refs, errors, f"{next_label}[{index}]")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _collect_scene_asset_refs(item, mesh_refs, errors, f"{label}[{index}]")


def _check_relative(value: str, errors: List[str], label: str) -> None:
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts:
        errors.append(f"{label} path must be relative and portable: {value}")


def _resolve_relative(root: Path, value: str, errors: List[str]) -> Optional[Path]:
    posix = PurePosixPath(value)
    candidate = (root / Path(*posix.parts)).resolve()
    root_resolved = root.resolve()
    if root_resolved != candidate and root_resolved not in candidate.parents:
        errors.append(f"path escapes package root: {value}")
        return None
    return candidate


def _check_obj(path: Path, label: str, errors: List[str]) -> None:
    if not path.exists():
        errors.append(f"referenced mesh missing: {label}")
        return
    text = path.read_text(encoding="utf-8")
    if "\nv " not in f"\n{text}":
        errors.append(f"{label} has no vertices")
    if "\nf " not in f"\n{text}":
        errors.append(f"{label} has no faces")


def _check_bbox(asset_manifest: Dict[str, Any], errors: List[str]) -> None:
    bbox = asset_manifest.get("bbox")
    if not _is_bbox(bbox):
        errors.append("asset_manifest bbox must be [[minx,miny,minz],[maxx,maxy,maxz]]")
        return
    flat = [float(value) for row in bbox for value in row]
    if not all(math.isfinite(value) for value in flat):
        errors.append("asset_manifest bbox contains non-finite values")
    extents = [float(bbox[1][i]) - float(bbox[0][i]) for i in range(3)]
    if any(value <= 0 for value in extents):
        errors.append("asset_manifest bbox has non-positive extent")
    if any(value > 1000 for value in extents):
        errors.append("asset_manifest bbox is larger than 1000 meters")
    if float(bbox[0][2]) < -0.01:
        errors.append("asset_manifest bbox lowest z must be aligned near 0")


def _is_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(row, list) and len(row) == 3 for row in value)
        and all(isinstance(item, (int, float)) for row in value for item in row)
    )


def _check_zip(path: Path, errors: List[str]) -> None:
    if not path.exists():
        errors.append("missing motrix_scene.zip")
        return
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        errors.append(f"invalid motrix_scene.zip: {exc}")
        return
    for expected in ["motrix_scene/scene.xml", "motrix_scene/scene.urdf", "motrix_scene/scene.json", "motrix_scene/metadata/asset_manifest.json"]:
        if expected not in names:
            errors.append(f"zip missing {expected}")


def _check_cosmos_artifacts(
    package_dir: Path,
    asset_manifest: Dict[str, Any],
    errors: List[str],
    warnings: List[str],
) -> None:
    cosmos = asset_manifest.get("cosmos")
    if not isinstance(cosmos, dict):
        errors.append("asset_manifest cosmos section is required")
        return
    if cosmos.get("preview_status") != "generated":
        warnings.append("Cosmos3 Nano preview was skipped; package is structurally valid but not model-backed")
        return
    artifacts = cosmos.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("generated Cosmos preview is missing artifact metadata")
        return
    for key in ["video", "request", "response_metadata"]:
        relative = artifacts.get(key)
        if not isinstance(relative, str) or not relative:
            errors.append(f"generated Cosmos preview is missing {key} artifact")
            continue
        _check_relative(relative, errors, f"Cosmos artifact {key}")
        path = package_dir / relative
        if not path.exists():
            errors.append(f"missing generated Cosmos artifact {relative}")
        elif path.stat().st_size == 0:
            errors.append(f"empty generated Cosmos artifact {relative}")
