# 原型介绍片与发布准备

四个平台：B站、YouTube、抖音、小红书。本文为发布素材说明，
不代表平台已投稿或公开视频；实际结果以平台回执为准。

## 可审阅产物

生成目录：`outputs/launch_review/`，不进入源码仓库。

- `prototype-landscape.mp4`：1920x1080，中文合成配音、中文字幕。
- `prototype-portrait.mp4`：1080x1920，重新排版的短版。
- `prototype-landscape.en.srt`：横屏片英文字幕，供 YouTube 使用。
- `prototype-landscape.zh.srt`、`prototype-portrait.zh.srt`：字幕原文。
- `poster-landscape.jpg`、`poster-portrait.jpg`：实际场景封面。
- `evidence.json`：新生成包的校验、MuJoCo 载入、文件指纹和媒体参数。
- `review-sheet.jpg`：横竖版关键帧检查图。

片子是静态场景包工具的原型介绍，不包含 Cosmos 生成画面或机器人执行片段。
相机环绕图直接由导出的 MJCF 通过 MuJoCo renderer 产生；没有添加虚构机器人。
配音使用 macOS 标准中文合成音，不克隆真人声音；没有背景音乐。
字幕、数据排版是说明性合成，不能称为终端录屏。

## 复现视频

本次制作需要 Python 3.12、MuJoCo、Pillow、FFmpeg，以及 macOS `say`。
字体默认使用 macOS 自带的 Arial Unicode / Menlo；不将字体文件复制进仓库。
源码本身的安装与测试不需要这些媒体工具。

```bash
python3.12 -m venv .venv-media
.venv-media/bin/python -m pip install -r docs/launch/requirements.txt
.venv-media/bin/python scripts/build_launch_preview.py
```

脚本在新的日期时间子目录生成示例包，避免覆盖已有用户任务。
主视频文件同名时默认拒绝覆写；重新制作请用 `--out outputs/launch_review_v2`。
具体镜头与旁白在 [storyboard.json](storyboard.json)。

## B站文案

标题：从一句任务描述到仿真场景包：Cosmos Robot SimGen 原型实测

简介：我在做一个机器人仿真场景包工具。当前版本通过规则模板，
把任务描述整理为 MJCF、URDF、OBJ 和元数据，并进行包校验与 MuJoCo 载入检查。
这次展示的是静态场景原型，机器人抓取控制、自动成功判定以及 Cosmos 真机推理
尚未完成。源码以 Apache-2.0 发布为实验性 Alpha；视频录制于发布准备阶段。
项目：https://github.com/eust-w/cosmos-robot-simgen
视频为项目真实产物渲染，配音为合成语音。

标签：机器人仿真、具身智能、MuJoCo、开发日志、Python

置顶提问：你最希望首先支持抓取、推物体，还是分类放置？

## YouTube 文案

Title: From a Task Prompt to a Simulation Scene Package | Cosmos Robot SimGen Prototype

Description: A prototype toolkit that compiles a task prompt into a template-based
scene package: MJCF, URDF, OBJ meshes, and metadata. This video shows real exported
geometry rendered in MuJoCo. The scene is static; there is no robot controller,
task-success evaluation, or verified Cosmos inference in this demo. Experimental
Alpha source: https://github.com/eust-w/cosmos-robot-simgen (Apache-2.0).
Recorded during release preparation. Mandarin synthetic narration; English
subtitles included. This is an independent project, not an official NVIDIA release.

Tags: robotics simulation, MuJoCo, scene generation, Python, development log

## 抖音文案

标题：一句任务描述，先把仿真场景搭起来

正文：这个机器人仿真工具以 Apache-2.0 开源了实验性 Alpha。当前能生成场景包并做载入检查，
画面是实际导出几何的静态渲染。下一步补机器人、控制器和成功判定。
原型演示，合成配音。#机器人仿真 #具身智能 #开发记录

## 小红书文案

标题：我做了个机器人仿真场景包原型

正文：想减少机器人实验前整理场景文件的工作，于是先做了一个任务描述到场景包的工具。
当前支持模板化 MJCF / URDF / OBJ 导出，保留任务元数据，也能用 MuJoCo 做载入检查。
目前仍是静态场景，没有把机器人抓取说成已经跑通；Cosmos 推理也还在待联调列表。
源码以 Apache-2.0 开源为实验性 Alpha，项目名 Cosmos Robot SimGen。
你平时搭仿真场景最费时间的是哪一步？
原型演示 / 合成配音。

## 发布顺序与账号

上述文案均为原型版，不能替换成“一键完整闭环”后直接发布。
文案中的开源链接须在仓库和 Alpha Release 公开核验后才用于平台投稿。

正式首发建议先完成公开 Release 与复现指南，再同步 B站 / YouTube 技术演示，
随后发布抖音 / 小红书短版。更新字幕中的状态和代码链接要与发布当天事实一致。
横竖版规格是本次编辑选择，不代表各平台官方限制；上传时以账号界面校验为准。

使用发布者已有登录会话上传；发布回执应记录视频 ID、实际链接和可见性。
