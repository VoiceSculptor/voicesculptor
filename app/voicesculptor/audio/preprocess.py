"""参考音频预处理：与 CosyVoice 官方 webui 的 postprocess 等价。

流程：去首尾静音（相对峰值 -50 dB，两端各留 0.1 s）-> 峰值归一化
-> 尾部补 0.2 s 静音。
"""

import numpy as np

TAIL_PAD_SECONDS = 0.2
SILENCE_DB = -50.0
FRAME_SECONDS = 0.025
HOP_SECONDS = 0.010
EDGE_PAD_SECONDS = 0.1
LOUD_PEAK = 0.8
QUIET_PEAK = 0.2
LOUD_TARGET = 0.8
QUIET_TARGET = 0.6


def _trim_silence(wave: np.ndarray, sample_rate: int) -> np.ndarray:
    """按帧能量裁掉相对峰值 -50 dB 以下的首尾静音。"""
    frame = max(1, int(sample_rate * FRAME_SECONDS))
    hop = max(1, int(sample_rate * HOP_SECONDS))
    if len(wave) <= frame:
        return wave
    count = 1 + (len(wave) - frame) // hop
    rms = np.array([
        np.sqrt(np.mean(wave[i * hop:i * hop + frame]**2)) for i in range(count)
    ])
    db = 20 * np.log10(rms + 1e-10)
    keep = np.where(db > db.max() + SILENCE_DB)[0]
    if keep.size == 0:
        return wave
    pad = int(sample_rate * EDGE_PAD_SECONDS)
    start = max(0, keep[0] * hop - pad)
    end = min(len(wave), keep[-1] * hop + frame + pad)
    return wave[start:end]


def _normalize_peak(wave: np.ndarray) -> np.ndarray:
    """过响压到 0.8，过轻抬到 0.6；其余保持不变。"""
    peak = float(np.abs(wave).max()) if len(wave) else 0.0
    if peak > LOUD_PEAK:
        return wave / peak * LOUD_TARGET
    if 0 < peak < QUIET_PEAK:
        return wave / peak * QUIET_TARGET
    return wave


def preprocess_reference(wave: np.ndarray, sample_rate: int) -> np.ndarray:
    """返回可直接写入 ref.wav 的 float32 波形。"""
    wave = np.asarray(wave, dtype=np.float32)
    wave = _trim_silence(wave, sample_rate)
    wave = _normalize_peak(wave)
    tail = np.zeros(int(sample_rate * TAIL_PAD_SECONDS), dtype=np.float32)
    return np.concatenate([wave, tail])
