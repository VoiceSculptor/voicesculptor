"""envcheck 单测：各检测分支、异常兜底、能力推导与缓存。"""

import shutil
import sys
import time
import types

import pytest

from voicesculptor.envcheck import checks
from voicesculptor.envcheck import runner


class _FakeEngine:

    def __init__(self, payload):
        self._payload = payload

    def health(self):
        return self._payload


class _FakeStore:

    def __init__(self, writable=True, broken=None):
        self._writable = writable
        self._broken = broken or []

    def is_writable(self):
        return self._writable

    def broken_voices(self):
        return self._broken


def _ctx(**overrides):
    settings = types.SimpleNamespace(model_dir=overrides.pop('model_dir', ''),
                                     voice_dir=overrides.pop('voice_dir', ''))
    return checks.CheckContext(settings=settings,
                               cosyvoice=overrides.pop('cosyvoice',
                                                       _FakeEngine(None)),
                               emotion=overrides.pop('emotion',
                                                     _FakeEngine(None)),
                               store=overrides.pop('store', _FakeStore()))


def test_python_ok_on_311():
    assert checks.check_python(_ctx()).level is checks.Level.OK


def test_python_fail_on_other_version(monkeypatch):
    monkeypatch.setattr(sys, 'version_info', (3, 10, 0))
    assert checks.check_python(_ctx()).level is checks.Level.FAIL


def test_model_files_ok(tmp_path):
    ctx = _ctx(model_dir=str(tmp_path))
    for name in checks.MODEL_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
    result = checks.check_model_files(ctx)
    assert result.level is checks.Level.OK


def test_model_files_fail_lists_missing(tmp_path):
    result = checks.check_model_files(_ctx(model_dir=str(tmp_path)))
    assert result.level is checks.Level.FAIL
    assert 'llm.pt' in result.message


def test_cosyvoice_ok_and_fail():
    ok = checks.check_cosyvoice(
        _ctx(cosyvoice=_FakeEngine({'sample_rate': 24000})))
    assert ok.level is checks.Level.OK
    down = checks.check_cosyvoice(_ctx(cosyvoice=_FakeEngine(None)))
    assert down.level is checks.Level.FAIL
    assert '未启动' in down.message
    wrong = checks.check_cosyvoice(_ctx(cosyvoice=_FakeEngine({'x': 1})))
    assert wrong.level is checks.Level.FAIL


def test_emotion_levels():
    down = checks.check_emotion_service(_ctx(emotion=_FakeEngine(None)))
    assert down.level is checks.Level.WARN
    loading = checks.check_emotion_service(
        _ctx(emotion=_FakeEngine({'loaded': False})))
    assert loading.level is checks.Level.WARN
    ok = checks.check_emotion_service(
        _ctx(emotion=_FakeEngine({
            'loaded': True,
            'model': 'fake'
        })))
    assert ok.level is checks.Level.OK


def test_voice_dir_and_broken_voices():
    assert checks.check_voice_dir(
        _ctx(store=_FakeStore(writable=True))).level is checks.Level.OK
    assert checks.check_voice_dir(
        _ctx(store=_FakeStore(writable=False))).level is checks.Level.FAIL
    assert checks.check_broken_voices(
        _ctx(store=_FakeStore(broken=[]))).level is checks.Level.OK
    warn = checks.check_broken_voices(
        _ctx(store=_FakeStore(broken=['v_a', 'v_b'])))
    assert warn.level is checks.Level.WARN
    assert 'v_a' in warn.message


def test_disk_space_branches(monkeypatch):
    usage = types.SimpleNamespace(free=3 * checks.GIB)
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: usage)
    assert checks.check_disk_space(_ctx()).level is checks.Level.OK
    monkeypatch.setattr(shutil, 'disk_usage',
                        lambda path: types.SimpleNamespace(free=512 * 1024**2))
    assert checks.check_disk_space(_ctx()).level is checks.Level.WARN
    monkeypatch.setattr(shutil, 'disk_usage',
                        lambda path: types.SimpleNamespace(free=50 * 1024**2))
    assert checks.check_disk_space(_ctx()).level is checks.Level.FAIL


def test_proxy_warns_without_no_proxy(monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:7890')
    monkeypatch.delenv('NO_PROXY', raising=False)
    monkeypatch.delenv('no_proxy', raising=False)
    assert checks.check_proxy(_ctx()).level is checks.Level.WARN
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    assert checks.check_proxy(_ctx()).level is checks.Level.OK


def test_runner_turns_exception_into_fail():

    def boom(_ctx):
        raise RuntimeError('kaboom')

    result = runner._run_one('demo', '演示', boom, None)
    assert result.level is checks.Level.FAIL
    assert '检测异常' in result.message
    assert 'kaboom' in result.message


def test_derive_capabilities():
    results = [
        checks.CheckResult('model_files', '模型文件', checks.Level.OK, ''),
        checks.CheckResult('cosyvoice', '合成引擎', checks.Level.FAIL, ''),
        checks.CheckResult('emotion_service', '情绪服务', checks.Level.OK, ''),
        checks.CheckResult('voice_dir', '音色目录', checks.Level.OK, ''),
        checks.CheckResult('disk_space', '磁盘空间', checks.Level.WARN, ''),
    ]
    caps = runner.derive_capabilities(results)
    assert caps['synthesize'] is False
    assert caps['similarity'] is True
    assert caps['emotion'] is True
    assert caps['clone'] is True
    assert caps['formats'][0] == 'wav'


def test_env_cache_reuses_fresh_report(monkeypatch):
    calls = {'count': 0}

    def fake_run_all(ctx):
        calls['count'] += 1
        return runner.EnvReport([], {}, time.time())

    monkeypatch.setattr(runner, 'run_all', fake_run_all)
    cache = runner.EnvCache(ttl=60)
    first = cache.get(None)
    second = cache.get(None)
    assert first is second
    assert calls['count'] == 1
    cache.get(None, refresh=True)
    assert calls['count'] == 2


@pytest.mark.parametrize('level', [checks.Level.OK, checks.Level.WARN])
def test_env_report_has_failure_flag(level):
    report = runner.EnvReport([checks.CheckResult('x', 'X', level, '')], {},
                              0.0)
    assert report.has_failure() is False
