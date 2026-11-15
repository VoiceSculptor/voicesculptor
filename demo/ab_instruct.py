# -*- coding: utf-8 -*-
"""指令 A/B 实验：比较自造指令与官方训练指令的情绪命中率与音色损失。

背景：CosyVoice3 的训练指令集里只有“开心/伤心/生气”三条情绪指令（见
engine/CosyVoice/cosyvoice/utils/common.py 的 instruct_list），app 里
“撒娇 / 平静 / 惊讶”是自造句式，效果没有保证。

用法（仓库根目录，引擎 50000 与应用 8091 已启动）：
    uv run --project app python demo/ab_instruct.py <voice_id>

输出每个（情绪, 变体）一行：hit=k/3、sim 均值、f0_rng 均值；
最后对每种情绪打印 ADOPT（建议改用该变体）或 KEEP（保留 app 内置指令）。
本脚本只给建议，不写回 EMOTION_INSTRUCT。
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
RUNS = 3

# 空字符串表示使用 app 内置的 EMOTION_INSTRUCT
VARIANTS = {
    '撒娇': ['', 'You are a helpful assistant. Please say a sentence in a very soft voice.',
             'You are a helpful assistant. 请非常开心地说一句话。'],
    '平静': ['', 'You are a helpful assistant. Please say a sentence in a very soft voice.',
             'You are a helpful assistant. 请用尽可能慢地语速说一句话。'],
    '惊讶': ['', 'You are a helpful assistant. 请非常惊讶地说一句话。',
             'You are a helpful assistant. Please say a sentence as loudly as possible.'],
}


def tts(vid, emo, instr):
    data = {'voice_id': vid, 'text': LINE, 'emotion': emo, 'mode': 'instruct2',
            'speed': '1.0', 'quality': 'balanced', 'verify': 'true'}
    if instr:
        data['instruct_text'] = instr
    r = requests.post(BASE + '/api/tts', data=data, timeout=900)
    r.raise_for_status()
    return r.json()


def f0_rng(j):
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
    return float(np.percentile(f0, 90) - np.percentile(f0, 10)) if len(f0) else float('nan')


def main():
    if len(sys.argv) != 2:
        sys.exit('用法: python demo/ab_instruct.py <voice_id>')
    vid = sys.argv[1]
    print('voice=%s  text=%s  runs=%d' % (vid, LINE, RUNS))
    print('%-5s %-3s %-10s %8s %8s' % ('emo', 'var', 'hit', 'sim_mean', 'f0_rng'))
    decisions = []
    for emo, variants in VARIANTS.items():
        base_hit, base_sim = None, None
        best = None
        for vi, v in enumerate(variants):
            hits, sims, rngs = 0, [], []
            for _ in range(RUNS):
                try:
                    j = tts(vid, emo, v)
                except Exception as e:
                    print('%-5s %-3d 请求失败: %s' % (emo, vi, e))
                    break
                if j.get('emotion_detected') == emo:
                    hits += 1
                if j.get('sim') is not None:
                    sims.append(float(j['sim']))
                rngs.append(f0_rng(j))
            sim_mean = float(np.mean(sims)) if sims else float('nan')
            print('%-5s %-3d %-10s %8.3f %8.1f' % (emo, vi, '%d/%d' % (hits, RUNS), sim_mean, float(np.nanmean(rngs))))
            if vi == 0:
                base_hit, base_sim = hits, sim_mean
            elif best is None or hits > best[0] or (hits == best[0] and sim_mean > best[1]):
                best = (hits, sim_mean, vi)
        if best and base_hit is not None and best[0] >= base_hit + 1 and best[1] >= base_sim - 0.02:
            decisions.append((emo, 'ADOPT', variants[best[2]]))
        else:
            decisions.append((emo, 'KEEP', ''))
    print('== DECISION ==')
    for emo, action, text in decisions:
        print('%s %s %s' % (action, emo, text))


if __name__ == '__main__':
    main()
