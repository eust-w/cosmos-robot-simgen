from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from .geometry import build_scene_mtl, build_scene_obj
from .models import SceneObject, SimulationTask

Vector3 = Tuple[float, float, float]


def export_motrix_package(
    task: SimulationTask,
    output_root: Path,
    *,
    cosmos_artifacts: Optional[Dict[str, Any]] = None,
) -> Path:
    """Export a Real2Motrix/MotrixSim-compatible package directory."""
    task.validate()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task.name):
        raise ValueError("task name must be 1-128 letters, digits, underscores, or hyphens")
    project_dir = output_root / task.name
    package_dir = project_dir / "motrix_scene"
    # Reserve a new directory, refusing existing files, directories, and symlinks.
    project_dir.mkdir(parents=True, exist_ok=False)

    for relative in ["meshes", "metadata", "raw", "textures"]:
        (package_dir / relative).mkdir(parents=True, exist_ok=True)

    movable_objects = [obj for obj in task.objects if obj.movable]
    static_objects = [obj for obj in task.objects if not obj.movable] or task.objects

    (package_dir / "meshes" / "scene_visual.obj").write_text(build_scene_obj(task.objects), encoding="utf-8")
    (package_dir / "meshes" / "scene_collision.obj").write_text(build_scene_obj(static_objects), encoding="utf-8")
    (package_dir / "meshes" / "material.mtl").write_text(build_scene_mtl(task.objects), encoding="utf-8")

    for obj in movable_objects:
        object_dir = package_dir / "meshes" / "objects" / _safe_id(obj.object_id)
        object_dir.mkdir(parents=True, exist_ok=True)
        object_mesh = build_scene_obj([obj])
        (object_dir / "visual.obj").write_text(object_mesh, encoding="utf-8")
        (object_dir / "collision.obj").write_text(object_mesh, encoding="utf-8")

    asset_manifest = _build_asset_manifest(task, cosmos_artifacts, movable_objects, static_objects)
    scene_manifest = asset_manifest["scene"]
    object_manifest = asset_manifest["objects"]

    (package_dir / "scene.xml").write_text(_build_mjcf(scene_manifest, object_manifest), encoding="utf-8")
    (package_dir / "scene.urdf").write_text(_build_urdf(scene_manifest, object_manifest), encoding="utf-8")
    _write_json(package_dir / "scene.json", _build_scene_index(scene_manifest, object_manifest))
    _write_json(package_dir / "metadata" / "asset_manifest.json", asset_manifest)
    _write_json(package_dir / "metadata" / "scene_manifest.json", scene_manifest)
    _write_json(package_dir / "metadata" / "object_manifest.json", _build_object_manifest(asset_manifest))
    _write_json(package_dir / "metadata" / "semantic.json", _build_semantic_manifest(asset_manifest))
    _write_json(package_dir / "metadata" / "generation_report.json", _build_report(task, cosmos_artifacts, asset_manifest))
    _write_json(package_dir / "metadata" / "validation_report.json", _build_initial_validation_report(asset_manifest))
    _write_json(package_dir / "raw" / "source_info.json", _build_source_info(task, cosmos_artifacts))
    (package_dir / "README.md").write_text(_build_package_readme(task, cosmos_artifacts), encoding="utf-8")

    write_package_zip(package_dir)
    return package_dir


def write_package_zip(package_dir: Path) -> Path:
    zip_path = package_dir.parent / "motrix_scene.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir.parent).as_posix())
    return zip_path


def _build_asset_manifest(
    task: SimulationTask,
    cosmos_artifacts: Optional[Dict[str, Any]],
    movable_objects: Sequence[SceneObject],
    static_objects: Sequence[SceneObject],
) -> Dict[str, Any]:
    return {
        "project_id": task.name,
        "unit": "meter",
        "coordinate_system": "motrix_world",
        "generator": "cosmos-robot-simgen",
        "visual_mesh": "meshes/scene_visual.obj",
        "collision_mesh": "meshes/scene_collision.obj",
        "visual_faces": _face_count(task.objects),
        "collision_faces": _face_count(static_objects),
        "bbox": _bbox(task.objects),
        "scene": {
            "id": "static_scene",
            "role": "environment",
            "visual_mesh": "meshes/scene_visual.obj",
            "collision_mesh": "meshes/scene_collision.obj",
            "visual_faces": _face_count(task.objects),
            "collision_faces": _face_count(static_objects),
            "bbox": _bbox(task.objects),
            "binding": {"type": "static_world", "body": "static_scene"},
            "gaussian_splat": None,
        },
        "objects": [_object_entry(obj) for obj in movable_objects],
        "robot": task.robot.to_dict(),
        "task": task.to_dict(),
        "cosmos": {
            "model": "nvidia/Cosmos3-Nano",
            "preview_status": "generated" if cosmos_artifacts else "skipped",
            "artifacts": cosmos_artifacts or {},
        },
        "import": {
            "type": "motrix_scene_package",
            "entry": "scene.xml",
            "entries": {"mjcf": "scene.xml", "urdf": "scene.urdf"},
        },
    }


