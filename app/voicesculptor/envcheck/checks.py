"""12 项环境检测。

每项检测都是纯函数：拿到 CheckContext，返回 CheckResult，不抛异常
（runner 会兜底）。检测只读，不改任何状态。
"""

# 所有检测函数统一签名，部分函数不需要 ctx。
# pylint: disable=unused-argument

import dataclasses
import enum
import http.client
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
import urllib.parse

from voicesculptor import config

REQUIRED_PACKAGES = ('fastapi', 'numpy', 'onnxruntime', 'soundfile', 'torch',
                     'torchaudio', 'requests')
MODEL_FILES = ('llm.pt', 'flow.pt', 'hift.pt', 'campplus.onnx',
               'speech_tokenizer_v3.onnx',
               os.path.join('CosyVoice-BlankEN', 'model.safetensors'))
SEED_FILES = (
    ('coquettish', os.path.join(config.ROXY_ORIG, 'coquettish.wav')),
    ('happy', os.path.join(config.ROXY_ORIG, 'happy.wav')),
    ('sad', os.path.join(config.ROXY_SEL, 'sad_v2.wav')),
    ('angry', os.path.join(config.ROXY_ORIG, 'angry.wav')),
    ('calm', os.path.join(config.ROXY_SEL, 'calm_v2.wav')),
    ('surprise', os.path.join(config.ROXY_ORIG, 'surprise.wav')),
)
AUDIO_FORMATS = (('MP3', 'mp3'), ('FLAC', 'flac'), ('OGG', 'ogg'))
PROXY_KEYS = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy',
              'https_proxy', 'all_proxy')
LOCAL_HOSTS = ('127.0.0.1', 'localhost')
GIB = 1024**3
DISK_WARN_BYTES = 2 * GIB
DISK_FAIL_BYTES = 200 * 1024**2
PYTHON_TARGET = (3, 11)


class Level(str, enum.Enum):
    """检测级别。"""

    OK = 'OK'
    WARN = 'WARN'
    FAIL = 'FAIL'


@dataclasses.dataclass
class CheckResult:
    """单项检测结果。"""

    id: str
    title: str
    level: Level
    message: str
    hint: str = ''
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        """序列化成 JSON 友好的字典。"""
        return {
            'id': self.id,
            'title': self.title,
            'level': self.level.value,
            'message': self.message,
            'hint': self.hint,
            'elapsed_ms': self.elapsed_ms,
        }


@dataclasses.dataclass
class CheckContext:
    """检测需要的依赖；纯净环境里客户端与音色库可能不存在。"""

    settings: config.Settings
    cosyvoice: object | None = None
    emotion: object | None = None
    store: object | None = None


def _probe_json(base: str, path: str, timeout: float = 1.5) -> dict | None:
    """用标准库探一个本地 HTTP 接口，失败返回 None。"""
    parsed = urllib.parse.urlparse(base)
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or 80
    conn = None
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request('GET', path)
        response = conn.getresponse()
        if response.status != 200:
            return None
        return json.loads(response.read().decode('utf-8'))
    except (OSError, ValueError):
        return None
    finally:
        if conn is not None:
            conn.close()


def probe_writable(directory: str, create: bool = False) -> None:
    """验证目录可写；create=True 时会先创建目录。"""
    if create:
        os.makedirs(directory, exist_ok=True)
    if not os.path.isdir(directory):
        raise OSError(f'目录不存在: {directory}')
    handle, path = tempfile.mkstemp(prefix='.vs-probe-', dir=directory)
    os.close(handle)
    os.remove(path)


def _result(check_id: str,
            title: str,
            level: Level,
            message: str,
            hint: str = '') -> CheckResult:
    """构造一条结果。"""
    return CheckResult(check_id, title, level, message, hint)


def check_python(ctx: CheckContext) -> CheckResult:
    """Python 版本必须是 3.11。"""
    version = sys.version_info[:2]
    text = platform.python_version()
    if version == PYTHON_TARGET:
        return _result('python', 'Python 版本', Level.OK, text)
    return _result('python', 'Python 版本', Level.FAIL, f'需要 3.11，当前 {text}',
                   '用 uv 安装 Python 3.11 后重新 uv sync')


