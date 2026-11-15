# -*- coding: utf-8 -*-
"""把 sample.wav + 六种情绪 wav 拼成 1280x720 演示视频（标题 + 波形 + 原声）。

前置：demo/out/results.json 已生成。
用法（仓库根目录）：
    uv run --project app python demo/make_video.py
"""
import json
import os
import shutil
import subprocess
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
FONT_SRC = r'C:\Windows\Fonts\msyh.ttc'
TITLE_Y = 120
SUB_Y = 250


def sentences(text):
    parts, cur = [], ''
    for ch in text.strip():
        cur += ch
        if ch in '。！？':
            parts.append(cur)
            cur = ''
    if cur:
        parts.append(cur)
    return '\n'.join(parts)


def run(cmd):
    subprocess.run(cmd, cwd=OUT, check=True)


def main():
    res_path = os.path.join(OUT, 'results.json')
    if not os.path.exists(res_path):
        sys.exit('缺少 demo/out/results.json')
    res = json.load(open(res_path, encoding='utf-8'))

    font = os.path.join(OUT, 'msyh.ttc')
    if not os.path.exists(font):
        if not os.path.exists(FONT_SRC):
            sys.exit('缺少中文字体 %s' % FONT_SRC)
        shutil.copyfile(FONT_SRC, font)

    sample = open(os.path.join(OUT, 'sample.txt'), encoding='utf-8').read().strip()
    segs = [('sample.wav', '原始样本（DeepSeek TTS）', sentences(sample))]
    for i, c in enumerate(res['clips'], 1):
        sim = c.get('sim')
        line = res['line'].get(c['emotion'], '') if isinstance(res['line'], dict) else res['line']
        sub = '「%s」\n声纹相似度 %s' % (line, '—' if sim is None else sim)
        segs.append((c['file'], '情绪 %d/6：%s' % (i, c['emotion']), sub))

    for idx, (wav, title, sub) in enumerate(segs):
        with open(os.path.join(OUT, 't%d.txt' % idx), 'w', encoding='utf-8') as f:
            f.write(title)
        with open(os.path.join(OUT, 's%d.txt' % idx), 'w', encoding='utf-8') as f:
            f.write(sub)
        fc = ('[0:a]aresample=48000,apad=pad_dur=0.8,asplit=2[a][w];'
              '[w]showwaves=s=1280x240:mode=cline:colors=0x4FC3F7:rate=30[wv];'
              'color=c=0x1E1E2E:s=1280x720:r=30[bg];'
              '[bg][wv]overlay=0:420:shortest=1,'
              'drawtext=fontfile=msyh.ttc:textfile=t%d.txt:fontsize=64:'
              'fontcolor=white:x=(w-tw)/2:y=%d,'
              'drawtext=fontfile=msyh.ttc:textfile=s%d.txt:fontsize=34:'
              'fontcolor=0xCCCCCC:x=(w-tw)/2:y=%d[v]'
              % (idx, TITLE_Y, idx, SUB_Y))
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', wav,
             '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30',
             '-c:a', 'aac', '-ar', '48000', '-ac', '2', 'seg%d.mp4' % idx])

    with open(os.path.join(OUT, 'list.txt'), 'w', encoding='utf-8') as f:
        for idx in range(len(segs)):
            f.write("file 'seg%d.mp4'\n" % idx)
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
         '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy',
         'demo_six_emotions.mp4'])
    print('OK demo_six_emotions.mp4')


if __name__ == '__main__':
    main()
