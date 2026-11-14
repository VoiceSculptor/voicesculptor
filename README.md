# 声刻 Studio

> 本地语音克隆 / 情感 TTS（CosyVoice3 + CAM++ 评测）。依赖由 **uv** 管理，模型权重单独分发。

## 环境要求

- Windows 10/11 64 位
- NVIDIA 独显，显存 ≥ 8GB；驱动 ≥ 570（CUDA 12.8）
- 已安装 [uv](https://docs.astral.sh/uv/)：`winget install astral-sh.uv`
- Python 3.11（uv 会按 `.python-version` 自动下载；不要用 3.12+，`pyworld` 没有对应轮子）

## 安装

```bash
git clone --recurse-submodules https://github.com/VoiceSculptor/voicesculptor.git
cd voicesculptor
```

从 GitHub Release 下载 6 个权重文件，放到：

```
engine/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B/
├─ llm.pt / flow.pt / hift.pt / campplus.onnx / speech_tokenizer_v3.onnx
└─ CosyVoice-BlankEN/model.safetensors
```

## 运行

双击 `启动-声刻.cmd`。首次运行会自动 `uv sync`，下载 CUDA 版 torch 等约 4GB 依赖，可能需要 10 分钟以上；看到「引擎就绪」后再打开 http://127.0.0.1:8091

模型默认从仓库内 `engine/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B` 读取；如果权重放在别处，启动前设置环境变量 `COSYVOICE_MODEL_DIR` 指向该目录。

## 目录

```
app/                Studio 后端 + 前端
engine/CosyVoice/   引擎（git submodule，独立仓库）
runtime/roxy-*/     内置情绪参考音频
logs/               运行日志
```

## 出问题

双击 `诊断.cmd`，把 `logs\诊断报告.txt` 发回。

## 说明

仅用于课程/竞赛演示与学习，勿商用或模仿真人声音对外发布。
