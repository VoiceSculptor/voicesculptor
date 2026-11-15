# -*- coding: utf-8 -*-
"""声刻 Studio —— 本地语音克隆应用（FastAPI + 单页界面）

【这个文件做什么】
  1. 提供一个 HTTP 服务（默认 8091），同时托管前端页面和 JSON 接口；
  2. 前端页面（static/index.html）通过 /api/* 调用这里的接口；
  3. 真正"说话"的是另一个进程（CosyVoice 引擎，默认 50000），本文件只负责转发与评测。

【启动顺序】
  1. 先由 _run-engine.cmd 启动 CosyVoice（模型加载约 20~60 秒）；
  2. 再由 _run-app.cmd 启动本文件；
  3. 启动脚本确认两个端口都可连后，才打开浏览器。

【目录约定】（由启动脚本保证相对路径正确）
  <绿色版根目录>/
    app/app.py                <- 本文件
    app/static/index.html     <- 前端
    app/voices/<id>/          <- 运行时生成：每个音色的 meta.json + ref.wav
    app/.venv/                <- uv 管理的依赖环境（首次 uv sync 生成）
    runtime/roxy-emotions-orig/    <- 6 段情绪参考音频（内置音色）
    runtime/roxy-refs-selected/    <- 精选后的参考（难过/平静）
    engine/CosyVoice/         <- 合成引擎 + 模型

【接口一览】
  GET  /                   前端页面
  GET  /api/health         引擎与参考音色状态（前端顶栏用）
  GET  /api/voices         音色列表
  POST /api/voices         新建音色（上传参考音频 + 转录文本）
  DELETE /api/voices/{id}  删除音色
  POST /api/tts            合成语音（核心接口，见函数注释）
  POST /api/audit          素材体检（统计时长/信噪比/可用性）

【常见故障对应】
  · 前端显示 "Failed to fetch" -> 本服务没起来，或浏览器用 file:// 打开
  · /api/tts 返回 503         -> CosyVoice 引擎不可用（看 logs/engine.log）
  · 合成很慢                  -> 引擎退到了 CPU（CUDA 不可用，检查驱动）
"""

import argparse
import base64
import io
import json
import logging
import os
import re
import shutil
import struct
import time
import uuid

import numpy as np
import onnxruntime
import requests
import soundfile as sf
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

APP_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(APP_DIR, 'voices')
STATIC_DIR = os.path.join(APP_DIR, 'static')
QA = os.path.dirname(APP_DIR)
ROXY_SEL = os.path.join(QA, 'runtime', 'roxy-refs-selected')
ROXY_ORIG = os.path.join(QA, 'runtime', 'roxy-emotions-orig')
MODEL_DIR = os.environ.get('COSYVOICE_MODEL_DIR') or os.path.join(
    QA, 'engine', 'CosyVoice', 'pretrained_models', 'Fun-CosyVoice3-0.5B')
COSYVOICE = os.environ.get('COSYVOICE_BASE', 'http://127.0.0.1:50000')
EMO_SVC = os.environ.get('EMOTION_BASE', 'http://127.0.0.1:50001')

os.makedirs(VOICE_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title='声刻 Studio', version='1.1.0')
LOG = logging.getLogger('voicesculptor')
_sess = None
HTTP = requests.Session()


# ------------------------------------------------------------
# 懒加载 CAM++ 说话人嵌入模型（ONNX，CPU 推理），首次调用时初始化
# ------------------------------------------------------------
def campplus():
    global _sess
    if _sess is None:
        onnx_path = os.path.join(MODEL_DIR, 'campplus.onnx')
        if not os.path.isfile(onnx_path):
            raise HTTPException(503, '找不到评测模型: ' + onnx_path + '（请设置 COSYVOICE_MODEL_DIR）')
        opt = onnxruntime.SessionOptions()
        opt.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        _sess = onnxruntime.InferenceSession(onnx_path,
                                             sess_options=opt, providers=['CPUExecutionProvider'])
    return _sess


