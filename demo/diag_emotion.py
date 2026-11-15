# -*- coding: utf-8 -*-
"""情感不足诊断：
A. 同一音色、同一句话，分别用 zero_shot / instruct2 合成六种情绪，比较音高与能量差异；
B. 同一情绪(开心)用 instruct2 连续合成 6 次，看说话人相似度 sim 与音高起伏 f0_rng 的相关性。
用法（仓库根目录，引擎 50000 与应用 8091 已启动）：
    uv run --project app python demo/diag_emotion.py <voice_id>
"""
import base64
import io
import os
import sys

import numpy as np
import requests
import soundfile as sf
import torch
import torchaudio

BASE = os.environ.get('STUDIO_BASE', 'http://127.0.0.1:8091')
LINE = '今天发生的事情，我一定要好好跟你讲一讲。'
EMOS = ['撒娇', '开心', '难过', '生气', '平静', '惊讶']


def tts(vid, emo, mode):
    r = requests.post(BASE + '/api/tts', data={
        'voice_id': vid, 'text': LINE, 'emotion': emo, 'mode': mode,
        'speed': '1.0', 'quality': 'balanced', 'verify': 'false'}, timeout=900)
    r.raise_for_status()
    return r.json()


def feats(j):
    wav, sr = sf.read(io.BytesIO(base64.b64decode(j['audio_base64'])), dtype='float32')
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    try:
        import librosa
        f0 = librosa.pyin(wav, fmin=60, fmax=500, sr=sr, frame_length=1024)[0]
        f0 = f0[~np.isnan(f0)]
    except ImportError:
        t = torch.from_numpy(np.ascontiguousarray(wav)).unsqueeze(0)
        f0 = torchaudio.functional.detect_pitch_frequency(t, sr, freq_low=70, freq_high=500).flatten().numpy()
        f0 = f0[(f0 > 70) & (f0 < 500)]
    fr = int(sr * 0.02)
    n = len(wav) // fr
    rms = np.sqrt((wav[:n * fr].reshape(n, fr) ** 2).mean(axis=1))
    rms = rms[rms > 1e-3]
    return dict(
        f0_med=float(np.median(f0)) if len(f0) else float('nan'),
        f0_rng=float(np.percentile(f0, 90) - np.percentile(f0, 10)) if len(f0) else float('nan'),
        rms_db=float(np.median(20 * np.log10(rms))) if len(rms) else float('nan'),
        dur=j['duration'], sim=j['sim'], mode=j['mode'])


def main():
    if len(sys.argv) != 2:
        sys.exit('用法: python demo/diag_emotion.py <voice_id>')
    vid = sys.argv[1]
    print('== A. 六情绪 x 两种模式 ==')
    print('%-10s %-5s %-10s %8s %8s %8s %6s %6s' % ('req_mode', 'emo', 'real_mode', 'f0_med', 'f0_rng', 'rms_db', 'dur', 'sim'))
    for req_mode in ('zero_shot', 'instruct2'):
        rows = []
        for emo in EMOS:
            f = feats(tts(vid, emo, req_mode))
            rows.append(f)
            print('%-10s %-5s %-10s %8.1f %8.1f %8.1f %6.2f %6s' % (
                req_mode, emo, f['mode'], f['f0_med'], f['f0_rng'], f['rms_db'], f['dur'], f['sim']))
        med = [r['f0_med'] for r in rows]
        db = [r['rms_db'] for r in rows]
        print('SPREAD %-10s f0_med极差=%.1fHz rms_db极差=%.1fdB' % (
            req_mode, np.nanmax(med) - np.nanmin(med), np.nanmax(db) - np.nanmin(db)))
    print('== B. instruct2 开心 x6：sim 与 f0_rng 的相关性 ==')
    sims, rngs = [], []
    for i in range(6):
        f = feats(tts(vid, '开心', 'instruct2'))
        sims.append(f['sim'])
        rngs.append(f['f0_rng'])
        print('#%d sim=%s f0_rng=%.1f' % (i + 1, f['sim'], f['f0_rng']))
    print('CORR sim~f0_rng = %.2f' % float(np.corrcoef(sims, rngs)[0, 1]))


if __name__ == '__main__':
    main()
