# -*- coding: utf-8 -*-
"""绿色版自检：输出 Python / Torch / CUDA / 关键包状态（由 诊断.cmd 调用）"""
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

print("Python:", sys.version.replace("\n", " "))

try:
    import torch
    print("Torch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
        total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print("VRAM: %.1f GB" % total)
except Exception as e:
    print("Torch 导入失败:", type(e).__name__, e)

for name in ("fastapi", "uvicorn", "onnxruntime", "soundfile", "numpy",
             "torchaudio", "requests", "torchaudio.compliance.kaldi"):
    try:
        __import__(name)
        print("包 OK:", name)
    except Exception as e:
        print("包缺失:", name, "->", type(e).__name__, e)