# ------------------------------------------------------------
# 把一段音频转成说话人向量（16k 重采样 + fbank + ONNX 推理）
# ------------------------------------------------------------
def embed_array(wav, sr):
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    t = torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32)).unsqueeze(0)
    if sr != 16000:
        t = torchaudio.functional.resample(t, sr, 16000)
    f = kaldi.fbank(t, num_mel_bins=80, sample_frequency=16000, dither=0)
    f = f - f.mean(dim=0, keepdim=True)
    s = campplus()
    return s.run(None, {s.get_inputs()[0].name: f.unsqueeze(0).numpy()})[0].flatten()


def embed(path):
    wav, sr = sf.read(path, dtype='float32')
    return embed_array(wav, sr)


# ------------------------------------------------------------
# 两个说话人向量的余弦相似度，范围 -1~1，越接近 1 越像同一个人
# ------------------------------------------------------------
def sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ------------------------------------------------------------
# 把 CosyVoice 返回的裸 PCM（16bit 单声道 24k）包装成标准 WAV 头
# ------------------------------------------------------------
def wrap_wav(pcm_bytes, sr=24000):
    return (b'RIFF' + struct.pack('<I', 36 + len(pcm_bytes)) + b'WAVEfmt '
            + struct.pack('<IHHIIHH', 16, 1, 1, sr, sr * 2, 2, 16)
            + b'data' + struct.pack('<I', len(pcm_bytes)) + pcm_bytes)


# ------------------------------------------------------------
# 扫描 voices 目录，读出所有音色的元数据
# ------------------------------------------------------------
def _load_meta(d, vid):
    """读取并校验一个音色的 meta.json；损坏或不属于该音色时返回 None"""
    mp = os.path.join(d, 'meta.json')
    if not os.path.isfile(mp):
        return None
    try:
        with open(mp, encoding='utf-8') as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get('voice_id') != vid:
        return None
    return meta


def list_voices():
    out = []
    for vid in sorted(os.listdir(VOICE_DIR)):
        meta = _load_meta(os.path.join(VOICE_DIR, vid), vid)
        if meta is not None:
            out.append(meta)
    return out


# ------------------------------------------------------------
# 把 voice_id 解析成 voices 下的目录；含分隔符或 .. 的 id 一律视为不存在
# ------------------------------------------------------------
def _voice_dir(vid):
    if not vid or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', vid):
        raise HTTPException(404, 'voice not found')
    d = os.path.join(VOICE_DIR, vid)
    if os.path.dirname(os.path.normpath(d)) != os.path.normpath(VOICE_DIR):
        raise HTTPException(404, 'voice not found')
    return d


# ------------------------------------------------------------
# 根据 voice_id 取出元数据与参考音频路径，不存在则 404
# ------------------------------------------------------------
def voice_paths(vid):
    d = _voice_dir(vid)
    meta = _load_meta(d, vid)
    if meta is None:
        raise HTTPException(404, 'voice not found: ' + vid)
    ref = os.path.join(d, 'ref.wav')
    if not os.path.isfile(ref):
        raise HTTPException(404, '参考音频丢失: ' + vid)
    return meta, ref


# ------------------------------------------------------------
# 首次启动时把内置的 6 个情绪参考音频复制成默认音色
# ------------------------------------------------------------
def seed_defaults():
    defaults = [
        ('coquettish', '撒娇', os.path.join(ROXY_ORIG, 'coquettish.wav'),
         'ルディ、ちょっと背中を貸してもらっていいですか'),
        ('happy', '开心', os.path.join(ROXY_ORIG, 'happy.wav'),
         'はいそうですねルディ身長大きくなりましたね'),
        ('sad', '难过', os.path.join(ROXY_SEL, 'sad_v2.wav'),
         'なるほど、これは鍛えがいがありそうですね'),
        ('angry', '生气', os.path.join(ROXY_ORIG, 'angry.wav'),
         'もし妊娠でもしてしまったらどうする気なのですかまったく'),
        ('calm', '平静', os.path.join(ROXY_SEL, 'calm_v2.wav'),
         'ルディなら自力で立ち直るって言ってましたけど'),
        ('surprise', '惊讶', os.path.join(ROXY_ORIG, 'surprise.wav'),
         'えっと、ルーデオスさん、その、ありがとうございました'),
    ]
    for vid, name, ref, prompt in defaults:
        d = os.path.join(VOICE_DIR, vid)
        if os.path.exists(os.path.join(d, 'meta.json')) or not os.path.exists(ref):
            continue
        os.makedirs(d, exist_ok=True)
        with open(ref, 'rb') as src, open(os.path.join(d, 'ref.wav'), 'wb') as dst:
            dst.write(src.read())
        meta = dict(voice_id=vid, name=name, prompt=prompt, emoji='★',
                    created=time.strftime('%Y-%m-%d %H:%M:%S'), source='seed')
        with open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


