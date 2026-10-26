import json
import tempfile
import unittest
from pathlib import Path

from cosmos_robot_simgen.motrix import export_motrix_package, write_package_zip
from cosmos_robot_simgen.planner import compile_prompt_to_task
from cosmos_robot_simgen.validator import validate_package


class ValidatorEdgeTests(unittest.TestCase):
    def test_validator_accepts_generated_cosmos_artifacts_when_files_exist(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "cosmos_files_present")
        cosmos_artifacts = {
            "video": "raw/cosmos_preview.mp4",
            "request": "raw/cosmos_request.json",
            "response_metadata": "raw/cosmos_response_metadata.json",
            "video_sha256": "abc",
            "video_bytes": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp), cosmos_artifacts=cosmos_artifacts)
            (package_dir / "raw" / "cosmos_preview.mp4").write_bytes(b"mp4")
            (package_dir / "raw" / "cosmos_request.json").write_text("{}", encoding="utf-8")
            (package_dir / "raw" / "cosmos_response_metadata.json").write_text("{}", encoding="utf-8")
            write_package_zip(package_dir)

            result = validate_package(package_dir)

            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["warnings"], [])

    def test_validator_rejects_bad_scene_type_and_absolute_paths(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "bad_scene_json")

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            scene_json_path = package_dir / "scene.json"
            scene_json = json.loads(scene_json_path.read_text(encoding="utf-8"))
            scene_json["type"] = "bad"
            scene_json["assets"]["visual_mesh"] = "/tmp/bad.obj"
            scene_json_path.write_text(json.dumps(scene_json), encoding="utf-8")

            result = validate_package(package_dir)

            self.assertFalse(result["valid"])
            self.assertTrue(any("type must be motrix_scene_package" in error for error in result["errors"]))
            self.assertTrue(any("relative and portable" in error for error in result["errors"]))

    def test_validator_rejects_bad_object_count_and_bbox(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "bad_manifest")

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            object_manifest_path = package_dir / "metadata" / "object_manifest.json"
            object_manifest = json.loads(object_manifest_path.read_text(encoding="utf-8"))
            object_manifest["count"] = 99
            object_manifest_path.write_text(json.dumps(object_manifest), encoding="utf-8")

            asset_manifest_path = package_dir / "metadata" / "asset_manifest.json"
            asset_manifest = json.loads(asset_manifest_path.read_text(encoding="utf-8"))
            asset_manifest["bbox"] = [[0, 0, -1], [1, 1, 1]]
            asset_manifest_path.write_text(json.dumps(asset_manifest), encoding="utf-8")

            result = validate_package(package_dir)

            self.assertFalse(result["valid"])
            self.assertTrue(any("count must match" in error for error in result["errors"]))
            self.assertTrue(any("lowest z" in error for error in result["errors"]))

    def test_validator_rejects_missing_zip(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "missing_zip")

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            (package_dir.parent / "motrix_scene.zip").unlink()

            result = validate_package(package_dir)

            self.assertFalse(result["valid"])
            self.assertIn("missing motrix_scene.zip", result["errors"])


if __name__ == "__main__":
    unittest.main()
