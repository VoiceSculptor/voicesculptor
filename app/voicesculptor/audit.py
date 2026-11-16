"""素材体检：逐个音频统计时长、采样率、声道、信噪比并给出结论。"""

import os

import numpy as np
import soundfile as sf

from voicesculptor.errors import StorageError

AUDIO_SUFFIXES = ('.wav', '.mp3', '.m4a', '.flac', '.ogg')
REPORT_NAME = 'audit-report.md'
FRAME_SECONDS = 0.02
MIN_FRAMES = 10
SNR_FLOOR = 0.0
SNR_CEIL = 60.0
MAX_TABLE_ROWS = 60


def _snr_db(wave: np.ndarray, frame: int) -> float:
    """用 10/90 分位能量比估计信噪比，夹在 0~60 dB。"""
    count = len(wave) // frame
    if count < MIN_FRAMES:
        return 0.0
    rms = np.array([
        float(np.sqrt(np.mean(wave[i * frame:(i + 1) * frame]**2)) + 1e-9)
        for i in range(count)
    ])
    noise = max(float(np.percentile(rms, 10)), 1e-6)
    speech = max(float(np.percentile(rms, 90)), noise)
    return max(SNR_FLOOR, min(SNR_CEIL, float(20 * np.log10(speech / noise))))


def _read_row(path: str, name: str) -> dict | None:
    """读取一个音频文件的统计行；解析失败返回 None。"""
    try:
        info = sf.info(path)
        duration = info.frames / float(info.samplerate)
        sample_rate, channels = info.samplerate, info.channels
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    snr = 0.0
    try:
        wave, _ = sf.read(path, dtype='float32')
        if wave.ndim > 1:
            wave = wave.mean(axis=1)
        snr = _snr_db(wave, max(1, int(sample_rate * FRAME_SECONDS)))
    except Exception:  # pylint: disable=broad-exception-caught
        snr = 0.0
    return {
        'file': name,
        'dur': round(duration, 2),
        'sr': sample_rate,
        'ch': channels,
        'snr': round(snr, 1),
    }


def _verdict(usable_min: float, median_snr: float) -> str:
    """按有效时长与中位信噪比给出结论。"""
    if usable_min >= 30 and median_snr >= 25:
        return '优秀：可直接做全量 SFT'
    if usable_min >= 10 and median_snr >= 15:
        return '良好：可做 LoRA 微调'
    if usable_min >= 3:
        return '及格：可做零样本 + 少量微调'
    return '不足：建议重录（目标 ≥ 10 分钟有效语音）'


def audit_folder(dir_path: str) -> tuple[str, dict]:
    """生成 markdown 体检报告与摘要。

    参数:
        dir_path: 待体检目录。

    返回:
        (markdown 报告, 摘要 dict)。

    异常:
        StorageError: 目录不可读。
    """
    rows = []
    try:
        names = sorted(os.listdir(dir_path))
    except OSError as exc:
        raise StorageError('无法读取目录: ' + str(exc)) from exc
    for name in names:
        if not name.lower().endswith(AUDIO_SUFFIXES):
            continue
        row = _read_row(os.path.join(dir_path, name), name)
        if row is not None:
            rows.append(row)

    total = sum(row['dur'] for row in rows)
    usable = sum(row['dur'] for row in rows if 2 <= row['dur'] <= 12)
    snrs = [row['snr'] for row in rows if row['snr'] > 0]
    median_snr = float(np.median(snrs)) if snrs else 0.0
    usable_min = usable / 60
    verdict = _verdict(usable_min, median_snr)

    sample_rates = '/'.join(sorted({str(row['sr']) for row in rows})) or '-'
    channels = '/'.join(sorted({str(row['ch']) for row in rows})) or '-'
    lines = [
        '# 素材体检报告',
        '',
        '| 项目 | 数值 |',
        '|---|---|',
        f'| 文件数 | {len(rows)} |',
        f'| 总时长 | {total / 60:.1f} 分钟 |',
        f'| 有效片段（2~12 秒） | {usable_min:.1f} 分钟 |',
        f'| 中位信噪比 | {median_snr:.1f} dB |',
        f'| 采样率/声道 | {sample_rates} / {channels} |',
        '',
        '**结论**：' + verdict,
        '',
        '| 文件 | 时长 | 采样率 | 声道 | SNR |',
        '|---|---|---|---|---|',
    ]
    for row in rows[:MAX_TABLE_ROWS]:
        lines.append(f"| {row['file']} | {row['dur']:.1f}s | {row['sr']} | "
                     f"{row['ch']} | {row['snr']:.1f}dB |")
    if len(rows) > MAX_TABLE_ROWS:
        lines.append(f'| …（其余 {len(rows) - MAX_TABLE_ROWS} 个文件省略） | | | | |')
    summary = {
        'files': len(rows),
        'total_min': round(total / 60, 1),
        'usable_min': round(usable_min, 1),
        'median_snr': round(median_snr, 1),
        'verdict': verdict,
    }
    return '\n'.join(lines), summary


def write_report(report: str, log_dir: str) -> str:
    """把报告写进日志目录，返回文件路径。

    异常:
        StorageError: 目录或文件不可写。
    """
    try:
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, REPORT_NAME)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(report)
    except OSError as exc:
        raise StorageError('报告写入失败: ' + str(exc)) from exc
    return path