def check_packages(ctx: CheckContext) -> CheckResult:
    """关键依赖包是否齐全。"""
    versions = []
    missing = []
    for name in REQUIRED_PACKAGES:
        try:
            versions.append(f'{name} {importlib.metadata.version(name)}')
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    if missing:
        return _result('packages', '依赖包', Level.FAIL,
                       '缺失: ' + ', '.join(missing), '在 app 目录执行 uv sync')
    return _result('packages', '依赖包', Level.OK, '; '.join(versions))


def check_torch_cuda(ctx: CheckContext) -> CheckResult:
    """torch 能否使用 CUDA。"""
    try:
        import torch  # pylint: disable=import-outside-toplevel
    except ImportError:
        return _result('torch_cuda', 'CUDA', Level.FAIL, '未安装 torch',
                       '在 app 目录执行 uv sync')

    if not torch.cuda.is_available():
        return _result('torch_cuda', 'CUDA', Level.WARN,
                       '本进程 CPU 模式（引擎设备以引擎日志为准）')
    name = torch.cuda.get_device_name(0)
    memory = torch.cuda.get_device_properties(0).total_memory // (1024**2)
    return _result('torch_cuda', 'CUDA', Level.OK, f'{name} / {memory} MiB')


def check_model_files(ctx: CheckContext) -> CheckResult:
    """模型目录下 6 个文件是否齐全。"""
    missing = [
        name for name in MODEL_FILES
        if not os.path.isfile(os.path.join(ctx.settings.model_dir, name))
    ]
    if missing:
        return _result('model_files', '模型文件', Level.FAIL,
                       '缺少: ' + ', '.join(missing),
                       '运行 启动-声刻.cmd 自动下载，或设置 COSYVOICE_MODEL_DIR')
    return _result('model_files', '模型文件', Level.OK, '6 个文件齐全')


def check_cosyvoice(ctx: CheckContext) -> CheckResult:
    """CosyVoice 引擎是否在线。"""
    if ctx.cosyvoice is not None:
        payload = ctx.cosyvoice.health()
    else:
        payload = _probe_json(ctx.settings.cosyvoice_base, '/health')
    if payload is None:
        return _result('cosyvoice', '合成引擎', Level.FAIL, '引擎未启动',
                       '双击 启动-声刻.cmd 会自动拉起引擎')
    if 'sample_rate' not in payload:
        return _result('cosyvoice', '合成引擎', Level.FAIL, '端口 50000 被其他程序占用',
                       '关闭占用 50000 端口的程序后重启')
    return _result('cosyvoice', '合成引擎', Level.OK,
                   f"sample_rate={payload['sample_rate']}")


def check_emotion_service(ctx: CheckContext) -> CheckResult:
    """情绪服务是否加载完成。"""
    if ctx.emotion is not None:
        payload = ctx.emotion.health()
    else:
        payload = _probe_json(ctx.settings.emotion_base, '/health')
    if payload is None:
        return _result('emotion_service', '情绪服务', Level.WARN, '情绪服务不可用',
                       '运行 _run-emotion.cmd')
    if not payload.get('loaded'):
        return _result('emotion_service', '情绪服务', Level.WARN, '情绪服务加载中',
                       '等模型加载完成后再试')
    return _result('emotion_service', '情绪服务', Level.OK,
                   'model=' + str(payload.get('model', '?')))


def check_audio_formats(ctx: CheckContext) -> CheckResult:
    """libsndfile 支持的上传格式。"""
    try:
        import soundfile as sf  # pylint: disable=import-outside-toplevel
    except ImportError:
        return _result('audio_formats', '音频格式', Level.FAIL, '未安装 soundfile',
                       '在 app 目录执行 uv sync')
    available = sf.available_formats()
    missing = [name for name, _ in AUDIO_FORMATS if name not in available]
    if missing:
        return _result('audio_formats', '音频格式', Level.WARN,
                       '缺少格式: ' + ', '.join(missing),
                       '换用官方 pyinstaller 构建或重装 soundfile')
    return _result('audio_formats', '音频格式', Level.OK, 'MP3/FLAC/OGG 可用')


