# -*- coding: utf-8 -*-
"""P2 评测：split vs instruct2 vs zero_shot（不带情绪的音色基线）。sim 都相对音色参考计算。
用法：uv run --project app python demo/ab_split.py <音色voice_id，默认 calm> [每组轮数，默认 3]
需要：引擎(50000, 已含 /inference_split_prompt)、app(8091)、情绪服务(50001) 都在运行。"""
import os
import sys

import requests

STUDIO = os.environ.get('STUDIO_BASE', 'http://127.0.0.1:8091')
TEXT = '今天发生的事情，我一定要好好跟你讲一讲。'
EMO_REF = {'开心': 'happy', '生气': 'angry', '难过': 'sad', '惊讶': 'surprise', '撒娇': 'coquettish'}
METHODS = ('zero_shot', 'instruct2', 'split')


def run(voice, emo, method):
    data = {'voice_id': voice, 'text': TEXT, 'emotion': emo, 'mode': method,
            'quality': 'balanced', 'verify': 'true'}
    if method == 'split':
        data['emo_voice_id'] = EMO_REF[emo]
    r = requests.post(STUDIO + '/api/tts', data=data, timeout=900)
    r.raise_for_status()
    j = r.json()
    return j['sim'], j['emotion_detected'], j['mode']


def main():
    voice = sys.argv[1] if len(sys.argv) > 1 else 'calm'
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    res = {}
    for emo, ev in EMO_REF.items():
        if ev == voice:
            continue
        for m in METHODS:
            sims, hits, used = [], 0, ''
            for _ in range(rounds):
                s, det, used = run(voice, emo, m)
                if s is not None:
                    sims.append(s)
                hits += int(det == emo)
            mean = sum(sims) / len(sims) if sims else float('nan')
            res[(emo, m)] = (hits, mean)
            print('%s  %-9s  hit=%d/%d  sim_mean=%.3f  used=%s' % (emo, m, hits, rounds, mean, used))
    for emo in EMO_REF:
        if (emo, 'split') not in res:
            continue
        hs, ss = res[(emo, 'split')]
        hi, si = res[(emo, 'instruct2')]
        print(('SPLIT_BETTER ' if (hs >= hi and ss >= si - 0.01) else 'SPLIT_WORSE ') + emo)


if __name__ == '__main__':
    main()
