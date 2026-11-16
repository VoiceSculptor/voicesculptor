# -*- coding: utf-8 -*-
"""声刻 情绪识别服务（默认端口 50001）

  模型: emotion2vec_plus_large（FunASR AutoModel，ModelScope 下载，首次约 1GB 以上）
  接口:
    GET  /health   -> {"ok":true,"model":...,"device":...,"loaded":true}
    POST /emotion  form 字段 file=<音频> -> {"label":英文类别,"cn":中文标签或null,
                                             "scores":{英文:分数},"cn_scores":{中文:分数}}
  被 app/app.py 的 detect_emotion() 调用；cn 永不为 null；仅 angry/happy/neutral/sad/surprised
  与 app 的 EMOTION_INSTRUCT 键一致，其余类别只用于展示。
  环境变量: EMOTION_MODEL（默认 iic/emotion2vec_plus_large）、EMOTION_DEVICE（默认 cpu）
"""
import argparse
import io
import logging
import os
import tempfile
import threading

import numpy as np
import soundfile as sf
import torch
import torchaudio
from fastapi import FastAPI, File, HTTPException, UploadFile

MODEL_ID = os.environ.get('EMOTION_MODEL', 'iic/emotion2vec_plus_large')
DEVICE = os.environ.get('EMOTION_DEVICE', 'cpu')
# emotion2vec_plus 9 类；只有前 5 类与 app 的 EMOTION_INSTRUCT 键对应，其余只用于展示
EN2CN = {'angry': '生气', 'happy': '开心', 'neutral': '平静', 'sad': '难过', 'surprised': '惊讶',
         'disgusted': '厌恶', 'fearful': '恐惧', 'other': '其他', 'unknown': '未知'}
SILENCE_RMS = 10 ** (-50 / 20)  # 约 -50 dBFS，低于此值视为静音，不送模型


def _norm_label(lab):
    """'生气/angry' -> 'angry'；'<unk>' -> 'unknown'；统一小写"""
    s = str(lab).split('/')[-1].strip().lower()
    return 'unknown' if s in ('<unk>', 'unk', '') else s


def _cn(label):
    """已知类别返回中文；未知类别原样返回英文，永不返回 None"""
    return EN2CN.get(label, label)

app = FastAPI(title='voicesculptor-emotion', version='0.1.0')
LOG = logging.getLogger('emotion')
_model = None
_lock = threading.Lock()


def model():
    global _model
    if _model is None:
        from funasr import AutoModel
        _model = AutoModel(model=MODEL_ID, hub='ms', device=DEVICE, disable_update=True)
    return _model


# ------------------------------------------------------------
# 单声道 + 重采样到 16k，写临时 wav 交给 FunASR（路径输入是 FunASR 最稳的输入形式）
# 返回 (top 英文类别, {英文类别: 分数})
# ------------------------------------------------------------
def classify(wav, sr):
    wav = np.asarray(wav, dtype=np.float32)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != 16000:
        wav = torchaudio.functional.resample(torch.from_numpy(np.ascontiguousarray(wav)), sr, 16000).numpy()
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.close()
    try:
        sf.write(tmp.name, wav, 16000)
        with _lock:
            res = model().generate(tmp.name, granularity='utterance', extract_embedding=False)[0]
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass
    scores = {}
    for lab, s in zip(res['labels'], res['scores']):
        scores[_norm_label(lab)] = round(float(s), 4)
    top = max(scores, key=scores.get)
    return top, scores


@app.get('/health')
def health():
    return {'ok': True, 'model': MODEL_ID, 'device': DEVICE, 'loaded': _model is not None}


@app.post('/emotion')
def emotion(file: UploadFile = File(...)):
    data = file.file.read()
    if not data:
        raise HTTPException(422, '音频为空')
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, '音频过大（上限 20MB）')
    try:
        wav, sr = sf.read(io.BytesIO(data), dtype='float32')
    except Exception:
        raise HTTPException(422, '无法识别的音频文件')
    if len(wav) < 0.3 * sr:
        raise HTTPException(422, '音频短于 0.3 秒')
    mono = wav.mean(axis=1) if wav.ndim > 1 else wav
    if float(np.sqrt(np.mean(np.square(mono)))) < SILENCE_RMS:
        return {'label': 'unknown', 'cn': _cn('unknown'), 'scores': {}, 'cn_scores': {}, 'reason': 'silence'}
    top, scores = classify(wav, sr)
    return {'label': top, 'cn': _cn(top), 'scores': scores,
            'cn_scores': {_cn(k): v for k, v in scores.items()}}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=50001)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    model()  # 先加载（首次会下载），加载完才监听端口：端口可连 = 服务就绪
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port)
