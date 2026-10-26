"""Render an explicitly labelled prototype video from a fresh exported scene."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS = 24
CJK = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"
BG = "#F4F6F5"
INK = "#172723"
MUTED = "#53665F"
TEAL = "#16765F"
CORAL = "#B44835"


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def media_info(path):
    return json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ]).stdout)


def label(draw, xy, text, size, width, color=INK, mono=False):
    font = ImageFont.truetype(MONO if mono else CJK, size)
    while draw.textlength(text, font=font) > width and size > 18:
        size -= 1
        font = ImageFont.truetype(MONO if mono else CJK, size)
    if draw.textlength(text, font=font) > width:
        raise ValueError(f"Text cannot fit: {text}")
    draw.text(xy, text, fill=color, font=font)


def cli(*args):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    output = run([sys.executable, "-m", "cosmos_robot_simgen.cli", *args], cwd=ROOT, env=env).stdout
    return json.JSONDecoder().raw_decode(output)[0]


def capture_scene(package, dest):
    model = mujoco.MjModel.from_xml_path(str(package / "scene.xml"))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    if model.nq != 0 or model.nu != 0:
        raise RuntimeError("Storyboard describes a static scene; update it before recording a dynamic model")
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 600
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0.12, 0.0, 0.18]
    camera.distance = 3.65
    camera.elevation = -32
    frames = []
    with mujoco.Renderer(model, height=600, width=960) as renderer:
        for index in range(FPS * 8):
            camera.azimuth = 120 + 20 * math.sin(2 * math.pi * index / (FPS * 8))
            renderer.update_scene(data, camera=camera)
            frames.append(Image.fromarray(renderer.render().copy()))
    pixels = np.asarray(frames[0])
    changed = float(np.abs(pixels.astype(float) - np.asarray(frames[FPS * 2]).astype(float)).mean())
    if pixels.std() < 8 or changed < 0.2:
        raise RuntimeError("Scene render is blank or camera is not moving")
    frames[0].save(dest / "scene-render.png")
    return frames, {
        "engine": "mujoco", "version": mujoco.__version__,
        "nbody": model.nbody, "ngeom": model.ngeom, "nq": model.nq,
        "nv": model.nv, "nu": model.nu, "pixel_std": float(pixels.std()),
        "camera_frame_difference": changed, "motion": "camera orbit only; scene is static",
    }


def facts(scene, evidence):
    identity = scene["id"]
    if identity == "package":
        return ["motrix_scene/", "  scene.xml", "  scene.urdf", "  scene.json", "  meshes/", "  metadata/", "  raw/source_info.json"]
    if identity == "verify":
        summary = evidence["simcheck"]["summary"]
        return ["LOADER CHECK", "MuJoCo: loaded", f"nbody = {summary['nbody']}",
                f"ngeom = {summary['ngeom']}", f"nq = {summary['nq']} / nv = {summary['nv']}",
                "Robot control: not implemented"]
    if identity == "cosmos":
        return ["INFERENCE STATUS", "Cosmos: skipped", "Video: not generated", "Client: NIM-style JSON", "Model-to-action: pending"]
    if identity == "prompt":
        return ["PROMPT", "Pick a blue cube", "and place it in", "a yellow bin.", "", "Compiler: rule template"]
    if identity == "next":
        return ["NEXT MILESTONE", "Robot model", "Closed-loop controller", "Measured task outcome", "Reproducible release"]
    return ["CURRENT OUTPUT", "MJCF + URDF", "OBJ + JSON", "Package validation", "Static scene preview"]


def compose(scene, rendered, size, evidence, progress=0.0):
    width, height = size
    portrait = height > width
    canvas = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(canvas)
    pad = 80
    label(draw, (pad, 38 if not portrait else 82), "COSMOS ROBOT SIMGEN", 29, width - pad * 2, TEAL, True)
    label(draw, (pad, 102 if not portrait else 153), scene["eyebrow"], 24, width - pad * 2, MUTED, True)
    top = 146 if not portrait else 214
    for index, line in enumerate(scene["headline"]):
        label(draw, (pad, top + index * 84), line, 68, width - 2 * pad)
    label(draw, (pad, 322 if not portrait else 402), scene["detail"], 30, width - 2 * pad, TEAL)
    if portrait:
        rect = (80, 490, 920, 575)
        fx, fy, fw, font = 80, 1160, 920, 32
    else:
        rect = (80, 390, 1040, 650)
        fx, fy, fw, font = 1190, 452, 650, 30
    x, y, w, h = rect
    canvas.paste(rendered.resize((w, h), Image.Resampling.LANCZOS), (x, y))
    draw = ImageDraw.Draw(canvas)
    label(draw, (x + 22, y + 18), "MJCF RENDER / STATIC SCENE", 22, w - 44, "#D3E5DC", True)
    for index, line in enumerate(facts(scene, evidence)):
        label(draw, (fx, fy + index * (53 if portrait else 52)), line, font, fw,
              TEAL if index == 0 else INK, True)
    # The vertical layout reserves the platform interaction and subtitle margins.
    if portrait:
        caption_y = 1585
        draw.rectangle((0, caption_y - 28, width, height), fill=INK)
        for index, line in enumerate(scene["subtitle"]):
            label(draw, (pad, caption_y + index * 65), line, 40, width - 2 * pad, "#FFFFFF")
        label(draw, (pad, 1760), "原型预览 / 合成配音 / 正在准备开源", 27, width - 2 * pad, "#BDD0C5")
    else:
        for index, line in enumerate(scene["subtitle"]):
            label(draw, (fx, 834 + index * 54), line, 31, fw, CORAL if index else INK)
        label(draw, (fx, 988), "原型预览 / 合成配音 / 正在准备开源", 25, fw, MUTED)
    draw.rectangle((0, height - 6, int(width * progress), height), fill=TEAL)
    return canvas


def subtitle_time(seconds):
    milliseconds = round(seconds * 1000)
    whole, ms = divmod(milliseconds, 1000)
    minutes, sec = divmod(whole, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02}:{minute:02}:{sec:02},{ms:03}"


def write_subtitles(path, scenes, english=False):
    blocks, cursor = [], 0.0
    for index, scene in enumerate(scenes):
        end = cursor + scene["duration"]
        text = scene["english"] if english else "\n".join(scene["subtitle"])
        blocks.append(f"{index + 1}\n{subtitle_time(cursor)} --> {subtitle_time(end)}\n{text}\n")
        cursor = end
    path.write_text("\n".join(blocks), encoding="utf-8")


def encode(scenes, frames, evidence, size, name, dest):
    raw = dest / f"{name}.silent.mp4"
    duration = sum(scene["duration"] for scene in scenes)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "pipe:0", "-an",
           "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", str(raw)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    completed = 0
    reviews = []
    try:
        for scene in scenes:
            print(f"Rendering {name}: {scene['id']}", flush=True)
            count = round(scene["duration"] * FPS)
            # Compose each camera-loop frame once per chapter; reuse it during narration.
            layouts = [compose(scene, frame, size, evidence) for frame in frames]
            review = layouts[0].copy()
            review.save(dest / f"{name}-{scene['id']}.jpg", quality=88)
            reviews.append(review)
            for index in range(count):
                canvas = layouts[index % len(layouts)].copy()
                draw = ImageDraw.Draw(canvas)
                draw.rectangle((0, size[1] - 6, int(size[0] * completed / (FPS * duration)), size[1]), fill=TEAL)
                process.stdin.write(canvas.tobytes())
                completed += 1
            del layouts
    finally:
        process.stdin.close()
        code = process.wait()
    if code:
        raise RuntimeError(f"FFmpeg encoder exited {code}")
    audio_list = dest / f"{name}.audio.txt"
    audio_list.write_text("".join(f"file 'voice-{scene['id']}.wav'\n" for scene in scenes), encoding="utf-8")
    target = dest / f"{name}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-f", "concat", "-safe", "1",
         "-i", str(audio_list), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(target)])
    raw.unlink()
    run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"])
    write_subtitles(dest / f"{name}.zh.srt", scenes)
    write_subtitles(dest / f"{name}.en.srt", scenes, english=True)
    reviews[0].save(dest / ("poster-portrait.jpg" if size[1] > size[0] else "poster-landscape.jpg"), quality=93)
    info = media_info(target)
    tracks = info["streams"]
    video = next(s for s in tracks if s["codec_type"] == "video")
    audio = next(s for s in tracks if s["codec_type"] == "audio")
    if (video["width"], video["height"]) != size or abs(float(info["format"]["duration"]) - duration) > 0.2:
        raise RuntimeError("Encoded media dimensions/duration do not match the storyboard")
    return reviews, {"file": target.name, "duration_s": float(info["format"]["duration"]),
                     "width": video["width"], "height": video["height"], "video_codec": video["codec_name"],
                     "audio_codec": audio["codec_name"], "full_decode": "passed",
                     "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/launch_review")
    args = parser.parse_args()
    for executable in ("ffmpeg", "ffprobe", "say"):
        if not shutil.which(executable):
            parser.error(f"{executable} is required")
    for font in (CJK, MONO):
        if not Path(font).is_file():
            parser.error(f"Font not found: {font}")
    dest = args.out.resolve()
    if dest.exists():
        parser.error(f"Output already exists; select a new --out: {dest}")
    dest.mkdir(parents=True)
    board = json.loads((ROOT / "docs/launch/storyboard.json").read_text(encoding="utf-8"))
    name = "launch_" + uuid.uuid4().hex[:10]
    prompt = "A robot arm picks a blue cube from a work table and places it into a yellow bin."
    generation = cli("generate", "--name", name, "--prompt", prompt, "--out", str(dest), "--skip-cosmos")
    package = dest / name / "motrix_scene"
    validation = cli("validate", str(package))
    simcheck = cli("simcheck", str(package))
    frames, render = capture_scene(package, dest)
    evidence = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "generation": generation, "validation": validation, "simcheck": simcheck,
                "render": render, "cosmos_inference": "skipped", "robot_rollout": "not implemented",
                "package_sha256": hashlib.sha256((package.parent / "motrix_scene.zip").read_bytes()).hexdigest()}
    save_json(dest / "evidence.json", evidence)
    for scene in board["scenes"]:
        print(f"Narrating: {scene['id']}", flush=True)
        speech = dest / f"voice-{scene['id']}.aiff"
        source = dest / f"voice-{scene['id']}.txt"
        source.write_text(scene["narration"], encoding="utf-8")
        run(["say", "-v", "Tingting", "-r", "215", "-f", str(source), "-o", str(speech)])
        seconds = float(media_info(speech)["format"]["duration"])
        scene["duration"] = math.ceil((seconds + 1) * FPS) / FPS
        run(["ffmpeg", "-v", "error", "-y", "-i", str(speech), "-af", "apad",
             "-t", str(scene["duration"]), "-ar", "48000", "-ac", "1", str(dest / f"voice-{scene['id']}.wav")])
    save_json(dest / "timed-storyboard.json", board)
    landscape, info = encode(board["scenes"], frames, evidence, (1920, 1080), "prototype-landscape", dest)
    chosen = [scene for scene in board["scenes"] if scene["id"] in board["portrait_scenes"]]
    portrait, short_info = encode(chosen, frames, evidence, (1080, 1920), "prototype-portrait", dest)
    sheet = Image.new("RGB", (1920, 1320), BG)
    for index, frame in enumerate(landscape):
        sheet.paste(frame.resize((640, 360)), ((index % 3) * 640, (index // 3) * 360))
    for index, frame in enumerate(portrait):
        sheet.paste(frame.resize((324, 576)), (index * 480 + 78, 736))
    sheet.save(dest / "review-sheet.jpg", quality=90)
    evidence["videos"] = [info, short_info]
    save_json(dest / "evidence.json", evidence)
    print(json.dumps(evidence["videos"], indent=2), flush=True)


if __name__ == "__main__":
    main()