def _object_entry(obj: SceneObject) -> Dict[str, Any]:
    object_id = _safe_id(obj.object_id)
    return {
        "id": object_id,
        "label": obj.label,
        "kind": obj.kind,
        "source": "cosmos_robot_simgen_task",
        "movable": obj.movable,
        "visual_mesh": f"meshes/objects/{object_id}/visual.obj",
        "collision_mesh": f"meshes/objects/{object_id}/collision.obj",
        "visual_faces": _face_count([obj]),
        "collision_faces": _face_count([obj]),
        "bbox": _bbox([obj]),
        "binding": {"type": "dynamic_object", "body": object_id},
        "material": obj.material,
        "color": obj.color,
        "mass_kg": obj.mass_kg,
    }


def _build_mjcf(scene: Dict[str, Any], objects: List[Dict[str, Any]]) -> str:
    asset_lines = [
        f'    <mesh name="scene_visual" file="{_xml_attr(_meshdir_file(scene["visual_mesh"]))}"/>',
        f'    <mesh name="scene_collision" file="{_xml_attr(_meshdir_file(scene["collision_mesh"]))}"/>',
    ]
    body_lines = [
        '    <body name="static_scene" pos="0 0 0">',
        '      <geom name="scene_collision_geom"',
        '            type="mesh"',
        '            mesh="scene_collision"',
        '            contype="1"',
        '            conaffinity="1"',
        '            friction="0.8 0.1 0.1"/>',
        '      <geom name="scene_visual_geom"',
        '            type="mesh"',
        '            mesh="scene_visual"',
        '            contype="0"',
        '            conaffinity="0"',
        '            rgba="1 1 1 1"/>',
        "    </body>",
    ]
    for item in objects:
        object_id = _safe_id(str(item["id"]))
        visual_name = f"{object_id}_visual"
        collision_name = f"{object_id}_collision"
        asset_lines.extend(
            [
                f'    <mesh name="{_xml_attr(visual_name)}" file="{_xml_attr(_meshdir_file(item["visual_mesh"]))}"/>',
                f'    <mesh name="{_xml_attr(collision_name)}" file="{_xml_attr(_meshdir_file(item["collision_mesh"]))}"/>',
            ]
        )
        body_lines.extend(
            [
                f'    <body name="{_xml_attr(object_id)}" pos="0 0 0">',
                f'      <geom name="{_xml_attr(object_id)}_collision_geom"',
                '            type="mesh"',
                f'            mesh="{_xml_attr(collision_name)}"',
                '            contype="1"',
                '            conaffinity="1"',
                '            friction="0.8 0.1 0.1"/>',
                f'      <geom name="{_xml_attr(object_id)}_visual_geom"',
                '            type="mesh"',
                f'            mesh="{_xml_attr(visual_name)}"',
                '            contype="0"',
                '            conaffinity="0"',
                '            rgba="0.78 0.86 0.95 1"/>',
                "    </body>",
            ]
        )
    return "\n".join(
        [
            '<mujoco model="cosmos_robot_simgen_scene">',
            '  <compiler angle="radian" meshdir="meshes"/>',
            '  <option timestep="0.002" gravity="0 0 -9.81"/>',
            "  <asset>",
            *asset_lines,
            "  </asset>",
            "  <worldbody>",
            *body_lines,
            "  </worldbody>",
            "</mujoco>",
            "",
        ]
    )


def _build_urdf(scene: Dict[str, Any], objects: List[Dict[str, Any]]) -> str:
    lines = [
        '<robot name="cosmos_robot_simgen_scene">',
        '  <link name="static_scene">',
        "    <visual>",
        "      <geometry>",
        f'        <mesh filename="{_xml_attr(scene["visual_mesh"])}"/>',
        "      </geometry>",
        "    </visual>",
        "    <collision>",
        "      <geometry>",
        f'        <mesh filename="{_xml_attr(scene["collision_mesh"])}"/>',
        "      </geometry>",
        "    </collision>",
        "  </link>",
    ]
    for item in objects:
        object_id = _safe_id(str(item["id"]))
        lines.extend(
            [
                f'  <link name="{_xml_attr(object_id)}">',
                "    <visual>",
                "      <geometry>",
                f'        <mesh filename="{_xml_attr(item["visual_mesh"])}"/>',
                "      </geometry>",
                "    </visual>",
                "    <collision>",
                "      <geometry>",
                f'        <mesh filename="{_xml_attr(item["collision_mesh"])}"/>',
                "      </geometry>",
                "    </collision>",
                "  </link>",
                f'  <joint name="fixed_{_xml_attr(object_id)}" type="fixed">',
                '    <parent link="static_scene"/>',
                f'    <child link="{_xml_attr(object_id)}"/>',
                '    <origin xyz="0 0 0" rpy="0 0 0"/>',
                "  </joint>",
            ]
        )
    lines.append("</robot>")
    lines.append("")
    return "\n".join(lines)


