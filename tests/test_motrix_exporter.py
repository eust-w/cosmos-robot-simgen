import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cosmos_robot_simgen.motrix import export_motrix_package
from cosmos_robot_simgen.planner import compile_prompt_to_task
from cosmos_robot_simgen.validator import validate_package


class MotrixExporterTests(unittest.TestCase):
    def test_existing_output_is_preserved(self):
        task = compile_prompt_to_task("Pick a cube.", "preserve_me")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / task.name
            original.mkdir()
            marker = original / "user-data.txt"
            marker.write_text("keep me", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_motrix_package(task, root)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")

    def test_unsafe_task_names_are_rejected(self):
        task = compile_prompt_to_task("Pick a cube.", "safe")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            for name in ["..", "../escape", str(Path(tmp) / "absolute"), "nested/name", "nested\\name", "a" * 129]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    export_motrix_package(replace(task, name=name), root)
            self.assertFalse(root.exists())

    def test_output_symlink_is_not_followed(self):
        task = compile_prompt_to_task("Pick a cube.", "linked")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "outside"
            (root / task.name).symlink_to(destination, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                export_motrix_package(task, root)
            self.assertFalse(destination.exists())

    def test_export_package_contains_motrix_entrypoints_and_zip(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "motrix_demo")

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            result = validate_package(package_dir)

            self.assertTrue(result["valid"], result["errors"])
            self.assertTrue((package_dir / "scene.xml").exists())
            self.assertTrue((package_dir / "scene.urdf").exists())
            self.assertTrue((package_dir / "scene.json").exists())
            self.assertTrue((package_dir / "metadata" / "asset_manifest.json").exists())
            self.assertTrue((package_dir / "meshes" / "scene_visual.obj").exists())
            self.assertTrue((package_dir.parent / "motrix_scene.zip").exists())

    def test_export_records_cosmos_artifacts_when_present(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "with_cosmos")
        cosmos_artifacts = {"video": "raw/cosmos_preview.mp4", "video_sha256": "abc", "video_bytes": 3}

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp), cosmos_artifacts=cosmos_artifacts)
            manifest = json.loads((package_dir / "metadata" / "asset_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["cosmos"]["preview_status"], "generated")
            self.assertEqual(manifest["cosmos"]["artifacts"]["video"], "raw/cosmos_preview.mp4")
            self.assertEqual(manifest["import"]["type"], "motrix_scene_package")

    def test_validator_rejects_generated_cosmos_metadata_without_files(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "missing_cosmos_files")
        cosmos_artifacts = {
            "video": "raw/cosmos_preview.mp4",
            "request": "raw/cosmos_request.json",
            "response_metadata": "raw/cosmos_response_metadata.json",
            "video_sha256": "abc",
            "video_bytes": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp), cosmos_artifacts=cosmos_artifacts)
            result = validate_package(package_dir)

            self.assertFalse(result["valid"])
            self.assertTrue(any("missing generated Cosmos artifact" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
