from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

Vector3 = Tuple[float, float, float]


class TaskValidationError(ValueError):
    """Raised when a simulation task cannot be exported safely."""


def _vector3(value: Sequence[float], field_name: str) -> Vector3:
    if len(value) != 3:
        raise TaskValidationError(f"{field_name} must contain exactly 3 numbers")
    return (float(value[0]), float(value[1]), float(value[2]))


@dataclass(frozen=True)
class RobotSpec:
    name: str = "motrix_arm"
    model: str = "generic_6dof_arm"
    base_position: Vector3 = (0.0, 0.0, 0.0)
    reach_radius: float = 1.2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "base_position": list(self.base_position),
            "reach_radius": self.reach_radius,
        }


@dataclass(frozen=True)
class SceneObject:
    object_id: str
    label: str
    kind: str
    position: Vector3
    size: Vector3
    mass_kg: float
    material: str = "default"
    color: str = "#8AB4F8"
    movable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.object_id,
            "label": self.label,
            "kind": self.kind,
            "position": list(self.position),
            "size": list(self.size),
            "mass_kg": self.mass_kg,
            "material": self.material,
            "color": self.color,
            "movable": self.movable,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SceneObject":
        return cls(
            object_id=str(data["id"]),
            label=str(data.get("label", data["id"])),
            kind=str(data.get("kind", "box")),
            position=_vector3(data["position"], "object.position"),
            size=_vector3(data["size"], "object.size"),
            mass_kg=float(data.get("mass_kg", 0.1)),
            material=str(data.get("material", "default")),
            color=str(data.get("color", "#8AB4F8")),
            movable=bool(data.get("movable", True)),
        )


@dataclass(frozen=True)
class Waypoint:
    time_s: float
    gripper_position: Vector3
    gripper_open: bool
    note: str
    target_object: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_s": self.time_s,
            "gripper_position": list(self.gripper_position),
            "gripper_open": self.gripper_open,
            "note": self.note,
            "target_object": self.target_object,
        }


@dataclass(frozen=True)
class SimulationTask:
    name: str
    prompt: str
    robot: RobotSpec
    objects: List[SceneObject]
    waypoints: List[Waypoint]
    success_conditions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "cosmos_robot_simgen.task.v1",
            "name": self.name,
            "prompt": self.prompt,
            "robot": self.robot.to_dict(),
            "objects": [obj.to_dict() for obj in self.objects],
            "waypoints": [waypoint.to_dict() for waypoint in self.waypoints],
            "success_conditions": list(self.success_conditions),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SimulationTask":
        robot_data = data.get("robot", {})
        robot = RobotSpec(
            name=str(robot_data.get("name", "motrix_arm")),
            model=str(robot_data.get("model", "generic_6dof_arm")),
            base_position=_vector3(robot_data.get("base_position", (0, 0, 0)), "robot.base_position"),
            reach_radius=float(robot_data.get("reach_radius", 1.2)),
        )
        waypoints = [
            Waypoint(
                time_s=float(item["time_s"]),
                gripper_position=_vector3(item["gripper_position"], "waypoint.gripper_position"),
                gripper_open=bool(item["gripper_open"]),
                note=str(item.get("note", "")),
                target_object=item.get("target_object"),
            )
            for item in data.get("waypoints", [])
        ]
        return cls(
            name=str(data["name"]),
            prompt=str(data.get("prompt", "")),
            robot=robot,
            objects=[SceneObject.from_mapping(item) for item in data.get("objects", [])],
            waypoints=waypoints,
            success_conditions=[str(item) for item in data.get("success_conditions", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> None:
        if not self.name:
            raise TaskValidationError("task name is required")
        if not self.objects:
            raise TaskValidationError("at least one scene object is required")
        if len(self.waypoints) < 2:
            raise TaskValidationError("at least two waypoints are required")

        ids = [obj.object_id for obj in self.objects]
        if len(ids) != len(set(ids)):
            raise TaskValidationError("object ids must be unique")

        known_ids = set(ids)
        for obj in self.objects:
            if any(component <= 0 for component in obj.size):
                raise TaskValidationError(f"object {obj.object_id} has non-positive size")
            if obj.mass_kg < 0:
                raise TaskValidationError(f"object {obj.object_id} has negative mass")

        last_time = -1.0
        for waypoint in self.waypoints:
            if waypoint.time_s <= last_time:
                raise TaskValidationError("waypoint times must be strictly increasing")
            last_time = waypoint.time_s
            if waypoint.target_object and waypoint.target_object not in known_ids:
                raise TaskValidationError(f"unknown waypoint target object: {waypoint.target_object}")


def validate_task_dict(data: Mapping[str, Any]) -> SimulationTask:
    task = SimulationTask.from_dict(data)
    task.validate()
    return task


def object_by_id(objects: Iterable[SceneObject], object_id: str) -> SceneObject:
    for obj in objects:
        if obj.object_id == object_id:
            return obj
    raise TaskValidationError(f"unknown object id: {object_id}")
