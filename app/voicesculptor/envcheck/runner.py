"""执行全部检测、推导能力开关、提供 10 秒缓存。"""

import dataclasses
import threading
import time

from voicesculptor.envcheck import checks

CHECK_BUDGET_SECONDS = 3.0
CACHE_TTL_SECONDS = 10.0

CHECK_FUNCTIONS = (
    ('python', 'Python 版本', checks.check_python),
    ('packages', '依赖包', checks.check_packages),
    ('torch_cuda', 'CUDA', checks.check_torch_cuda),
    ('model_files', '模型文件', checks.check_model_files),
    ('cosyvoice', '合成引擎', checks.check_cosyvoice),
    ('emotion_service', '情绪服务', checks.check_emotion_service),
    ('audio_formats', '音频格式', checks.check_audio_formats),
    ('voice_dir', '音色目录', checks.check_voice_dir),
    ('broken_voices', '损坏音色', checks.check_broken_voices),
    ('seed_refs', '种子参考', checks.check_seed_refs),
    ('disk_space', '磁盘空间', checks.check_disk_space),
    ('proxy', '代理', checks.check_proxy),
)


@dataclasses.dataclass
class EnvReport:
    """一次完整检测的结果。"""

    checks: list[checks.CheckResult]
    capabilities: dict
    generated_at: float

    def to_dict(self) -> dict:
        """序列化成 JSON 友好的字典。"""
        return {
            'generated_at': self.generated_at,
            'checks': [item.to_dict() for item in self.checks],
            'capabilities': self.capabilities,
        }

    def has_failure(self) -> bool:
        """是否存在 FAIL 项。"""
        return any(item.level is checks.Level.FAIL for item in self.checks)


def _run_one(check_id, title, func, ctx) -> checks.CheckResult:
    """在独立线程里跑一项检测，超过预算就算超时。"""
    box = {}

    def target():
        try:
            box['result'] = func(ctx)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            box['error'] = exc

    thread = threading.Thread(target=target, daemon=True)
    started = time.time()
    thread.start()
    thread.join(CHECK_BUDGET_SECONDS)
    elapsed_ms = int((time.time() - started) * 1000)
    if thread.is_alive():
        return checks.CheckResult(check_id, title, checks.Level.FAIL,
                                  '检测超时（3 秒）', '', elapsed_ms)
    if 'error' in box:
        return checks.CheckResult(check_id, title, checks.Level.FAIL,
                                  '检测异常: ' + repr(box['error']), '', elapsed_ms)
    result = box['result']
    result.elapsed_ms = elapsed_ms
    return result


def _supported_formats() -> list[str]:
    """当前 libsndfile 支持的上传扩展名。"""
    try:
        import soundfile as sf  # pylint: disable=import-outside-toplevel
        available = sf.available_formats()
    except Exception:  # pylint: disable=broad-exception-caught
        return ['wav']
    formats = ['wav']
    for name, suffix in checks.AUDIO_FORMATS:
        if name in available:
            formats.append(suffix)
    return formats


def derive_capabilities(results: list[checks.CheckResult]) -> dict:
    """把检测结果折算成前端开关。"""
    levels = {item.id: item.level for item in results}
    model_ok = levels.get('model_files') is checks.Level.OK
    engine_ok = levels.get('cosyvoice') is checks.Level.OK
    emotion_ok = levels.get('emotion_service') is checks.Level.OK
    voice_ok = levels.get('voice_dir') is checks.Level.OK
    disk_ok = levels.get('disk_space') is not checks.Level.FAIL
    return {
        'synthesize': model_ok and engine_ok,
        'similarity': model_ok,
        'emotion': emotion_ok,
        'clone': voice_ok and disk_ok,
        'formats': _supported_formats(),
    }


def run_all(ctx) -> EnvReport:
    """依次执行 12 项检测；任何异常都转成 FAIL，不向外抛。"""
    results = [
        _run_one(check_id, title, func, ctx)
        for check_id, title, func in CHECK_FUNCTIONS
    ]
    return EnvReport(results, derive_capabilities(results), time.time())


class EnvCache:
    """带 TTL 的检测结果缓存。"""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._report = None
        self._lock = threading.Lock()

    def get(self, ctx, refresh: bool = False) -> EnvReport:
        """返回缓存结果；过期、缺失或 refresh 时重新检测。"""
        with self._lock:
            now = time.time()
            stale = (self._report is None or
                     now - self._report.generated_at > self._ttl)
            if refresh or stale:
                self._report = run_all(ctx)
            return self._report