def check_voice_dir(ctx: CheckContext) -> CheckResult:
    """音色目录是否可写。"""
    if ctx.store is not None:
        writable = ctx.store.is_writable()
    else:
        try:
            probe_writable(ctx.settings.voice_dir)
            writable = True
        except OSError:
            writable = False
    if writable:
        return _result('voice_dir', '音色目录', Level.OK, ctx.settings.voice_dir)
    hint = '检查目录权限或 VS_VOICE_DIR'
    if not os.path.isdir(ctx.settings.voice_dir):
        hint = '运行 python -m voicesculptor.envcheck --fix 创建目录'
    return _result('voice_dir', '音色目录', Level.FAIL,
                   '不可写: ' + ctx.settings.voice_dir, hint)


def _scan_broken_voices(voice_dir: str) -> list[str]:
    """扫描有 meta.json 但缺 ref.wav 的音色目录。"""
    broken = []
    try:
        names = sorted(os.listdir(voice_dir))
    except OSError:
        return broken
    for name in names:
        if name.startswith('.'):
            continue
        directory = os.path.join(voice_dir, name)
        if not os.path.isdir(directory):
            continue
        has_meta = os.path.isfile(os.path.join(directory, 'meta.json'))
        has_ref = os.path.isfile(os.path.join(directory, 'ref.wav'))
        if has_meta and not has_ref:
            broken.append(name)
    return broken


def check_broken_voices(ctx: CheckContext) -> CheckResult:
    """存在 meta.json 但缺 ref.wav 的音色。"""
    if ctx.store is not None:
        broken = ctx.store.broken_voices()
    else:
        broken = _scan_broken_voices(ctx.settings.voice_dir)
    if not broken:
        return _result('broken_voices', '损坏音色', Level.OK, '无')
    return _result('broken_voices', '损坏音色', Level.WARN,
                   '损坏: ' + ', '.join(broken), '删除对应目录，或重新采集参考音频')


def check_seed_refs(ctx: CheckContext) -> CheckResult:
    """内置 6 段种子参考音频是否还在。"""
    missing = [name for name, path in SEED_FILES if not os.path.isfile(path)]
    if missing:
        return _result('seed_refs', '种子参考', Level.WARN,
                       '缺少: ' + ', '.join(missing), '恢复 runtime 目录后重启')
    return _result('seed_refs', '种子参考', Level.OK, '6 段齐全')


def check_disk_space(ctx: CheckContext) -> CheckResult:
    """仓库所在磁盘剩余空间。"""
    free = shutil.disk_usage(config.ROOT_DIR).free
    gib = free / GIB
    if free >= DISK_WARN_BYTES:
        return _result('disk_space', '磁盘空间', Level.OK, f'{gib:.1f} GiB 可用')
    if free >= DISK_FAIL_BYTES:
        return _result('disk_space', '磁盘空间', Level.WARN, f'{gib:.1f} GiB 可用',
                       '清理磁盘，至少保留 2 GiB')
    return _result('disk_space', '磁盘空间', Level.FAIL, f'仅 {gib:.1f} GiB 可用',
                   '清理磁盘后重试')


def check_proxy(ctx: CheckContext) -> CheckResult:
    """系统代理是否会拦截本地回环请求。"""
    configured = [key for key in PROXY_KEYS if os.environ.get(key)]
    if not configured:
        return _result('proxy', '代理', Level.OK, '未设置代理')
    no_proxy = (os.environ.get('NO_PROXY') or os.environ.get('no_proxy') or '')
    lowered = no_proxy.lower()
    if any(host in lowered for host in LOCAL_HOSTS):
        return _result('proxy', '代理', Level.OK, '代理已豁免本地地址')
    return _result('proxy', '代理', Level.WARN,
                   '已设置代理但未豁免 127.0.0.1（本机请求直连，下载仍走代理）',
                   '设置 NO_PROXY=127.0.0.1,localhost 可消除此提示')
