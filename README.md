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

双击 `启动-声刻.cmd`。首次运行会自动 `uv sync`，下载 CUDA 版 torch 等约 4GB 依赖，可能需要 10 分钟以上；脚本在引擎/应用就绪后会自动打开 http://127.0.0.1:8091（也可以手动访问）。

仓库中的 `.cmd`/`.bat` 文件统一为 **ASCII 内容 + CRLF 换行**，不依赖 Windows 的系统区域或控制台代码页，也能兼容常见的 ASCII 兼容编码。修改启动脚本时不要加入中文或其他非 ASCII 字符；中文文档和 Python 源码使用 UTF-8。Git 会按 `.gitattributes` 处理批处理文件的换行。

模型默认从仓库内 `engine/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B` 读取；如果权重放在别处，启动前设置环境变量 `COSYVOICE_MODEL_DIR` 指向该目录（启动器、引擎启动脚本、应用都会读取）。

想再快一点可设置 `COSYVOICE_FP16=1` 后启动引擎（fp16 推理，仅 CUDA 生效，显存占用更低；个别显卡音质可能有轻微波动，默认关闭）。

## 情绪模式

- **auto**：有情绪指令时自动用 instruct2（情绪优先）；参考音色本身即目标情绪时用 zero_shot。
- **zero_shot**：只复刻参考音频的音色与语气，emotion 参数不生效。
- **instruct2**：按情绪指令合成，情绪更明显，但音色相似度可能略降。

## 情绪识别服务（可选，端口 50001）

`emotion/` 是独立的情绪识别服务（emotion2vec_plus_large，FunASR，默认 CPU 推理），`启动-声刻.cmd` 会自动拉起它，日志写在 `logs\emotion.log`。首次启动要下载模型到 ModelScope 缓存（约 1GB 以上）。服务没起来时 Studio 照常合成，只是不显示"实际情绪"，best 模式也不做情绪择优。

- 用 GPU：启动前设置 `EMOTION_DEVICE=cuda:0`
- 不启动它：设置 `VS_NO_EMOTION=1`
- 能识别：生气 / 开心 / 平静 / 难过 / 惊讶（"撒娇"没有对应类别）

## 目录

```
app/                Studio 后端 + 前端
engine/CosyVoice/   引擎（git submodule，独立仓库）
emotion/            情绪识别服务（50001，可选）
emotion/            情绪识别服务（50001，可选）
runtime/roxy-*/     内置情绪参考音频
logs/               运行日志
```

## 出问题

双击 `诊断.cmd`，把 `logs\diagnostic-report.txt` 发回。

## 说明

仅用于课程/竞赛演示与学习，勿商用或模仿真人声音对外发布。