EMOTION_INSTRUCT = {
    '撒娇': 'You are a helpful assistant. 请用非常可爱、撒娇的语气说一句话。',
    '开心': 'You are a helpful assistant. 请非常开心地说一句话。',
    '难过': 'You are a helpful assistant. 请非常伤心地说一句话。',
    '生气': 'You are a helpful assistant. 请非常生气地说一句话。',
    '平静': 'You are a helpful assistant. 请用平静、温柔的语气说一句话。',
    '惊讶': 'You are a helpful assistant. 请用非常惊讶、意外的语气说一句话。',
}


# ------------------------------------------------------------
# 引擎侧 zero_shot 说话人缓存：首次注册，之后直接按 spk_id 合成，
# 省掉每次请求重复提取 speech token / fbank / 说话人向量的开销
# ------------------------------------------------------------
_REGISTERED = set()


def _spk_id(ref_path):
    vid = os.path.basename(os.path.dirname(ref_path))
    return '%s_%d' % (vid, int(os.path.getmtime(ref_path)))


def _register_spk(spk, ref_path, prompt):
    with open(ref_path, 'rb') as f:
        files = {'prompt_wav': ('p.wav', f.read(), 'application/octet-stream')}
    data = {'spk_id': spk,
            'prompt_text': 'You are a helpful assistant.<|endofprompt|>' + prompt}
    r = HTTP.post(COSYVOICE + '/add_zero_shot_spk', data=data, files=files, timeout=120)
    r.raise_for_status()
    _REGISTERED.add(spk)


# ------------------------------------------------------------
# 调用一次 CosyVoice：instruct 非空走 instruct2，否则走 zero_shot（带说话人缓存）
# ------------------------------------------------------------
def synth_once(ref_path, prompt, text, instruct, speed=1.0):
    if instruct:
        with open(ref_path, 'rb') as f:
            files = {'prompt_wav': ('p.wav', f.read(), 'application/octet-stream')}
        data = {'tts_text': text, 'instruct_text': instruct + '<|endofprompt|>',
                'speed': str(speed)}
        r = HTTP.post(COSYVOICE + '/inference_instruct2', data=data, files=files, timeout=300)
        r.raise_for_status()
        return r.content
    spk = _spk_id(ref_path)
    if spk not in _REGISTERED:
        _register_spk(spk, ref_path, prompt)
    data = {'tts_text': text, 'spk_id': spk, 'speed': str(speed)}
    r = HTTP.post(COSYVOICE + '/inference_zero_shot_spk', data=data, timeout=300)
    if r.status_code == 404:  # 引擎重启过，说话人缓存丢了：重注册再试
        _REGISTERED.discard(spk)
        _register_spk(spk, ref_path, prompt)
        r = HTTP.post(COSYVOICE + '/inference_zero_shot_spk', data=data, timeout=300)
    r.raise_for_status()
    return r.content


# ------------------------------------------------------------
# 对内存中的 PCM 直接算说话人向量（不落盘）
# ------------------------------------------------------------
def _emb_bytes(pcm_bytes):
    return embed_array(np.frombuffer(pcm_bytes, dtype='<i2').astype(np.float32) / 32768.0, 24000)


# ------------------------------------------------------------
# 参考音频的 embedding 缓存：best 模式一次请求最多合成 7 条，参考向量只该算一次
# ------------------------------------------------------------
_REF_EMB = {}


def ref_embedding(path):
    key = (path, os.path.getmtime(path))
    v = _REF_EMB.get(key)
    if v is None:
        v = embed(path)
        if len(_REF_EMB) > 64:
            _REF_EMB.clear()
        _REF_EMB[key] = v
    return v


# --------------------------------------------------------------------
# 接口: @app.get('/')
# 作用: 首页：直接返回 static/index.html
# --------------------------------------------------------------------
@app.get('/')
def index():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))


