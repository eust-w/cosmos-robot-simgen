# v0.1.0-alpha.1: Static Scene-Package Prototype

First experimental source release, licensed under Apache-2.0.

## Available

- Keyword/template-based scene generation, with MJCF, URDF, OBJ and JSON exports.
- ZIP packaging, structural validation, and optional MuJoCo load checks.
- Optional NIM-style Cosmos video-attachment client, tested with fixtures only.
- CLI environment checks and experimental Real2Motrix helpers.
- Refusal to overwrite existing output and validation of export task names.
- Reproducible launch-preview script and subtitles/storyboard sources.

## Important limitations

This is not a model-to-robotics closed loop. All scene meshes are boxes. The
scene is static, with no articulated robot, controller, physical task rollout,
or executable success evaluator. Waypoints are metadata, not executed motion.

No live Cosmos inference or native MotrixSim execution is verified for this
release. Optional model video does not determine geometry or actions. The
legacy vLLM reasoner helper does not serve the client's video API.

Preview videos show real exported geometry with camera motion, not robot
execution. They use synthetic narration and were recorded during release
preparation. Model weights, upstream media, local environment data, and
credentials are excluded from the source release.

See README for a CPU-only generation quick start and the release assessment
for the remaining work. This release is for experimentation, not production.
