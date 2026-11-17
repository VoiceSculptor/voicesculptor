# 声刻 Studio

> 本地语音克隆 / 情感 TTS（CosyVoice3 + CAM++ 评测）。依赖由 **uv** 管理，模型权重首次启动自动下载。

## 目录结构

```
voicesculptor-repo/
├─ app/                        Studio 应用（FastAPI，端口 8091）
│  ├─ app.py                   兼容入口：uvicorn app:app / python app.py 都走这里
│  ├─ voicesculptor/
│  │  ├─ config.py             运行配置（Settings.from_env）
│  │  ├─ errors.py             异常层级，自带 HTTP 状态码
│  │  ├─ emotions.py           六种情绪与情绪指令文案
│  │  ├─ audio/                波形读写、参考音频预处理、韵律特征
│  │  ├─ speaker/              CAM++ 说话人向量（onnxruntime）
│  │  ├─ voices/               音色库读写、内置种子音色
│  │  ├─ clients/              CosyVoice 引擎与情绪服务客户端
│  │  ├─ synthesis/            请求校验、合成计划、候选排序、合成流水线
│  │  ├─ envcheck/             环境检测（12 项），可命令行独立运行
│  │  ├─ api/                  HTTP 路由与错误处理
│  │  ├─ audit.py              素材体检报告
│  │  └─ main.py               create_app / main
│  ├─ static/                  前端（原生 ES Module，无构建步骤）
│  │  ├─ index.html
│  │  ├─ css/                  tokens / base / layout / components
│  │  └─ js/                   main / api / store / dom / wav
│  │     ├─ components/        状态芯片、音色列表、波形、结果卡等
│  │     └─ views/             合成 / 情绪识别 / 素材体检 / 环境检测
│  ├─ tests/                   pytest + 假引擎 / 假情绪服务
│  └─ voices/                  音色库（参考音频 + meta.json，git 忽略）
├─ emotion/                    情绪识别服务（FunASR，端口 50001）
│  ├─ server.py                兼容入口
│  ├─ voicesculptor_emotion/   config / labels / classifier / api / main
│  └─ tests/
├─ engine/CosyVoice/           CosyVoice 子模块（不改动）
├─ logs/                       运行日志与体检报告（git 忽略）
├─ pylintrc                    Google Python Style 的 pylint 配置
└─ *.cmd                       启动脚本（ASCII 内容 + CRLF 换行）
```

## 环境要求

