import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from cosmos_robot_simgen.motrix import export_motrix_package
from cosmos_robot_simgen.planner import compile_prompt_to_task
from cosmos_robot_simgen.simcheck import run_mujoco_check


class SimcheckTests(unittest.TestCase):
    def test_simcheck_rejects_missing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_mujoco_check(Path(tmp) / "missing")

            self.assertFalse(result["valid"])
            self.assertIn("motrix_scene", result["errors"][0])

    def test_simcheck_reports_missing_mujoco(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "simcheck_missing_mujoco")
        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            with mock.patch.dict(sys.modules, {"mujoco": None}):
                result = run_mujoco_check(package_dir)

            self.assertFalse(result["valid"])
            self.assertTrue(any("mujoco Python package" in error for error in result["errors"]))

    def test_simcheck_accepts_mocked_mujoco_loader(self):
        task = compile_prompt_to_task("Pick a cube into a yellow bin.", "simcheck_ok")

        class FakeModel:
            nbody = 2
            ngeom = 3
            nmesh = 2
            nq = 0
            nv = 0

            @classmethod
            def from_xml_path(cls, path):
                return cls()

        fake_mujoco = types.SimpleNamespace(
            MjModel=FakeModel,
            MjData=lambda model: object(),
            mj_forward=lambda model, data: None,
        )

        with tempfile.TemporaryDirectory() as tmp:
            package_dir = export_motrix_package(task, Path(tmp))
            with mock.patch.dict(sys.modules, {"mujoco": fake_mujoco}):
                result = run_mujoco_check(package_dir)

            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["summary"]["nmesh"], 2)


if __name__ == "__main__":
    unittest.main()
