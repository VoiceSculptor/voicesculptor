"""pytest 全局配置：先起假服务，再让被测模块读到假服务地址。"""

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests import fakes  # pylint: disable=wrong-import-position

_SERVERS = {}
_TMP_DIRS = []


def pytest_configure(config):
    """启动假引擎与假情绪服务，把地址写进环境变量。"""
    del config
    engine = fakes.run_in_thread(fakes.make_fake_engine())
    emotion = fakes.run_in_thread(fakes.make_fake_emotion())
    os.environ['COSYVOICE_BASE'] = engine.__enter__()
    os.environ['EMOTION_BASE'] = emotion.__enter__()
    os.environ['VS_EMOTION_RANK'] = '1'
    os.environ['VS_TTS_CONCURRENCY'] = '1'
    os.environ.pop('COSYVOICE_MODEL_DIR', None)
    voice_dir = tempfile.mkdtemp(prefix='vs-voices-')
    log_dir = tempfile.mkdtemp(prefix='vs-logs-')
    os.environ['VS_VOICE_DIR'] = voice_dir
    os.environ['VS_LOG_DIR'] = log_dir
    _TMP_DIRS.extend([voice_dir, log_dir])
    _SERVERS['engine'] = engine
    _SERVERS['emotion'] = emotion


def pytest_unconfigure(config):
    """关闭假服务与临时目录。"""
    del config
    for server in _SERVERS.values():
        server.__exit__(None, None, None)
    _SERVERS.clear()
    for path in _TMP_DIRS:
        shutil.rmtree(path, ignore_errors=True)
    _TMP_DIRS.clear()


@pytest.fixture(scope='session')
def engine_url():
    """假引擎地址。"""
    return os.environ['COSYVOICE_BASE']


@pytest.fixture(scope='session')
def emotion_url():
    """假情绪服务地址。"""
    return os.environ['EMOTION_BASE']


@pytest.fixture(scope='session')
def settings():
    """按当前环境变量构造的配置。"""
    from voicesculptor import config  # pylint: disable=import-outside-toplevel

    return config.Settings.from_env()
