import os
import stat
import tempfile
import unittest
from pathlib import Path

from cosmos_robot_simgen.preflight import run_preflight


class PreflightTests(unittest.TestCase):
    def test_preflight_detects_assets_full_checkpoint_and_real2motrix_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_dir = root / "Cosmos3-Nano"
            (model_dir / "assets").mkdir(parents=True)
            (model_dir / "assets" / "example.txt").write_text("prompt", encoding="utf-8")
            (model_dir / "config.json").write_text("{}", encoding="utf-8")

            real2motrix = root / "Real2Motrix"
            (real2motrix / "backend" / "app" / "pipeline" / "motrix").mkdir(parents=True)
            (real2motrix / "backend" / "app" / "pipeline" / "motrix" / "validate.py").write_text(
                "def validate_package(path): return {'valid': True}", encoding="utf-8"
            )
            fake_python = real2motrix / ".venv" / "bin" / "python"
            fake_python.parent.mkdir(parents=True)
            fake_python.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            result = run_preflight(model_dir=model_dir, real2motrix_dir=real2motrix, cosmos_url="http://localhost")

            self.assertTrue(result["ready_for_remote_cosmos_generation"])
            self.assertTrue(result["ready_for_real2motrix_validation"])
            self.assertTrue(result["checks"]["cosmos_lightweight_assets"]["ok"])
            self.assertTrue(result["checks"]["cosmos_full_checkpoint"]["ok"])

    def test_preflight_handles_missing_real2motrix_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_preflight(model_dir=Path(tmp) / "missing", real2motrix_dir=Path(tmp) / "missing")

            self.assertFalse(result["ready_for_real2motrix_validation"])
            self.assertIn("virtualenv python is missing", result["checks"]["real2motrix_validator_importable"]["message"])


if __name__ == "__main__":
    unittest.main()
