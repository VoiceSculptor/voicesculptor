# -*- coding: utf-8 -*-
"""把 sample.wav 导入声刻 Studio，再用与情绪匹配的台词合成六种情绪。

前置：引擎（50000）与应用（8091）已启动，demo/out/sample.wav + sample.txt 已存在。
用法（仓库根目录）：
    uv run --project app python demo/run_six_emotions.py
"""
import base64
import json
import os
import sys

import requests

BASE = os.environ.get('STUDIO_BASE', 'http://127.0.0.1:8091')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
LINES = {
    '撒娇': '人家就要这个小玩具嘛，你陪我去买好不好呀？',
    '开心': '太好了，我们终于赢啦！今天必须好好庆祝一下！',
    '难过': '这件事我真的完全没有想到会变成这样，心里好难受。',
    '生气': '你怎么可以这样说话？我真的非常生气！',
    '平静': '今天天气不错，我们一起去公园散步吧。',
    '惊讶': '真的吗？我完全没想到会有这样的结果！',
}
EMOTIONS = [('coquettish', '撒娇'), ('happy', '开心'), ('sad', '难过'),
            ('angry', '生气'), ('calm', '平静'), ('surprise', '惊讶')]


def main():
    h = requests.get(BASE + '/api/health', timeout=5).json()
    if not h.get('engines', {}).get('cosyvoice'):
        sys.exit('引擎未就绪: %s' % h)
    sample = os.path.join(OUT, 'sample.wav')
    txt = os.path.join(OUT, 'sample.txt')
    if not (os.path.exists(sample) and os.path.exists(txt)):
        sys.exit('缺少 demo/out/sample.wav 或 sample.txt')
    prompt = open(txt, encoding='utf-8').read().strip()

    with open(sample, 'rb') as f:
        r = requests.post(BASE + '/api/voices',
                          data={'name': 'DeepSeek 样本', 'prompt': prompt, 'emoji': '🎙'},
                          files={'ref': ('sample.wav', f.read(), 'audio/wav')},
                          timeout=120)
    r.raise_for_status()
    vid = r.json()['voice_id']
    print('voice_id', vid)

    results = []
    for i, (key, emo) in enumerate(EMOTIONS, 1):
        r = requests.post(BASE + '/api/tts', data={
            'voice_id': vid, 'text': LINES[emo], 'emotion': emo, 'mode': 'instruct2',
            'speed': '1.0', 'quality': 'best', 'best_n': '2',
            'verify': 'true'}, timeout=900)
        r.raise_for_status()
        j = r.json()
        fn = '%02d_%s.wav' % (i, key)
        with open(os.path.join(OUT, fn), 'wb') as f:
            f.write(base64.b64decode(j['audio_base64']))
        results.append(dict(file=fn, key=key, emotion=emo, sim=j.get('sim'),
                            duration=j.get('duration'), mode=j.get('mode')))
        print('%s %s sim=%s dur=%.2fs mode=%s'
              % (fn, emo, j.get('sim'), j.get('duration'), j.get('mode')))

    meta = dict(voice_id=vid, line=LINES, prompt=prompt, clips=results)
    with open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