# ------------------------------------------------------------
# 接口: GET /api/health
# 作用: 健康检查：探测 CosyVoice(50000) 与本地评测模型是否就绪
# ------------------------------------------------------------
@app.get('/api/health')
def health():
    engines = {}
    try:
        engines['cosyvoice'] = HTTP.get(COSYVOICE + '/health', timeout=2).ok
    except Exception:
        engines['cosyvoice'] = False
    # 评测模型是本应用的硬依赖，单独上报，前端可直接看出模型目录是否正确
    engines['model'] = os.path.isfile(os.path.join(MODEL_DIR, 'campplus.onnx'))
    return {'ok': all(engines.values()), 'engines': engines, 'voices': len(list_voices())}


# --------------------------------------------------------------------
# 接口: @app.get('/api/voices')
# 作用: 接口：返回全部音色
# --------------------------------------------------------------------
@app.get('/api/voices')
def get_voices():
    return {'voices': list_voices()}


@app.post('/api/voices')
async def create_voice(name: str = Form(...), prompt: str = Form(''),
                       emoji: str = Form(''), ref: UploadFile = File(...)):
    data = await ref.read()
    if not data:
        raise HTTPException(422, '参考音频为空')
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, '参考音频过大（上限 20MB）')
    # 统一转成 WAV 保存，避免把 mp3/m4a 原样写成 .wav 后引擎读不了
    try:
        wav, sr = sf.read(io.BytesIO(data), dtype='float32')
    except Exception:
        raise HTTPException(422, '无法识别的音频文件，请上传 wav/mp3/m4a/flac/ogg')
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    dur = len(wav) / float(sr or 1)
    if not 0.5 <= dur <= 30:
        raise HTTPException(422, '参考音频时长需在 0.5~30 秒（当前 %.1f 秒）' % dur)
    vid = 'v_' + uuid.uuid4().hex[:8]
    d = os.path.join(VOICE_DIR, vid)
    try:
        os.makedirs(d, exist_ok=True)
        sf.write(os.path.join(d, 'ref.wav'), wav, sr)
        meta = dict(voice_id=vid, name=name, prompt=prompt, emoji=emoji or '★',
                    created=time.strftime('%Y-%m-%d %H:%M:%S'), source='upload')
        with open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return meta


# --------------------------------------------------------------------
# 接口: @app.delete('/api/voices/{vid}')
# 作用: 接口：删除音色（连同参考音频）
# --------------------------------------------------------------------
@app.delete('/api/voices/{vid}')
def delete_voice(vid: str):
    d = _voice_dir(vid)
    if not os.path.isdir(d):
        raise HTTPException(404, 'voice not found')
    shutil.rmtree(d, ignore_errors=True)
    if os.path.isdir(d):
        raise HTTPException(500, '删除失败：目录仍被占用，请关闭占用的程序后重试')
    for k in [k for k in _REF_EMB if k[0].startswith(d + os.sep)]:
        _REF_EMB.pop(k, None)
    return {'ok': True}


