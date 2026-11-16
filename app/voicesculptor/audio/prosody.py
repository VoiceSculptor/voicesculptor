"""韵律统计：音高起伏与能量起伏，用于 best 择优时判断情绪强弱。"""

import numpy as np
import torch
import torchaudio

from voicesculptor.audio.wav import pcm16_to_float
from voicesculptor.audio.wav import SAMPLE_RATE

FRAME = 240  # 10 ms @ 24 kHz
PITCH_LOW = 70
PITCH_HIGH = 500
RANGE_LO_PERCENT = 10
RANGE_HI_PERCENT = 90


def prosody(pcm: bytes) -> tuple[float, float]:
    """返回 (音高十分位差 Hz, 帧能量标准差)。"""
    wave = pcm16_to_float(pcm)
    try:
        tensor = torch.from_numpy(np.ascontiguousarray(wave)).unsqueeze(0)
        f0 = torchaudio.functional.detect_pitch_frequency(
            tensor, SAMPLE_RATE, freq_low=PITCH_LOW,
            freq_high=PITCH_HIGH).flatten().numpy()
        f0 = f0[(f0 > PITCH_LOW) & (f0 < PITCH_HIGH)]
        if len(f0):
            pitch_range = float(
                np.percentile(f0, RANGE_HI_PERCENT) -
                np.percentile(f0, RANGE_LO_PERCENT))
        else:
            pitch_range = 0.0
    except Exception:  # pylint: disable=broad-exception-caught
        pitch_range = 0.0
    usable = len(wave) // FRAME * FRAME
    if usable:
        frames = wave[:usable].reshape(-1, FRAME)
        energy = np.sqrt((frames**2).mean(axis=1))
    else:
        energy = np.zeros(1)
    return pitch_range, float(energy.std())


def zscore(values: list[float]) -> list[float]:
    """标准化到均值 0、标准差 1；全相同时返回 0 向量。"""
    mean = sum(values) / len(values)
    variance = sum((value - mean)**2 for value in values) / len(values)
    std = variance**0.5 or 1.0
    return [(value - mean) / std for value in values]
