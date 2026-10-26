# Cosmos Robot SimGen

An experimental prompt-to-scene-package toolkit for robotics simulation workflows.
It exports MJCF, URDF, OBJ meshes, and task metadata in a Real2Motrix-style layout,
with an optional Cosmos3 Nano video attachment.

**Status: experimental Alpha (`0.1.0a1`).** Original source code is licensed under
[Apache-2.0](LICENSE). This is a static scene-package prototype, not a completed
robotics task execution system. See the
[release assessment](docs/open-source-readiness.zh-CN.md) and
[video / launch kit](docs/launch/README.md).

## What actually works

- A keyword-based compiler builds a fixed pick-and-place scene template.
- The exporter writes scene files, metadata, and a ZIP package.
- The validator checks package structure and references.
- The optional MuJoCo check loads the MJCF and runs `mj_forward`.
- The optional HTTP client accepts a NIM-style JSON response containing `b64_video`.

## Current limitations

The exported scene is static. There is no articulated robot, gripper controller,
dynamic manipulation rollout, or executable success evaluator. Waypoints and
success conditions are metadata, not executed actions. All generated object
meshes are boxes, even when their semantic labels say bottle, cup, or sphere.

The scene and waypoints are computed by rules before calling Cosmos. A returned
video is saved alongside the scene; it is not used to reconstruct geometry or
infer actions. No live Cosmos inference result has been verified for this release.

Real2Motrix preview and package validation do not establish native MotrixSim
execution compatibility. A successful MuJoCo load also does not establish task
success. Native MotrixSim import and execution need a separately recorded test.

The project deliberately separates two paths:

- Optional model request: calls a NIM-style endpoint and saves the response as an MP4 attachment. This client is not directly compatible with vLLM-Omni's native video endpoint.
- Local structural validation: `--skip-cosmos` builds and validates the MotrixSim package without pretending a model ran.

## Why Cosmos3 Nano

Cosmos3 Nano is an optional world-model integration target. The current client
expects the NIM-style `b64_video` response contract. NVIDIA's current model card
also documents vLLM-Omni video serving, which requires a different client adapter.
Model weights and upstream sample media are not included in this project's source
release. Check the model revision and its license separately from this repository.

Primary references:

- [NVIDIA NIM model card: cosmos3-nano](https://build.nvidia.com/nvidia/cosmos3-nano/modelcard)
- [Hugging Face: nvidia/Cosmos3-Nano](https://huggingface.co/nvidia/Cosmos3-Nano)
- [NVIDIA Cosmos 3 research page](https://research.nvidia.com/labs/cosmos-lab/cosmos3/)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Generate a local package without model inference

Use this first to verify local scene-package generation (no GPU required):

```bash
cosmos-simgen generate \
  --name warehouse_pick_place \
  --prompt "A robot arm picks a blue cube from a work table and places it into a yellow bin." \
  --out outputs \
  --skip-cosmos
```

Validate the generated package:

```bash
cosmos-simgen validate outputs/warehouse_pick_place
# or validate the package folder directly
cosmos-simgen validate outputs/warehouse_pick_place/motrix_scene
```

Existing output directories are never overwritten. Use a new `--name` or `--out`
when repeating a generation command. This also applies to `make smoke`.

## Generate with Cosmos3 Nano

Point the CLI at a local or hosted Cosmos3 Nano endpoint that accepts the NIM-style JSON body and returns `b64_video`.

```bash
export COSMOS3_NANO_URL="http://127.0.0.1:8000/v1/infer"
# For NVIDIA hosted endpoints, set the exact endpoint URL and API key:
# export COSMOS3_NANO_URL="https://..."
# export NVIDIA_API_KEY="..."

cosmos-simgen generate \
  --name warehouse_pick_place_cosmos \
  --prompt "A robot arm picks a blue cube from a work table and places it into a yellow bin." \
  --out outputs \
  --resolution 720_16_9 \
  --frames 189 \
  --seed 42
```

## Pull Cosmos3 Nano assets

Cosmos3 Nano is large, so the helper pulls only the model repo assets by default. Set `COSMOS_PULL_FULL=1` only when you intentionally want the full checkpoint tree and have accepted the model license/storage cost.

```bash
scripts/pull_cosmos3_nano_assets.sh
COSMOS_PULL_FULL=1 scripts/pull_cosmos3_nano_assets.sh
```

## MotrixSim package layout

Each generated project directory contains a Real2Motrix-style `motrix_scene` folder plus a sibling zip:

```text
outputs/<task_name>/
  motrix_scene/
    scene.xml
    scene.urdf
    scene.json
    meshes/
      scene_visual.obj
      scene_collision.obj
      objects/<object_id>/visual.obj
      objects/<object_id>/collision.obj
    metadata/
      asset_manifest.json
      scene_manifest.json
      object_manifest.json
      semantic.json
      generation_report.json
      validation_report.json
    raw/
      source_info.json
      cosmos_preview.mp4        # only when Cosmos3 Nano inference ran
  motrix_scene.zip
```

The exporter follows the package shape used by Real2Motrix: `scene.xml`, `scene.urdf`, `scene.json`, `meshes/`, `metadata/asset_manifest.json`, `raw/source_info.json`, and `motrix_scene.zip`.

Current local smoke output:

```text
outputs/smoke_demo/motrix_scene/
outputs/smoke_demo/motrix_scene.zip
```

This package has been validated by both the local validator and the Real2Motrix validator.

## Runtime readiness

Run preflight before claiming a real model-backed result:

```bash
cosmos-simgen doctor
make doctor
```

If you have a compatible Real2Motrix checkout, set its location and validate:

```bash
REAL2MOTRIX_DIR=/path/to/Real2Motrix make validate-real2motrix
```

To register the generated package as a real Real2Motrix project for browser preview:

```bash
REAL2MOTRIX_DIR=/path/to/Real2Motrix make import-real2motrix
```

The import helper writes to that checkout's database through internal APIs;
use a disposable development instance, not a production service. The default
checkout path is `../Real2Motrix`; `doctor` accepts `--real2motrix-dir` explicitly.
Preflight flags check configuration and file presence, not successful inference.

To verify the MJCF scene with a real physics loader, use Python 3.10+ for the optional MuJoCo dependency:

```bash
python -m pip install -e ".[sim]"
make simcheck
```

The legacy `serve-cosmos-vllm` helper starts the reasoner architecture. It does
**not** provide the video-generation API expected by this client and is not an
end-to-end video deployment recipe. Do not use it as release verification:

```bash
make serve-cosmos-vllm
```

The June 2026 development environment reported the following. Run `doctor` again
to check your current machine:

- Real2Motrix validator: available and importable.
- Cosmos3 Nano lightweight assets: available under `vendor/Cosmos3-Nano/assets`.
- Cosmos3 Nano endpoint/API key: not configured.
- Full local checkpoint and CUDA/vLLM runtime: not available.

That means MotrixSim package generation and Real2Motrix validation are real locally; model-backed Cosmos video generation requires a configured remote endpoint or a separate CUDA-capable host.

## Development checks

```bash
make test
make coverage
make smoke
make validate-smoke
make doctor
make simcheck
make validate-real2motrix
```

## License and contributions

See [LICENSE](LICENSE), [NOTICE](NOTICE), and [third-party notices](THIRD_PARTY_NOTICES.md).
Model weights, upstream media, and simulator binaries are not included and are
not relicensed by this repository. This is an independent project, not an
official NVIDIA or MotrixSim release.

Reproducible bug reports and focused pull requests are welcome. Include your
Python/OS versions, command, observed output, and expected behavior; remove
credentials and private paths. Run `make coverage` before submitting code.
