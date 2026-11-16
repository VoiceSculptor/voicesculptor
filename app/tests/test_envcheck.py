"""envcheck 单测：各检测分支、异常兜底、能力推导与缓存。"""

# 测试需要直接调用私有入口，并用桩函数模拟慢检测，这里统一放行。
# pylint: disable=protected-access,unused-argument

import shutil
import sys
import time
import types

import pytest

from voicesculptor.envcheck import checks
from voicesculptor.envcheck import fixes
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

    def boom(context):
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


def _item(check_id, level=checks.Level.FAIL):
    return checks.CheckResult(check_id, check_id, level, 'demo')


def test_light_context_voice_dir_missing(tmp_path):
    ctx = checks.CheckContext(
        types.SimpleNamespace(voice_dir=str(tmp_path / 'missing')))
    result = checks.check_voice_dir(ctx)
    assert result.level is checks.Level.FAIL
    assert '--fix' in result.hint


def test_light_context_voice_dir_writable(tmp_path):
    ctx = checks.CheckContext(types.SimpleNamespace(voice_dir=str(tmp_path)))
    assert checks.check_voice_dir(ctx).level is checks.Level.OK


def test_light_context_scans_broken_voices(tmp_path):
    broken = tmp_path / 'vid1'
    broken.mkdir()
    (broken / 'meta.json').write_text('{}', encoding='utf-8')
    ctx = checks.CheckContext(types.SimpleNamespace(voice_dir=str(tmp_path)))
    assert checks.check_broken_voices(ctx).level is checks.Level.WARN


def test_light_context_engine_probe_offline():
    settings = types.SimpleNamespace(cosyvoice_base='http://127.0.0.1:9',
                                     emotion_base='http://127.0.0.1:9')
    ctx = checks.CheckContext(settings)
    assert checks.check_cosyvoice(ctx).level is checks.Level.FAIL
    assert checks.check_emotion_service(ctx).level is checks.Level.WARN


def test_fix_voice_dir_creates_directory(tmp_path):
    voice_dir = tmp_path / 'voices'
    ctx = checks.CheckContext(types.SimpleNamespace(voice_dir=str(voice_dir)))
    outcome = fixes.fix_voice_dir(ctx, _item('voice_dir'))
    assert outcome.ok is True
    assert voice_dir.is_dir()


def test_fix_broken_voices_quarantines(tmp_path):
    broken = tmp_path / 'vid1'
    broken.mkdir()
    (broken / 'meta.json').write_text('{}', encoding='utf-8')
    ctx = checks.CheckContext(types.SimpleNamespace(voice_dir=str(tmp_path)))
    outcome = fixes.fix_broken_voices(ctx, _item('broken_voices'))
    assert outcome.ok is True
    assert not broken.exists()
    assert (tmp_path / '.broken').is_dir()


def test_fix_packages_without_uv(monkeypatch):
    monkeypatch.setattr(fixes.shutil, 'which', lambda name: None)
    ctx = checks.CheckContext(types.SimpleNamespace())
    outcome = fixes.fix_packages(ctx, _item('packages'))
    assert outcome.ok is False
    assert 'uv' in outcome.message


def test_fix_model_files_points_to_launcher():
    ctx = checks.CheckContext(types.SimpleNamespace(model_dir='C:/models'))
    outcome = fixes.fix_model_files(ctx, _item('model_files'))
    assert outcome.ok is False
    assert '--download-models' in outcome.message


def test_download_models_runs_script(tmp_path, monkeypatch):
    script = tmp_path / 'download_models.py'
    script.write_text('', encoding='utf-8')
    monkeypatch.setattr(fixes.config, 'ROOT_DIR', str(tmp_path))
    monkeypatch.setattr(fixes.shutil, 'which', lambda name: 'uv.exe')
    seen = {}

    def fake_run(argv, timeout):
        seen['argv'] = argv
        return 0, 'ok'

    monkeypatch.setattr(fixes, '_run_command', fake_run)
    ctx = checks.CheckContext(
        types.SimpleNamespace(model_dir=str(tmp_path / 'models')))
    outcome = fixes.download_models(ctx, _item('model_files'))
    assert outcome.ok is True
    assert 'download_models.py' in ' '.join(seen['argv'])


def test_apply_only_touches_repairable_failures(tmp_path, monkeypatch):
    ctx = checks.CheckContext(
        types.SimpleNamespace(voice_dir=str(tmp_path / 'voices')))
    report = types.SimpleNamespace(checks=[
        checks.CheckResult('voice_dir', '音色目录', checks.Level.FAIL, ''),
        checks.CheckResult('seed_refs', '种子参考', checks.Level.WARN, ''),
        checks.CheckResult('python', 'Python 版本', checks.Level.OK, ''),
    ])
    monkeypatch.setattr(fixes, 'fix_python', lambda ctx, item: None)
    outcomes = fixes.apply(report, ctx)
    assert [item.id for item in outcomes] == ['voice_dir']


def test_fix_packages_keeps_extra_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(fixes.shutil, 'which', lambda name: 'uv.exe')
    seen = {}

    def fake_run(argv, timeout):
        seen['argv'] = argv
        return 0, 'ok'

    monkeypatch.setattr(fixes, '_run_command', fake_run)
    monkeypatch.setattr(fixes.config, 'APP_DIR', str(tmp_path))
    ctx = checks.CheckContext(types.SimpleNamespace())
    outcome = fixes.fix_packages(ctx, _item('packages'))
    assert outcome.ok is True
    assert '--inexact' in seen['argv']
