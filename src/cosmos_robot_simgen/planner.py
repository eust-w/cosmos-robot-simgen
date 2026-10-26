from __future__ import annotations

import re
from typing import Dict, Tuple

from .models import RobotSpec, SceneObject, SimulationTask, Waypoint


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "cosmos_task"


def compile_prompt_to_task(prompt: str, name: str = "") -> SimulationTask:
    """Compile a natural-language task into a conservative Motrix task skeleton."""
    task_name = slugify(name or prompt[:48])
    item_label, item_kind, item_color = _detect_primary_object(prompt)
    target_label, target_color = _detect_target(prompt)

    objects = [
        SceneObject(
            object_id="floor",
            label="matte floor plane",
            kind="floor",
            position=(0.0, 0.0, 0.02),
            size=(2.4, 1.8, 0.04),
            mass_kg=0.0,
            material="rubber",
            color="#67727E",
            movable=False,
        ),
        SceneObject(
            object_id="work_table",
            label="work table",
            kind="table",
            position=(0.45, 0.0, 0.38),
            size=(0.95, 0.65, 0.08),
            mass_kg=0.0,
            material="laminated_wood",
            color="#B7A57A",
            movable=False,
        ),
        SceneObject(
            object_id="target_zone",
            label=target_label,
            kind="target_bin",
            position=(0.72, -0.18, 0.47),
            size=(0.24, 0.22, 0.12),
            mass_kg=0.25,
            material="plastic",
            color=target_color,
            movable=False,
        ),
        SceneObject(
            object_id="manipulated_object",
            label=item_label,
            kind=item_kind,
            position=(0.35, 0.18, 0.48),
            size=_size_for_kind(item_kind),
            mass_kg=0.18,
            material="plastic",
            color=item_color,
            movable=True,
        ),
    ]

    waypoints = [
        Waypoint(0.0, (0.12, 0.0, 0.76), True, "home pose"),
        Waypoint(1.2, (0.35, 0.18, 0.66), True, "approach object", "manipulated_object"),
        Waypoint(2.0, (0.35, 0.18, 0.52), True, "descend to grasp", "manipulated_object"),
        Waypoint(2.4, (0.35, 0.18, 0.52), False, "close gripper", "manipulated_object"),
        Waypoint(3.2, (0.35, 0.18, 0.74), False, "lift object", "manipulated_object"),
        Waypoint(4.4, (0.72, -0.18, 0.74), False, "move over target zone", "target_zone"),
        Waypoint(5.2, (0.72, -0.18, 0.58), False, "lower into target zone", "target_zone"),
        Waypoint(5.7, (0.72, -0.18, 0.58), True, "release object", "target_zone"),
        Waypoint(6.8, (0.12, 0.0, 0.76), True, "return home"),
    ]

    metadata: Dict[str, object] = {
        "compiler": "heuristic_prompt_compiler_v1",
        "cosmos_model": "nvidia/Cosmos3-Nano",
        "cosmos_required_for_physics_preview": True,
    }

    task = SimulationTask(
        name=task_name,
        prompt=prompt,
        robot=RobotSpec(),
        objects=objects,
        waypoints=waypoints,
        success_conditions=[
            "manipulated_object is inside target_zone at the final waypoint",
            "robot returns to home pose without colliding with work_table",
            "cosmos preview video is present when model inference is enabled",
        ],
        metadata=metadata,
    )
    task.validate()
    return task


def build_cosmos_prompt(task: SimulationTask) -> str:
    primary = next(obj for obj in task.objects if obj.object_id == "manipulated_object")
    target = next(obj for obj in task.objects if obj.object_id == "target_zone")
    return (
        "Physics-aware robot manipulation video for simulation task generation. "
        f"A generic six degree of freedom robot arm picks up {primary.label} from a clean work table "
        f"and places it into {target.label}. "
        "Use a fixed three-quarter camera view, realistic contact, stable lighting, no humans, "
        "and make the object motion smooth enough to infer waypoints for a simulator. "
        f"Original user task: {task.prompt}"
    )


def _detect_primary_object(prompt: str) -> Tuple[str, str, str]:
    lowered = prompt.lower()
    if "瓶" in prompt or "bottle" in lowered:
        return ("blue bottle", "bottle", "#4C8EDA")
    if "杯" in prompt or "cup" in lowered:
        return ("green cup", "cup", "#49A078")
    if "盒" in prompt or "box" in lowered:
        return ("red box", "box", "#D65A4A")
    if "球" in prompt or "ball" in lowered:
        return ("orange ball", "sphere", "#E29D38")
    return ("blue cube", "box", "#4C8EDA")


def _detect_target(prompt: str) -> Tuple[str, str]:
    lowered = prompt.lower()
    if "yellow" in lowered or "黄" in prompt:
        return ("yellow target bin", "#D8B23F")
    if "red" in lowered or "红" in prompt:
        return ("red target bin", "#C6534D")
    if "tray" in lowered or "托盘" in prompt:
        return ("gray target tray", "#8E99A4")
    return ("target bin", "#D8B23F")


def _size_for_kind(kind: str) -> Tuple[float, float, float]:
    if kind == "sphere":
        return (0.09, 0.09, 0.09)
    if kind == "bottle":
        return (0.07, 0.07, 0.18)
    if kind == "cup":
        return (0.08, 0.08, 0.11)
    return (0.09, 0.09, 0.09)