# --------------------------------------------------------------------
# 接口: @app.post('/api/tts')
# 作用: 接口：合成语音。流程见函数体内的分步注释
# --------------------------------------------------------------------
@app.post('/api/tts')
def tts(voice_id: str = Form(...), text: str = Form(...), emotion: str = Form('平静'),
        mode: str = Form('auto'), speed: float = Form(1.0), quality: str = Form('balanced'),
        best_n: int = Form(2), verify: bool = Form(True)):
    # 1) 定位音色：拿到参考音频与转录文本
    meta, ref = voice_paths(voice_id)
    if not text.strip():
        raise HTTPException(422, '文本为空')
    # 评测模型缺失时尽早失败，避免先等一次完整合成
    campplus()
    # 参数白名单：非法值早点 422，别等合成完才发现
    if mode not in ('auto', 'zero_shot', 'instruct2'):
        raise HTTPException(422, 'mode 只能是 auto/zero_shot/instruct2')
    if quality not in ('balanced', 'best'):
        raise HTTPException(422, 'quality 只能是 balanced/best')
    # 语速只接受 0.5~2.0，防止引擎收到离谱的值
    speed = max(0.5, min(2.0, float(speed)))

    def _synth(instr):
        return synth_once(ref, meta.get('prompt', ''), text, instr, speed)

    # 2) 决定用哪种模式：撒娇/生气默认走 instruct2（情绪更准），其余 zero_shot（音色更好）
    instruct = EMOTION_INSTRUCT.get(emotion) if mode == 'instruct2' else None
    if mode == 'auto' and emotion in ('撒娇', '生气'):
        instruct = EMOTION_INSTRUCT.get(emotion)

    # 3) 第一次合成（失败直接 503，让前端提示引擎不可用）
    t0 = time.time()
    try:
        pcm = _synth(instruct)
    except Exception as e:
        LOG.exception('首次合成失败')
        raise HTTPException(503, '合成失败: ' + str(e))

    # 4) 时长健全性检查（CosyVoice 偶发“早停”或“生成过长”，必须兜底）
    #    · 期望时长 ≈ 字数 / 5.8（按经验语速换算）
    #    · 短于期望 55% -> 重试（最多 2 次，取更长的一条）
    #    · 长于期望 250% -> 重试一次（取更接近期望的一条）
    #    · 仍然过短且当前是 zero_shot -> 切 instruct2 再试一次（实测更稳）
    def _dur(b):
        return len(b) / 2.0 / 24000.0

    expected = max(0.8, len(text.strip()) / 5.8)
    tries = 0
    while (_dur(pcm) < expected * 0.55 or _dur(pcm) > expected * 2.5) and tries < 2:
        tries += 1
        try:
            alt = _synth(instruct)
            d_old, d_new = _dur(pcm), _dur(alt)
            # 谁更接近期望区间就选谁
            def _badness(d):
                if d < expected * 0.55:
                    return expected * 0.55 - d
                if d > expected * 2.5:
                    return d - expected * 2.5
                return 0.0
            if _badness(d_new) < _badness(d_old):
                pcm = alt
        except Exception as e:
            LOG.warning('时长重试失败: %s', e)

    fallback = EMOTION_INSTRUCT.get(emotion)
    if _dur(pcm) < expected * 0.55 and instruct is None and fallback:
        try:
            alt = _synth(fallback)
            if _dur(alt) > _dur(pcm):
                pcm = alt
                instruct = fallback
        except Exception as e:
            LOG.warning('情绪回退合成失败: %s', e)

    # 5) 质量模式：best 会额外生成 n-1 条，按相似度择优；balanced 只做一次
    n = max(1, min(4, int(best_n))) if quality == 'best' else 1
    try:
        ref_emb = ref_embedding(ref)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, '评测模型加载失败: ' + str(e))
    best_pcm = pcm
    try:
        best_s = sim(_emb_bytes(pcm), ref_emb)
    except Exception as e:
        LOG.warning('相似度计算失败: %s', e)
        best_s = None
    for _ in range(n - 1):
        try:
            alt = _synth(instruct)
            s = sim(_emb_bytes(alt), ref_emb)
            if best_s is None or s > best_s:
                best_pcm, best_s = alt, s
        except Exception as e:
            LOG.warning('候选择优失败: %s', e)

    # 6) 包装成 WAV，并计算时长
    wav = wrap_wav(best_pcm, 24000)
    duration = len(best_pcm) / 2 / 24000
    # 7) 可选：让情绪服务判断实际情绪（用于对比目标情绪）
    detected = None
    if verify:
        try:
            r = HTTP.post(EMO_SVC + '/emotion',
                          files={'file': ('a.wav', wav, 'audio/wav')}, timeout=60)
            if r.ok:
                detected = r.json().get('cn')
        except Exception as e:
            LOG.info('情绪服务不可用: %s', e)

    return JSONResponse({
        'audio_base64': base64.b64encode(wav).decode('ascii'),
        'sim': round(best_s, 3) if best_s is not None else None,
        'duration': round(duration, 2),
        'latency': round(time.time() - t0, 2),
        'engine': 'cosyvoice',
        'mode': 'instruct2' if instruct else 'zero_shot',
        'emotion_target': emotion,
        'emotion_detected': detected,
        'candidates': n,
    })


