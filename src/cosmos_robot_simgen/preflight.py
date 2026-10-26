from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_MODEL_DIR = Path("vendor/Cosmos3-Nano")
DEFAULT_REAL2MOTRIX_DIR = Path("../Real2Motrix")


def run_preflight(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    real2motrix_dir: Path = DEFAULT_REAL2MOTRIX_DIR,
    cosmos_url: Optional[str] = None,
) -> Dict[str, Any]:
    endpoint = cosmos_url or os.environ.get("COSMOS3_NANO_URL", "")
    api_key_present = bool(os.environ.get("NVIDIA_API_KEY") or os.environ.get("COSMOS3_NANO_API_KEY"))
    model_dir = Path(model_dir)
    real2motrix_dir = Path(real2motrix_dir)

    checks = {
        "cosmos_endpoint_configured": _check(bool(endpoint), "COSMOS3_NANO_URL or --cosmos-url is configured"),
        "cosmos_api_key_configured": _check(api_key_present, "NVIDIA_API_KEY/COSMOS3_NANO_API_KEY is configured when required"),
        "cosmos_lightweight_assets": _check(
            (model_dir / "assets").exists() and any((model_dir / "assets").glob("*")),
            f"lightweight Cosmos3 Nano assets exist in {model_dir / 'assets'}",
        ),
        "cosmos_full_checkpoint": _check(_looks_like_full_checkpoint(model_dir), f"full checkpoint files exist in {model_dir}"),
        "vllm_available": _check(shutil.which("vllm") is not None, "vllm executable is on PATH"),
        "nvidia_smi_available": _check(shutil.which("nvidia-smi") is not None, "nvidia-smi executable is on PATH"),
        "real2motrix_validator_available": _check(
            (real2motrix_dir / "backend" / "app" / "pipeline" / "motrix" / "validate.py").exists(),
            f"Real2Motrix validator exists under {real2motrix_dir}",
        ),
        "real2motrix_venv_available": _check(
            (real2motrix_dir / ".venv" / "bin" / "python").exists(),
            f"Real2Motrix virtualenv exists under {real2motrix_dir / '.venv'}",
        ),
        "mujoco_available": _check(_can_import("mujoco"), "mujoco Python package imports successfully"),
    }
    checks["real2motrix_validator_importable"] = _check_real2motrix_import(real2motrix_dir)

    return {
        "ready_for_remote_cosmos_generation": bool(endpoint),
        "ready_for_local_vllm_generation": checks["cosmos_full_checkpoint"]["ok"] and checks["vllm_available"]["ok"],
        "ready_for_real2motrix_validation": checks["real2motrix_validator_importable"]["ok"],
        "checks": checks,
        "notes": [
            "Remote/hosted Cosmos generation requires an endpoint and may require an API key.",
            "Local vLLM generation needs the full checkpoint and CUDA-class hardware; lightweight assets alone are not enough.",
            "MotrixSim app import cannot be automated unless the simulator or web viewer is installed and scriptable on this machine.",
        ],
    }


def _check(ok: bool, message: str) -> Dict[str, Any]:
    return {"ok": bool(ok), "message": message}


def _looks_like_full_checkpoint(model_dir: Path) -> bool:
    if not model_dir.exists():
        return False
    checkpoint_patterns = ["*.safetensors", "*.bin", "*.pt", "model_index.json", "config.json"]
    return any(any(model_dir.rglob(pattern)) for pattern in checkpoint_patterns)


def _can_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _check_real2motrix_import(real2motrix_dir: Path) -> Dict[str, Any]:
    python = real2motrix_dir / ".venv" / "bin" / "python"
    if not python.exists():
        return _check(False, "Real2Motrix virtualenv python is missing")
    code = "from app.pipeline.motrix.validate import validate_package; print('ok')"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(real2motrix_dir / "backend")
    try:
        result = subprocess.run(
            [str(python), "-c", code],
            cwd=str(real2motrix_dir / "backend"),
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        return _check(False, f"Real2Motrix validator import failed: {exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return _check(False, f"Real2Motrix validator import failed: {detail}")
    return _check(True, "Real2Motrix validator imports successfully")
