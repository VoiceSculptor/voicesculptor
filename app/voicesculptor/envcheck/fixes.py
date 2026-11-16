"""环境修补：把检测到的问题尽量就地修好。

只做幂等、非破坏性的修复；需要联网下载大文件的动作默认只给出命令，
显式传入 download_models 才会真正开始下载。
"""

# 所有修复器统一签名，部分修复器不需要 ctx。
# pylint: disable=unused-argument

import dataclasses
import os
import shutil
import subprocess
import time

from voicesculptor import config
from voicesculptor.envcheck import checks

UV_TIMEOUT_SECONDS = 900
DOWNLOAD_TIMEOUT_SECONDS = 3600
BROKEN_DIR_NAME = '.broken'
MODEL_DOWNLOAD_HINT = ('运行 启动-声刻.cmd 自动下载（约 5.1 GB），'
                       '或加 --download-models')


@dataclasses.dataclass
class FixOutcome:
    """一次修复的结果。"""

    id: str
    title: str
    ok: bool
    message: str

    def to_dict(self) -> dict:
        """序列化成 JSON 友好的字典。"""
        return {
            'id': self.id,
            'title': self.title,
            'ok': self.ok,
            'message': self.message,
        }


def _outcome(item: checks.CheckResult, ok: bool, message: str) -> FixOutcome:
    """构造一条修复结果。"""
    return FixOutcome(item.id, item.title, ok, message)


def _find_uv() -> str:
    """定位 uv 可执行文件。"""
    return shutil.which('uv') or ''


def _run_command(argv: list[str], timeout: float) -> tuple[int, str]:
    """执行外部命令，返回 (退出码, 输出尾部)。"""
    try:
        completed = subprocess.run(argv,
                                   capture_output=True,
                                   text=True,
                                   timeout=timeout,
                                   check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    output = (completed.stdout or '') + (completed.stderr or '')
    return completed.returncode, output.strip()


def fix_voice_dir(ctx: checks.CheckContext,
                  item: checks.CheckResult) -> FixOutcome:
    """创建音色目录并确认可写。"""
    try:
        checks.probe_writable(ctx.settings.voice_dir, create=True)
    except OSError as exc:
        return _outcome(item, False, f'无法创建或写入：{exc}')
    return _outcome(item, True, '已创建并确认可写：' + ctx.settings.voice_dir)


def fix_broken_voices(ctx: checks.CheckContext,
                      item: checks.CheckResult) -> FixOutcome:
    """把损坏的音色目录移到 .broken/ 隔离，不直接删除。"""
    broken = checks._scan_broken_voices(  # pylint: disable=protected-access
        ctx.settings.voice_dir)
    if not broken:
        return _outcome(item, True, '没有需要隔离的音色')
    target_root = os.path.join(ctx.settings.voice_dir, BROKEN_DIR_NAME)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    moved = []
    try:
        os.makedirs(target_root, exist_ok=True)
        for name in broken:
            source = os.path.join(ctx.settings.voice_dir, name)
            target = os.path.join(target_root, f'{name}-{stamp}')
            os.replace(source, target)
            moved.append(name)
    except OSError as exc:
        return _outcome(item, False, f'隔离失败：{exc}')
    return _outcome(item, True, '已隔离到 .broken/：' + ', '.join(moved))


def fix_python(ctx: checks.CheckContext,
               item: checks.CheckResult) -> FixOutcome:
    """用 uv 安装 Python 3.11。"""
    uv = _find_uv()
    if not uv:
        return _outcome(item, False, '未找到 uv：winget install astral-sh.uv')
    code, output = _run_command([uv, 'python', 'install', '3.11'],
                                UV_TIMEOUT_SECONDS)
    if code != 0:
        return _outcome(item, False, 'uv python install 失败：' + output[-300:])
    return _outcome(item, True, '已安装 Python 3.11，请重新 uv sync 后重启')


def fix_packages(ctx: checks.CheckContext,
                 item: checks.CheckResult) -> FixOutcome:
    """在 app 项目里执行 uv sync。"""
    uv = _find_uv()
    if not uv:
        return _outcome(item, False, '未找到 uv：winget install astral-sh.uv')
    code, output = _run_command(
        [uv, 'sync', '--inexact', '--directory', config.APP_DIR],
        UV_TIMEOUT_SECONDS)
    if code != 0:
        return _outcome(item, False, 'uv sync 失败：' + output[-300:])
    return _outcome(item, True, '已执行 uv sync；依赖装在 app/.venv，请用它复检')


def fix_model_files(ctx: checks.CheckContext,
                    item: checks.CheckResult) -> FixOutcome:
    """缺模型文件时提示；加 --download-models 才真正下载。"""
    if not ctx.settings.model_dir:
        return _outcome(item, False, '未配置模型目录')
    return _outcome(item, False, MODEL_DOWNLOAD_HINT)


def download_models(ctx: checks.CheckContext,
                    item: checks.CheckResult) -> FixOutcome:
    """调用 download_models.py 下载缺失权重（约 5.1 GB）。"""
    uv = _find_uv()
    if not uv:
        return _outcome(item, False, '未找到 uv：winget install astral-sh.uv')
    script = os.path.join(config.ROOT_DIR, 'download_models.py')
    if not os.path.isfile(script):
        return _outcome(item, False, '缺少 download_models.py：' + script)
    code, output = _run_command([
        uv, 'run', '--no-project', '--python', '3.11', 'python', script,
        '--dest', ctx.settings.model_dir
    ], DOWNLOAD_TIMEOUT_SECONDS)
    if code != 0:
        return _outcome(item, False, '模型下载失败：' + output[-300:])
    return _outcome(item, True, '模型权重已下载到 ' + ctx.settings.model_dir)


FIXERS = {
    'python': fix_python,
    'packages': fix_packages,
    'torch_cuda': fix_packages,
    'model_files': fix_model_files,
    'audio_formats': fix_packages,
    'voice_dir': fix_voice_dir,
    'broken_voices': fix_broken_voices,
}


def apply(report,
          ctx: checks.CheckContext,
          download: bool = False) -> list[FixOutcome]:
    """按检测结果逐项修复；只处理有修复器的非 OK 项。

    多个检测项共用同一个修复器时只执行一次，避免重复 uv sync。
    """
    outcomes = []
    done = {}
    for item in report.checks:
        if item.level is checks.Level.OK:
            continue
        fixer = FIXERS.get(item.id)
        if fixer is None:
            continue
        if fixer in done:
            base = done[fixer]
            outcomes.append(
                FixOutcome(item.id, item.title, base.ok,
                           f'同 {base.id}：{base.message}'))
            continue
        if item.id == 'model_files' and download:
            outcome = download_models(ctx, item)
        else:
            outcome = fixer(ctx, item)
        done[fixer] = outcome
        outcomes.append(outcome)
    return outcomes