# ------------------------------------------------------------
# 素材体检：逐个音频统计时长、采样率、声道、信噪比与可用性结论
# ------------------------------------------------------------
def audit_folder(dir_path):
    """轻量素材体检：时长 / 采样率 / 声道 / SNR / 总量 + 结论"""
    rows = []
    try:
        names = sorted(os.listdir(dir_path))
    except OSError as e:
        raise HTTPException(500, '无法读取目录: ' + str(e))
    for fn in names:
        if not fn.lower().endswith(('.wav', '.mp3', '.m4a', '.flac', '.ogg')):
            continue
        p = os.path.join(dir_path, fn)
        try:
            info = sf.info(p)
            dur = info.frames / float(info.samplerate)
            sr, ch = info.samplerate, info.channels
        except Exception:
            continue
        snr = 0.0
        try:
            w, _ = sf.read(p, dtype='float32')
            if w.ndim > 1:
                w = w.mean(axis=1)
            frame = max(1, int(sr * 0.02))
            n = len(w) // frame
            if n >= 10:
                rms = np.array([float(np.sqrt(np.mean(w[i * frame:(i + 1) * frame] ** 2)) + 1e-9)
                                for i in range(n)])
                noise = max(float(np.percentile(rms, 10)), 1e-6)
                speech = max(float(np.percentile(rms, 90)), noise)
                snr = float(20 * np.log10(speech / noise))
                snr = max(0.0, min(60.0, snr))
        except Exception:
            pass
        rows.append(dict(file=fn, dur=round(dur, 2), sr=sr, ch=ch, snr=round(snr, 1)))

    total = sum(r['dur'] for r in rows)
    usable = sum(r['dur'] for r in rows if 2 <= r['dur'] <= 12)
    snrs = [r['snr'] for r in rows if r['snr'] > 0]
    med_snr = float(np.median(snrs)) if snrs else 0.0
    if usable / 60 >= 30 and med_snr >= 25:
        verdict = '优秀：可直接做全量 SFT'
    elif usable / 60 >= 10 and med_snr >= 15:
        verdict = '良好：可做 LoRA 微调'
    elif usable / 60 >= 3:
        verdict = '及格：可做零样本 + 少量微调'
    else:
        verdict = '不足：建议重录（目标 ≥ 10 分钟有效语音）'

    lines = ['# 素材体检报告', '',
             '| 项目 | 数值 |', '|---|---|',
             '| 文件数 | %d |' % len(rows),
             '| 总时长 | %.1f 分钟 |' % (total / 60),
             '| 有效片段（2~12 秒） | %.1f 分钟 |' % (usable / 60),
             '| 中位信噪比 | %.1f dB |' % med_snr,
             '| 采样率/声道 | %s / %s |' % (
                 '/'.join(sorted({str(r['sr']) for r in rows})) or '-',
                 '/'.join(sorted({str(r['ch']) for r in rows})) or '-'),
             '', '**结论**：' + verdict, '',
             '| 文件 | 时长 | 采样率 | 声道 | SNR |', '|---|---|---|---|---|']
    for r in rows[:60]:
        lines.append('| %s | %.1fs | %d | %d | %.1fdB |' % (r['file'], r['dur'], r['sr'], r['ch'], r['snr']))
    if len(rows) > 60:
        lines.append('| …（其余 %d 个文件省略） | | | | |' % (len(rows) - 60))
    return '\n'.join(lines), dict(files=len(rows), total_min=round(total / 60, 1),
                                  usable_min=round(usable / 60, 1),
                                  median_snr=round(med_snr, 1), verdict=verdict)


# --------------------------------------------------------------------
# 接口: @app.post('/api/audit')
# 作用: 接口：对指定目录做体检，返回 markdown 报告
# --------------------------------------------------------------------
@app.post('/api/audit')
def audit(dir_path: str = Form(...)):
    if not os.path.isdir(dir_path):
        raise HTTPException(422, '目录不存在: ' + dir_path)
    report, summary = audit_folder(dir_path)
    try:
        with open(os.path.join(APP_DIR, 'audit-report.md'), 'w', encoding='utf-8') as f:
            f.write(report)
    except OSError as e:
        raise HTTPException(500, '报告写入失败: ' + str(e))
    return {'ok': True, 'report': report, 'summary': summary}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8091)
    args = ap.parse_args()
    seed_defaults()
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port)
