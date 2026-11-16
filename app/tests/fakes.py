"""测试用的假引擎 / 假情绪服务。

用 uvicorn 在随机端口起真实的 HTTP 服务，这样被测代码走的还是
requests 网络路径，行为与真实引擎一致，不需要打桩。
"""

import contextlib
import socket
import threading
import time

import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response

SAMPLE_RATE = 24000
CLIP_SECONDS = 1.5
CLIP_HZ = 220.0


def make_pcm(seconds=CLIP_SECONDS, freq=CLIP_HZ, sr=SAMPLE_RATE):
    """生成一段 int16 单声道 PCM（正弦波），时长固定。"""
    count = int(seconds * sr)
    t = np.arange(count, dtype=np.float64) / sr
    wave = 0.2 * np.sin(2.0 * np.pi * freq * t)
    return (wave * 32767.0).astype('<i2').tobytes()


def make_fake_engine():
    """构造只实现 CosyVoice 三个推理接口的假引擎。"""
    app = FastAPI()
    pcm = make_pcm()

    @app.get('/health')
    def health():
        return {'sample_rate': SAMPLE_RATE}

    @app.post('/add_zero_shot_spk')
    async def add_spk(request: Request):
        form = await request.form()
        return {'ok': True, 'spk_id': form.get('spk_id')}

    @app.post('/inference_zero_shot_spk')
    def inference_zero_shot_spk():
        return Response(content=pcm, media_type='application/octet-stream')

    @app.post('/inference_cross_lingual')
    def inference_cross_lingual():
        return Response(content=pcm, media_type='application/octet-stream')

    @app.post('/inference_instruct2')
    def inference_instruct2():
        return Response(content=pcm, media_type='application/octet-stream')

    @app.post('/inference_split_prompt')
    def inference_split_prompt():
        return Response(content=pcm, media_type='application/octet-stream')

    return app


def make_fake_emotion(label='happy', cn='开心'):
    """构造返回固定情绪标签的假情绪服务。"""
    app = FastAPI()
    scores = {'happy': 0.62, 'sad': 0.05, 'angry': 0.04, 'neutral': 0.2}
    cn_scores = {cn: 0.62, '难过': 0.05, '生气': 0.04, '平静': 0.2}

    @app.get('/health')
    def health():
        return {'ok': True, 'model': 'fake', 'device': 'cpu', 'loaded': True}

    @app.post('/emotion')
    def emotion():
        return {'label': label, 'cn': cn, 'scores': scores,
                'cn_scores': cn_scores}

    return app


@contextlib.contextmanager
def run_in_thread(app):
    """用 uvicorn 在随机空闲端口跑一个 FastAPI 应用。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_level='warning', lifespan='off')
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]},
                              daemon=True)
    thread.start()
    deadline = time.time() + 15
    while time.time() < deadline:
        if server.started:
            break
        time.sleep(0.02)
    if not server.started:
        sock.close()
        raise RuntimeError('假服务启动超时')
    try:
        yield 'http://127.0.0.1:%d' % port
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
