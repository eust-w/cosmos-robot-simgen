from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .cosmos import Cosmos3NanoClient, CosmosClientError, cosmos_artifact_index, write_cosmos_artifacts
from .motrix import export_motrix_package, write_package_zip
from .planner import build_cosmos_prompt, compile_prompt_to_task
from .preflight import DEFAULT_REAL2MOTRIX_DIR, run_preflight
from .simcheck import run_mujoco_check
from .validator import validate_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cosmos-simgen", description="Generate experimental static scene packages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a MotrixSim task package.")
    generate.add_argument("--prompt", required=True, help="Natural-language robot task prompt.")
    generate.add_argument("--name", default="", help="Output task name. Defaults to a prompt-derived slug.")
    generate.add_argument("--out", default="outputs", help="Output root directory.")
    generate.add_argument("--skip-cosmos", action="store_true", help="Skip model inference and only export the task package.")
    generate.add_argument("--cosmos-url", default=None, help="Cosmos3 Nano endpoint. Defaults to COSMOS3_NANO_URL.")
    generate.add_argument("--resolution", default="720_16_9", help="Cosmos output resolution, e.g. 720_16_9.")
    generate.add_argument("--frames", type=int, default=189, help="Cosmos output frame count.")
    generate.add_argument("--fps", type=int, default=24, help="Cosmos output FPS.")
    generate.add_argument("--seed", type=int, default=42, help="Cosmos generation seed.")
    generate.add_argument("--steps", type=int, default=None, help="Optional Cosmos inference steps.")
    generate.add_argument("--guidance-scale", type=float, default=None, help="Optional Cosmos guidance scale.")
    generate.add_argument("--negative-prompt", default=None, help="Optional negative prompt.")
    generate.add_argument("--image", default=None, help="Optional image URL, data URI, or base64 input.")
    generate.set_defaults(func=_cmd_generate)

    validate = subparsers.add_parser("validate", help="Validate a generated MotrixSim package directory.")
    validate.add_argument("package_dir", help="Generated package directory.")
    validate.set_defaults(func=_cmd_validate)

    doctor = subparsers.add_parser("doctor", help="Check real Cosmos/MotrixSim runtime readiness.")
    doctor.add_argument("--cosmos-url", default=None, help="Cosmos3 Nano endpoint. Defaults to COSMOS3_NANO_URL.")
    doctor.add_argument("--model-dir", default="vendor/Cosmos3-Nano", help="Local Cosmos3 Nano model/assets directory.")
    doctor.add_argument(
        "--real2motrix-dir",
        default=str(DEFAULT_REAL2MOTRIX_DIR),
        help="Real2Motrix checkout used for external Motrix package validation.",
    )
    doctor.set_defaults(func=_cmd_doctor)

    simcheck = subparsers.add_parser("simcheck", help="Load the exported MJCF scene with MuJoCo when available.")
    simcheck.add_argument("package_dir", help="Generated project directory or motrix_scene package directory.")
    simcheck.set_defaults(func=_cmd_simcheck)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError) as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        return 2


def _cmd_generate(args: argparse.Namespace) -> int:
    task = compile_prompt_to_task(args.prompt, args.name)
    output_root = Path(args.out).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    project_dir = output_root / task.name
    if project_dir.exists() or project_dir.is_symlink():
        raise FileExistsError(f"Output already exists: {project_dir}. Use a new --name or --out.")

    cosmos_artifacts = None
    generation = None
    if not args.skip_cosmos:
        try:
            client = Cosmos3NanoClient.from_environment(args.cosmos_url)
            generation = client.generate_video(
                build_cosmos_prompt(task),
                resolution=args.resolution,
                num_output_frames=args.frames,
                seed=args.seed,
                fps=args.fps,
                steps=args.steps,
                guidance_scale=args.guidance_scale,
                negative_prompt=args.negative_prompt,
                image=args.image,
            )
        except CosmosClientError as exc:
            print(f"Cosmos3 Nano generation failed: {exc}", file=sys.stderr)
            print("Use --skip-cosmos only for local package-structure validation.", file=sys.stderr)
            return 2
        cosmos_artifacts = cosmos_artifact_index(generation)

    package_dir = export_motrix_package(task, output_root, cosmos_artifacts=cosmos_artifacts)
    if generation is not None:
        write_cosmos_artifacts(package_dir, generation)
        write_package_zip(package_dir)
    result = validate_package(package_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        return 1
    print(f"Generated package: {package_dir}")
    print(f"MotrixSim zip: {package_dir.parent / 'motrix_scene.zip'}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    result = validate_package(Path(args.package_dir).expanduser().resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


def _cmd_doctor(args: argparse.Namespace) -> int:
    result = run_preflight(
        model_dir=Path(args.model_dir).expanduser().resolve(),
        real2motrix_dir=Path(args.real2motrix_dir).expanduser().resolve(),
        cosmos_url=args.cosmos_url,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_simcheck(args: argparse.Namespace) -> int:
    result = run_mujoco_check(Path(args.package_dir).expanduser().resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
