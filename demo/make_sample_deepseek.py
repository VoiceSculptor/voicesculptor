# -*- coding: utf-8 -*-
"""用 DeepSeek TTS 生成一段中文样本，供声刻 Studio 克隆音色。

用法（仓库根目录）：
    uv run --project app python demo/make_sample_deepseek.py

环境变量：
    DEEPSEEK_API_KEY     必填，DeepSeek 开放平台 API Key
    DEEPSEEK_TTS_URL     可选，默认 https://api.deepseek.com/v1/tools/tts
    DEEPSEEK_TTS_VOICE   可选，stella（女声，默认）或 tide（男声）
"""
import io
import os
import sys

import requests
import soundfile as sf

SAMPLE_TEXT = ('大家好，欢迎来到声刻工作室。'
               '今天我会用同一段声音，为你演示六种不同的情绪。')
URL = os.environ.get('DEEPSEEK_TTS_URL', 'https://api.deepseek.com/v1/tools/tts')
VOICE = os.environ.get('DEEPSEEK_TTS_VOICE', 'stella')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def main():
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        sys.exit('缺少环境变量 DEEPSEEK_API_KEY')
    os.makedirs(OUT, exist_ok=True)

    body = {'text': SAMPLE_TEXT, 'voice_id': VOICE, 'format': 'wav'}
    with requests.post(URL, json=body, stream=True, timeout=120,
                       headers={'Authorization': 'Bearer ' + key}) as r:
        r.raise_for_status()
        raw = b''.join(r.iter_content(8192))
    if not raw:
        sys.exit('TTS 返回空音频')

    data, sr = sf.read(io.BytesIO(raw), always_2d=True)
    mono = data.mean(axis=1)
    dur = len(mono) / float(sr)
    if not 3 <= dur <= 25:
        sys.exit('样本时长 %.2fs 不在 3~25 秒，请调整台词' % dur)

    sf.write(os.path.join(OUT, 'sample.wav'), mono, sr, subtype='PCM_16')
    with open(os.path.join(OUT, 'sample.txt'), 'w', encoding='utf-8') as f:
        f.write(SAMPLE_TEXT + '\n')
    print('OK sample.wav %.2fs %dHz' % (dur, sr))


if __name__ == '__main__':
    main()
