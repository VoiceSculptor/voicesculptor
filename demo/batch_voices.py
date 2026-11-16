# -*- coding: utf-8 -*-
"""批量处理音色（仓库根目录，Git Bash）：
  uv run --project app python demo/batch_voices.py preprocess [--apply] [--only VID]
      对存量音色补做参考音频预处理（app.preprocess_ref）。默认只打印计划；--apply 才写盘，
      写之前把原文件备份为 ref.orig.wav；处理完在 meta.json 里记 preproc=1，保证幂等。
      旧版种子（无 group 字段）在 --apply 时删除目录，再由 app.seed_defaults() 从 runtime/ 重建。
  uv run --project app python demo/batch_voices.py label
      用情绪服务（EMOTION_BASE，默认 50001）核对每个音色参考音频的实际情绪，只打印不写盘。
  uv run --project app python demo/batch_voices.py import <目录> [--group G] [--emotion 平静|auto]
      把目录下的音频逐个通过 /api/voices 导入（STUDIO_BASE，默认 8091）；同名 .txt 作为转录。
      --emotion auto 时用情绪服务判定，判不出则记为 平静。
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
import requests
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app'))
STUDIO = os.environ.get('STUDIO_BASE', 'http://127.0.0.1:8091')
EMO = os.environ.get('EMOTION_BASE', 'http://127.0.0.1:50001')
AUDIO_EXT = ('.wav', '.mp3', '.m4a', '.flac', '.ogg')


def _write_meta(d, meta):
    tmp = os.path.join(d, 'meta.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(d, 'meta.json'))


def _has_pre_tail(wav, sr):
    """preprocess_ref 会在尾部补 0.2s 纯零；有这段说明已经预处理过"""
    n = int(sr * 0.2)
    return len(wav) > n and not np.any(wav[-n:])


def cmd_preprocess(apply, only):
    import app as A
    cnt = dict(plan=0, marked=0, stale_seed=0, skip=0, applied=0)
    stale = False
    for meta in A.list_voices():
        vid = meta['voice_id']
        if only and vid != only:
            continue
        d = os.path.join(A.VOICE_DIR, vid)
        ref = os.path.join(d, 'ref.wav')
        if meta.get('preproc'):
            cnt['skip'] += 1
            print('SKIP', vid, 'flagged')
            continue
        if meta.get('source') == 'seed':
            if meta.get('group'):
                cnt['marked'] += 1
                print('MARK', vid, 'seed-new')
                if apply:
                    _write_meta(d, dict(meta, preproc=1))
            else:
                cnt['stale_seed'] += 1
                print('STALE_SEED', vid)
                if apply:
                    shutil.rmtree(d, ignore_errors=True)
                    stale = True
            continue
        if not os.path.isfile(ref):
            cnt['skip'] += 1
            print('SKIP', vid, 'no-ref')
            continue
        wav, sr = sf.read(ref, dtype='float32')
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        if _has_pre_tail(wav, sr):
            cnt['marked'] += 1
            print('MARK', vid, 'zero-tail')
            if apply:
                _write_meta(d, dict(meta, preproc=1))
            continue
        y = A.preprocess_ref(wav, sr)
        old, new = len(wav) / sr, len(y) / sr
        if not 0.5 <= new <= 30:
            cnt['skip'] += 1
            print('SKIP', vid, 'bad-dur %.2fs' % new)
            continue
        cnt['plan'] += 1
        if not apply:
            print('PLAN', vid, '%.2fs -> %.2fs' % (old, new))
            continue
        bak = os.path.join(d, 'ref.orig.wav')
        if not os.path.exists(bak):
            shutil.copy2(ref, bak)
        sf.write(ref, y, sr)
        _write_meta(d, dict(meta, preproc=1))
        cnt['applied'] += 1
        print('APPLIED', vid, '%.2fs -> %.2fs' % (old, new))
    if stale:
        A.seed_defaults()
    print('SUMMARY ' + ' '.join('%s=%d' % kv for kv in cnt.items()))


def cmd_label():
    import app as A
    try:
        requests.get(EMO + '/health', timeout=3).raise_for_status()
    except Exception as e:
        print('SUMMARY svc=down', e)
        sys.exit(2)
    total = match = 0
    for meta in A.list_voices():
        vid = meta['voice_id']
        ref = os.path.join(A.VOICE_DIR, vid, 'ref.wav')
        if not os.path.isfile(ref):
            continue
        with open(ref, 'rb') as f:
            r = requests.post(EMO + '/emotion', files={'file': ('a.wav', f.read(), 'audio/wav')}, timeout=120)
        if not r.ok:
            print('ERR', vid, r.status_code, r.text[:200])
            continue
        j = r.json()
        want = A.voice_emotion(meta)
        total += 1
        match += int(j.get('cn') == want)
        print('%-12s meta=%s det=%s label=%s score=%.3f'
              % (vid, want, j.get('cn'), j['label'], j['scores'][j['label']]))
    print('SUMMARY svc=ok total=%d match=%d' % (total, match))


def cmd_import(folder, group, emotion):
    if not os.path.isdir(folder):
        sys.exit('目录不存在: ' + folder)
    ok = fail = 0
    for fn in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(fn)
        if ext.lower() not in AUDIO_EXT:
            continue
        p = os.path.join(folder, fn)
        txt = os.path.join(folder, stem + '.txt')
        prompt = ''
        if os.path.isfile(txt):
            with open(txt, encoding='utf-8') as f:
                prompt = f.read().strip()
        with open(p, 'rb') as f:
            data = f.read()
        emo = emotion
        if emotion == 'auto':
            try:
                r = requests.post(EMO + '/emotion', files={'file': (fn, data, 'application/octet-stream')},
                                  timeout=120)
                emo = (r.json().get('cn') if r.ok else None) or '平静'
            except requests.RequestException:
                emo = '平静'
        r = requests.post(STUDIO + '/api/voices',
                          data={'name': stem, 'prompt': prompt, 'emotion': emo, 'group': group},
                          files={'ref': (fn, data, 'application/octet-stream')}, timeout=120)
        if r.ok:
            j = r.json()
            ok += 1
            print('IMPORTED', stem, j['voice_id'], emo, ';'.join(j.get('warnings', [])))
        else:
            fail += 1
            print('FAILED', stem, r.status_code, r.text[:200])
    print('SUMMARY imported=%d failed=%d' % (ok, fail))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('preprocess')
    p1.add_argument('--apply', action='store_true')
    p1.add_argument('--only', default='')
    sub.add_parser('label')
    p3 = sub.add_parser('import')
    p3.add_argument('folder')
    p3.add_argument('--group', default='')
    p3.add_argument('--emotion', default='平静')
    a = ap.parse_args()
    if a.cmd == 'preprocess':
        cmd_preprocess(a.apply, a.only)
    elif a.cmd == 'label':
        cmd_label()
    else:
        cmd_import(a.folder, a.group, a.emotion)


if __name__ == '__main__':
    main()