- Windows 10/11 64 位
- NVIDIA 独显，显存 ≥ 8GB；驱动 ≥ 570（CUDA 12.8）
- 已安装 [uv](https://docs.astral.sh/uv/)：`winget install astral-sh.uv`
- Python 3.11（uv 会自动准备；不要用 3.12+，`pyworld` 没有对应轮子）

## 安装

```bash
git clone --recurse-submodules https://github.com/VoiceSculptor/voicesculptor.git
cd voicesculptor
```

首次双击 `启动-声刻.cmd` 时会自动下载 6 个权重文件（约 5.1 GB），默认放到：

```
engine/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B/
├─ llm.pt / flow.pt / hift.pt / campplus.onnx / speech_tokenizer_v3.onnx
└─ CosyVoice-BlankEN/model.safetensors
```

下载源按 **ModelScope → hf-mirror → HuggingFace** 顺序自动尝试：国内一般走 ModelScope，海外可用 HuggingFace。也可以手动指定：

```bat
set VS_MODEL_SOURCE=modelscope
set VS_MODEL_SOURCE=hf-mirror
set VS_MODEL_SOURCE=huggingface
```

下载支持断点续传（`.part` 文件），完成后会校验文件大小和 SHA-256。

## 运行

双击 `启动-声刻.cmd`。首次运行会先下载约 5.1 GB 模型权重，再自动 `uv sync` 下载 CUDA 版 torch 等约 4 GB 依赖；总耗时取决于网速，可能需要 20 分钟以上。脚本在引擎/应用就绪后会自动打开 http://127.0.0.1:8091（也可以手动访问）。

仓库中的 `.cmd`/`.bat` 文件统一为 **ASCII 内容 + CRLF 换行**，不依赖 Windows 的系统区域或控制台代码页，也能兼容常见的 ASCII 兼容编码。修改启动脚本时不要加入中文或其他非 ASCII 字符；中文文档和 Python 源码使用 UTF-8。Git 会按 `.gitattributes` 处理批处理文件的换行。

模型默认从仓库内 `engine/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B` 读取；如果权重放在别处，启动前设置环境变量 `COSYVOICE_MODEL_DIR` 指向该目录（启动器、引擎启动脚本、应用都会读取），启动器会自动跳过下载。设置 `VS_NO_MODEL_DOWNLOAD=1` 可以关闭首次启动的自动下载。

想再快一点可设置 `COSYVOICE_FP16=1` 后启动引擎（fp16 推理，仅 CUDA 生效，显存占用更低；个别显卡音质可能有轻微波动，默认关闭）。

## 使用方法

打开 http://127.0.0.1:8091 后，左侧是「合成 / 情绪识别 / 素材体检 / 环境检测」四个页面加音色库，右上角芯片显示整体健康度（绿=全部正常；黄/红=有 FAIL 或 WARN，点一下跳到环境检测）。

### 合成语音

1. 在「音色」下拉里选参考音色，或在左侧列表点选（两处同步）。
2. 输入文本，建议 1–3 句；上限默认 500 字（可用 `VS_MAX_TEXT_CHARS` 调整，页面字数提示会跟着变）。
3. 点情绪芯片：撒娇 / 开心 / 难过 / 生气 / 平静 / 惊讶。
4. 模式一般保持「自动」；「指令」情绪更明显但音色相似度可能略降，「零样本」只复刻音色、不吃情绪参数。
5. 质量选「均衡」；选「最佳」后可设候选数量 2–4，打开「情绪校验」会综合情绪一致度、响度、相似度排序。
6. 点「生成语音」或按 Ctrl+Enter。结果卡可试听、下载 wav，并显示相似度、时长、延迟和实际识别到的情绪。

### 新建音色

左侧「新建音色」→ 上传 0.5–30 秒干净人声（wav / mp3 / flac / ogg，≤ 20 MB）→ 填名称（≤ 32 字）、情绪、分组、参考文本 → 保存。参考音频会自动去静音并归一化；太短、太长或太吵会给出提示。保存后立即出现在左侧音色库。

### 情绪识别

「情绪识别」页上传一段音频，返回模型判定的主要情绪和各情绪分数。合成页打开「情绪校验」时，后端对你的参考音频做的就是同一件事。

### 素材体检

「素材体检」页填写音色库目录（默认 `app\voices`），生成 markdown 报告到 `logs\audit-report.md`，列出每个音色的时长、响度、可读性等问题。

### 环境检测

12 项检查与命令行走同一套逻辑，失败项会给处理建议；右上角能力开关决定哪些按钮可用。详见下面的「环境检测」。

## 常见故障排除

先看日志：`logs\app.log`（Studio）、`logs\engine.log`（CosyVoice 引擎）、`logs\emotion.log`（情绪服务）、`logs\launcher.log`（启动器）。`诊断.cmd` 收集环境信息，`收集日志.cmd` 打包日志。

| 症状 | 可能原因 | 处理 |
|---|---|---|
| 双击启动器窗口一闪而过 | 没装 uv、不在仓库根目录、或路径含特殊字符 | 在仓库根目录打开 cmd，运行 `启动-声刻.cmd` 看报错；`winget install astral-sh.uv` |
| 浏览器打不开 8091 | 应用还没起完，或端口被占 | 看 `logs\app.log` 是否 `Studio app is listening`；`netstat -ano \| findstr :8091` 找占用进程 |
| 健康芯片红，`engines.cosyvoice=false` | 引擎没起 / 加载中 / 崩溃 | 看 `logs\engine.log`；等模型加载（首次 20 秒以上）；确认 50000 端口 |
| 合成返回 503「引擎未就绪」 | 引擎还在加载模型 | 等 `/health` 里 `sample_rate` 出现后重试 |
| 合成失败、日志里 CUDA out of memory | 显存不足或候选数太大 | 降低候选数量、关掉其他占显存的程序；可设 `COSYVOICE_FP16=1` 后重启引擎 |
| 生成很慢（几十秒一条） | torch 没跑在 CUDA 上 | `python -m voicesculptor.envcheck` 看 `torch_cuda` 是否 OK；更新驱动到 ≥ 570 |
| 上传参考音频报「无法识别的音频文件」 | 格式不支持（m4a/aac 等）或文件损坏 | 先转成 wav/mp3/flac/ogg；确认 20 MB 以内 |
| 上传报 422「有效语音过短」 | 参考音频里几乎都是静音或太短 | 换 1–10 秒、人声清晰、尽量无背景音乐的片段 |
| `broken_voices` FAIL | 音色目录缺 `ref.wav` 或 `meta.json` | `python -m voicesculptor.envcheck --fix`，损坏目录会被移到 `voices\.broken\` |
| 情绪识别一直 WARN | 50001 没起，或首次在下载模型（约 1 GB） | 看 `logs\emotion.log`；耐心等首次下载；需要 GPU 可设 `EMOTION_DEVICE=cuda:0` |
| 合成能用但「实际情绪」为空 | 情绪服务不可用，属预期降级 | 启动 `启动-声刻.cmd` 时不要设 `VS_NO_EMOTION=1`；best 择优会自动跳过情绪项 |
| `uv sync` 失败或卡住 | 网络、代理、或缓存损坏 | 设 `NO_PROXY=127.0.0.1,localhost`；必要时 `uv cache clean` 后重试；国内可配 uv 镜像 |
| 模型下载报 403 / 卡在 `.part` | 下载源被限流或中断 | 换源 `set VS_MODEL_SOURCE=huggingface`（或 `hf-mirror`）；删掉对应 `.part` 重试 |
| 启动报 `pyworld` 构建失败 | 用了 Python 3.12+ | 必须 Python 3.11：`uv python install 3.11`，删掉 `.venv` 让它重建 |
| 跑测试报 `No module named pytest` | 启动器的 `uv sync` 把 test 组依赖清掉了 | `cd app && uv sync --group test`（emotion 目录同样处理） |
| 日志里中文乱码 | 用记事本按 ANSI 打开了 UTF-8 日志 | 用 VS Code / Notepad++ 以 UTF-8 打开；`.cmd` 保持 ASCII+CRLF，不要塞中文 |

还查不出来时，运行 `诊断.cmd` 和 `python -m voicesculptor.envcheck --json`，把输出连同 `logs\` 一起带上再问。

## 开发

两个应用各自是一个 uv 项目，测试依赖放在 `test` 组里：

```bat
cd app
uv sync --group test

cd ..\emotion
uv sync --group test
```

日常命令：

```bat
cd app
.venv\Scripts\python -m pytest -q          REM 单元 + 接口测试
.venv\Scripts\python -m voicesculptor.envcheck   REM 命令行自检
.venv\Scripts\python app.py --port 8091    REM 只起 Studio（引擎需另开）
```

代码风格按 Google Python Style：4 空格缩进、80 列、类型注解、文档字符串；格式化和 import 排序由 yapf / isort 负责（配置在各自的 `pyproject.toml` 里，风格均为 Google）。前端是原生 ES Module：只用 `const`/`let`、命名导出，DOM 写入一律 `textContent`，不写内联样式和 `onclick`。

## 测试

```bat
cd app
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pylint --rcfile ..\pylintrc voicesculptor
.venv\Scripts\python -m yapf --diff -r voicesculptor tests
.venv\Scripts\python -m isort --check-only --diff voicesculptor tests

cd ..\emotion
.venv\Scripts\python -m pytest -q
```

接口测试会自己在随机端口起假引擎和假情绪服务，不需要 GPU，也不需要下载模型。

## 环境检测

环境检测覆盖 12 项，命令行走一遍最直观：

```bat
cd app
.venv\Scripts\python -m voicesculptor.envcheck
.venv\Scripts\python -m voicesculptor.envcheck --json
.venv\Scripts\python -m voicesculptor.envcheck --fix
```

`--fix` 先报告、再就地修、最后复检，输出「修复前 / 修复动作 / 修复后」三段：

| 能自动修 | 做法 |
|---|---|
| `voice_dir` | 创建音色目录并确认可写 |
| `broken_voices` | 把损坏目录移到 `voices/.broken/<id>-<时间戳>`，不删除 |
| `packages` / `torch_cuda` / `audio_formats` | 在 app 目录执行 `uv sync --inexact`（需要 uv 在 PATH） |
| `python` | `uv python install 3.11` |
| `model_files` | 默认只提示；加 `--download-models` 才下载约 5.1 GB 权重 |

`disk_space`、`seed_refs`、`proxy` 只给建议：磁盘要自己清，种子文件属于仓库内容，代理变量要改在启动环境里。`cosyvoice` / `emotion_service` 由 `启动-声刻.cmd` 拉起。

纯净机器上的顺序：装 uv（`winget install astral-sh.uv`）→ `cd app && uv sync` → `.venv\Scripts\python -m voicesculptor.envcheck --fix` → 双击 `启动-声刻.cmd` 补模型并起服务。检测命令行只用标准库，依赖没装齐也能跑出报告。

每行输出 `[OK  ] id  message`，有 `FAIL` 时退出码为 1。Studio 里对应「环境检测」页，页面上也能点一次重新检测；接口是 `GET /api/env?refresh=1`，它总是返回 200，检测结果不会阻止服务启动，只用来告诉你哪些能力暂时不可用。

| # | 检测项 | 检查内容 | FAIL 时的影响 |
|---|---|---|---|
| 1 | `python` | Python 版本 ≥ 3.11 | 无法启动 |
| 2 | `packages` | fastapi / numpy / onnxruntime / soundfile / torch / torchaudio / requests | 缺少依赖，功能不可用 |
| 3 | `torch_cuda` | torch 是否可用 CUDA、显存大小 | 退回 CPU，合成很慢 |
| 4 | `model_files` | 6 个模型权重是否齐全且非空 | 无法合成、无法算相似度 |
| 5 | `cosyvoice` | 引擎 `/health`（50000 端口） | 无法合成 |
| 6 | `emotion_service` | 情绪服务 `/health`（50001 端口） | 不做情绪校验与情绪择优 |
| 7 | `audio_formats` | wav / mp3 / flac / ogg 解码能力 | 只能上传 wav |
| 8 | `voice_dir` | 音色库目录可写 | 不能新建、删除音色 |
| 9 | `broken_voices` | 损坏的音色目录（缺 ref.wav 或 meta.json） | 对应音色不可用 |
| 10 | `seed_refs` | 6 个内置种子参考音频存在 | 首次启动补不齐默认音色 |
| 11 | `disk_space` | 剩余磁盘空间（< 2 GB 警告，< 200 MB 失败） | 写不下新音色 |
| 12 | `proxy` | 代理环境变量是否会拦截 127.0.0.1 | 应用连不上本机引擎 |

检测结果同时推导出四项能力开关（`synthesize`、`similarity`、`emotion`、`clone`），前端据此置灰按钮。结果缓存 10 秒，`refresh=1` 可强制重跑。

## 情绪模式

- **auto**：有情绪指令时自动用 instruct2（情绪优先）；参考音色本身即目标情绪时用 zero_shot。
- **zero_shot**：只复刻参考音频的音色与语气，emotion 参数不生效。
- **instruct2**：按情绪指令合成，情绪更明显，但音色相似度可能略降。

best 模式（`best_n` > 1）默认把情绪识别结果计入择优打分：情绪与目标一致的候选会加分，情绪服务不可用时该项自动跳过。想恢复旧行为可设置 `VS_EMOTION_RANK=0`。

## 情绪识别服务（可选，端口 50001）

`emotion/` 是独立的情绪识别服务（emotion2vec_plus_large，FunASR，默认 CPU 推理），`启动-声刻.cmd` 会自动拉起它，日志写在 `logs\emotion.log`。首次启动要下载模型到 ModelScope 缓存（约 1GB 以上）。服务没起来时 Studio 照常合成，只是不显示"实际情绪"，best 模式也不做情绪择优。

- 用 GPU：启动前设置 `EMOTION_DEVICE=cuda:0`
- 不启动它：设置 `VS_NO_EMOTION=1`
- 能识别：生气 / 开心 / 平静 / 难过 / 惊讶（"撒娇"没有对应类别）
