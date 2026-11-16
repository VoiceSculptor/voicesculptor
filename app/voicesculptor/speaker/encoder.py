"""CAM++ 说话人评测：声纹嵌入、缓存与余弦相似度。"""

import os
import threading

import numpy as np
import onnxruntime
import soundfile as sf
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi

from voicesculptor.audio import wav
from voicesculptor.errors import ModelUnavailableError

MODEL_FILE = 'campplus.onnx'
TARGET_SAMPLE_RATE = 16000
NUM_MEL_BINS = 80
EMBEDDING_CACHE_LIMIT = 64
SIMILARITY_EPSILON = 1e-9


class SpeakerEncoder:
    """懒加载的 CAM++ 声纹编码器。

    Args:
        model_dir: 模型目录，读取其中的 campplus.onnx。
    """

    def __init__(self, model_dir: str) -> None:
        self._model_dir = model_dir
        self._session = None
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, float], np.ndarray] = {}

    def is_available(self) -> bool:
        """模型文件是否存在。"""
        return os.path.isfile(os.path.join(self._model_dir, MODEL_FILE))

    def ensure_loaded(self) -> onnxruntime.InferenceSession:
        """返回已加载的 ONNX 会话，首次调用时初始化。

        Returns:
            onnxruntime.InferenceSession 实例。

        Raises:
            ModelUnavailableError: campplus.onnx 不存在。
        """
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            path = os.path.join(self._model_dir, MODEL_FILE)
            if not os.path.isfile(path):
                raise ModelUnavailableError('找不到评测模型: ' + path +
                                            '（请设置 COSYVOICE_MODEL_DIR）')
            options = onnxruntime.SessionOptions()
            options.graph_optimization_level = (
                onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL)
            self._session = onnxruntime.InferenceSession(
                path, sess_options=options, providers=['CPUExecutionProvider'])
        return self._session

    def embed_array(self, wave: np.ndarray, sample_rate: int) -> np.ndarray:
        """把一段波形编码成说话人向量。

        Args:
            wave: float32 波形，可以是多声道。
            sample_rate: 输入采样率，非 16 kHz 会自动重采样。

        Returns:
            一维 float32 声纹向量。
        """
        if wave.ndim > 1:
            wave = wave.mean(axis=1)
        tensor = torch.from_numpy(np.ascontiguousarray(
            wave, dtype=np.float32)).unsqueeze(0)
        if sample_rate != TARGET_SAMPLE_RATE:
            tensor = torchaudio.functional.resample(tensor, sample_rate,
                                                    TARGET_SAMPLE_RATE)
        features = kaldi.fbank(tensor,
                               num_mel_bins=NUM_MEL_BINS,
                               sample_frequency=TARGET_SAMPLE_RATE,
                               dither=0)
        features = features - features.mean(dim=0, keepdim=True)
        session = self.ensure_loaded()
        inputs = {session.get_inputs()[0].name: features.unsqueeze(0).numpy()}
        return session.run(None, inputs)[0].flatten()

    def embed_file(self, path: str) -> np.ndarray:
        """读取音频文件并编码成说话人向量。"""
        wave, sample_rate = sf.read(path, dtype='float32')
        return self.embed_array(wave, int(sample_rate))

    def embed_pcm(self, pcm: bytes) -> np.ndarray:
        """把 24 kHz 16bit 单声道 PCM 编码成说话人向量。"""
        return self.embed_array(wav.pcm16_to_float(pcm), wav.SAMPLE_RATE)

    def reference_embedding(self, path: str) -> np.ndarray:
        """参考音频的声纹向量，按 (路径, mtime) 缓存。"""
        key = (path, os.path.getmtime(path))
        embedding = self._cache.get(key)
        if embedding is None:
            embedding = self.embed_file(path)
            if len(self._cache) > EMBEDDING_CACHE_LIMIT:
                self._cache.clear()
            self._cache[key] = embedding
        return embedding

    def evict_dir(self, dir_path: str) -> None:
        """丢弃某个音色目录下所有参考音频的缓存。"""
        prefix = dir_path + os.sep
        for key in [item for item in self._cache if item[0].startswith(prefix)]:
            self._cache.pop(key, None)


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """两个向量的余弦相似度，范围约 -1~1。"""
    numerator = float(np.dot(left, right))
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return numerator / (denominator + SIMILARITY_EPSILON)