def _build_scene_index(scene: Dict[str, Any], objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "name": "cosmos_robot_simgen_scene",
        "type": "motrix_scene_package",
        "entry": "scene.xml",
        "entries": {"mjcf": "scene.xml", "urdf": "scene.urdf"},
        "assets": {
            "visual_mesh": scene["visual_mesh"],
            "collision_mesh": scene["collision_mesh"],
            "scene_manifest": "metadata/scene_manifest.json",
            "object_manifest": "metadata/object_manifest.json",
            "objects": {
                item["id"]: {
                    "visual_mesh": item["visual_mesh"],
                    "collision_mesh": item["collision_mesh"],
                    "body": item.get("binding", {}).get("body", item["id"]),
                    "gaussian_splat": item.get("gaussian_splat"),
                }
                for item in objects
            },
        },
        "metadata": "metadata/asset_manifest.json",
    }


def _build_object_manifest(asset_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "objects": asset_manifest["objects"],
        "count": len(asset_manifest["objects"]),
        "coordinate_system": asset_manifest["coordinate_system"],
        "unit": asset_manifest["unit"],
    }


def _build_semantic_manifest(asset_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "labels": [
            {
                "id": item["id"],
                "label": item.get("label", "object_candidate"),
                "source": item.get("source", "cosmos_robot_simgen_task"),
            }
            for item in asset_manifest["objects"]
        ],
        "coordinate_system": asset_manifest["coordinate_system"],
        "unit": asset_manifest["unit"],
    }


def _build_report(
    task: SimulationTask,
    cosmos_artifacts: Optional[Dict[str, Any]],
    asset_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "task_name": task.name,
        "object_count": len(task.objects),
        "movable_object_count": len(asset_manifest["objects"]),
        "waypoint_count": len(task.waypoints),
        "visual_faces": asset_manifest["visual_faces"],
        "collision_faces": asset_manifest["collision_faces"],
        "bbox": asset_manifest["bbox"],
        "cosmos": asset_manifest["cosmos"],
        "validation": {
            "task_valid": True,
            "motrix_entrypoints": ["scene.xml", "scene.urdf", "scene.json"],
        },
    }


def _build_initial_validation_report(asset_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "valid": True,
        "issues": [],
        "summary": {
            "object_count": len(asset_manifest["objects"]),
            "visual_faces": asset_manifest["visual_faces"],
            "collision_faces": asset_manifest["collision_faces"],
        },
        "source": "cosmos_robot_simgen_internal_export",
    }


def _build_source_info(task: SimulationTask, cosmos_artifacts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "source": "cosmos_robot_simgen",
        "prompt": task.prompt,
        "task_name": task.name,
        "cosmos": {
            "model": "nvidia/Cosmos3-Nano",
            "preview_status": "generated" if cosmos_artifacts else "skipped",
            "artifacts": cosmos_artifacts or {},
        },
    }


def _build_package_readme(task: SimulationTask, cosmos_artifacts: Optional[Dict[str, Any]]) -> str:
    status = "generated" if cosmos_artifacts else "skipped"
    return (
        "# Cosmos Robot SimGen Motrix Package\n\n"
        "This folder is a MotrixSim-compatible scene package in the same layout used by Real2Motrix.\n\n"
        f"Task: {task.name}\n\n"
        f"Prompt: {task.prompt}\n\n"
        f"Cosmos3 Nano preview status: {status}\n\n"
        "Import steps:\n"
        "1. Open MotrixSim Web Viewer.\n"
        "2. Drag this entire `motrix_scene` folder into the viewer.\n"
        "3. Load `scene.xml`, `scene.urdf`, or `scene.json`.\n\n"
        "Package layout:\n"
        "- `meshes/scene_visual.obj` and `meshes/scene_collision.obj` contain the scene geometry.\n"
        "- `meshes/objects/*` contains movable object candidates for manipulation tasks.\n"
        "- `metadata/asset_manifest.json` is the authoritative package manifest.\n"
        "- `raw/source_info.json` records the prompt and Cosmos inference artifacts.\n"
    )


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _face_count(objects: Iterable[SceneObject]) -> int:
    return sum(12 for _ in objects)


def _bbox(objects: Sequence[SceneObject]) -> List[List[float]]:
    if not objects:
        return [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for obj in objects:
        for index in range(3):
            low = obj.position[index] - obj.size[index] / 2.0
            high = obj.position[index] + obj.size[index] / 2.0
            mins[index] = min(mins[index], low)
            maxs[index] = max(maxs[index], high)
    mins[2] = 0.0 if abs(mins[2]) < 1e-9 else mins[2]
    return [[round(value, 6) for value in mins], [round(value, 6) for value in maxs]]


def _meshdir_file(value: str) -> str:
    posix = PurePosixPath(value)
    if posix.parts and posix.parts[0] == "meshes":
        return str(PurePosixPath(*posix.parts[1:]))
    return str(posix)


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return cleaned or "asset"


def _xml_attr(value: Any) -> str:
    return escape(str(value), {'"': "&quot;"})
