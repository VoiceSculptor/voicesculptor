"""WAV/PCM 工具：打包、拆包、时长与音频解码。"""

import io
import struct

import numpy as np
import soundfile as sf

from voicesculptor.errors import ValidationError

SAMPLE_RATE = 24000
DEFAULT_CHANNELS = 1
BITS_PER_SAMPLE = 16
HEADER_BYTES = 44


def wrap_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """把 16bit 单声道裸 PCM 包装成标准 WAV。"""
    return (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' +
            struct.pack('<IHHIIHH', 16, 1, DEFAULT_CHANNELS, sample_rate,
                        sample_rate * 2, 2, BITS_PER_SAMPLE) + b'data' +
            struct.pack('<I', len(pcm)) + pcm)


def pcm16_to_float(pcm: bytes) -> np.ndarray:
    """int16 PCM 转 -1~1 的 float32 波形。"""
    return np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0


def even_bytes(pcm: bytes) -> bytes:
    """截成偶数字节：奇数字节会让 np.frombuffer('<i2') 抛错。"""
    return pcm[:len(pcm) // 2 * 2]


def pcm_duration(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> float:
    """按 16bit 单声道换算 PCM 时长（秒）。"""
    return len(pcm) / 2.0 / float(sample_rate)


def decode_audio(data: bytes) -> tuple[np.ndarray, int]:
    """解码上传音频为单声道 float32 波形。

    参数:
        data: 音频文件字节（wav/mp3/flac/ogg）。

    返回:
        (波形, 采样率)。

    异常:
        ValidationError: 文件无法被 libsndfile 识别。
    """
    try:
        wave, sample_rate = sf.read(io.BytesIO(data), dtype='float32')
    except Exception as exc:  # noqa: BLE001 - 底层库异常类型不稳定
        raise ValidationError('无法识别的音频文件，请上传 wav/mp3/flac/ogg') from exc
    if wave.ndim > 1:
        wave = wave.mean(axis=1)
    return wave, int(sample_rate or 1)
