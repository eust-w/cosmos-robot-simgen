import tempfile
import unittest
from pathlib import Path

from cosmos_robot_simgen.cli import main
from cosmos_robot_simgen.cli import build_parser


class CliTests(unittest.TestCase):
    def test_existing_output_returns_error_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing"
            output.mkdir()
            marker = output / "user-data.txt"
            marker.write_text("keep me", encoding="utf-8")
            code = main(["generate", "--name", "existing", "--prompt", "Pick a cube.",
                         "--out", tmp, "--skip-cosmos"])
            self.assertEqual(code, 2)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")

    def test_doctor_default_checkout_is_portable(self):
        args = build_parser().parse_args(["doctor"])
        self.assertFalse(Path(args.real2motrix_dir).is_absolute())

    def test_generate_skip_cosmos_creates_valid_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "generate",
                    "--name",
                    "cli_demo",
                    "--prompt",
                    "A robot arm moves a cube into a yellow bin.",
                    "--out",
                    tmp,
                    "--skip-cosmos",
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "cli_demo" / "motrix_scene").is_dir())
            self.assertTrue((Path(tmp) / "cli_demo" / "motrix_scene.zip").exists())

    def test_validate_returns_nonzero_for_missing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["validate", str(Path(tmp) / "missing")])

            self.assertEqual(code, 1)

    def test_doctor_reports_environment_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "doctor",
                    "--model-dir",
                    str(Path(tmp) / "missing-model"),
                    "--real2motrix-dir",
                    str(Path(tmp) / "missing-real2motrix"),
                ]
            )

            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
