"""pytest 全局配置：先起假服务，再让被测模块读到假服务地址。"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests import fakes  # pylint: disable=wrong-import-position

_SERVERS = {}


def pytest_configure(config):
    """启动假引擎与假情绪服务，把地址写进环境变量。"""
    engine = fakes.run_in_thread(fakes.make_fake_engine())
    emotion = fakes.run_in_thread(fakes.make_fake_emotion())
    os.environ['COSYVOICE_BASE'] = engine.__enter__()
    os.environ['EMOTION_BASE'] = emotion.__enter__()
    os.environ['VS_EMOTION_RANK'] = '1'
    os.environ['VS_TTS_CONCURRENCY'] = '1'
    os.environ.pop('COSYVOICE_MODEL_DIR', None)
    _SERVERS['engine'] = engine
    _SERVERS['emotion'] = emotion


def pytest_unconfigure(config):
    """关闭假服务。"""
    for server in _SERVERS.values():
        server.__exit__(None, None, None)
    _SERVERS.clear()


@pytest.fixture(scope='session')
def engine_url():
    """假引擎地址。"""
    return os.environ['COSYVOICE_BASE']


@pytest.fixture(scope='session')
def emotion_url():
    """假情绪服务地址。"""
    return os.environ['EMOTION_BASE']
