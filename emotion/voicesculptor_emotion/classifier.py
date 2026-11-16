"""Emotion classification backed by FunASR emotion2vec.

The model is created lazily and guarded by a lock: FunASR inference is not
thread-safe, so only one ``generate`` call runs at a time.
"""

import logging
import os
import tempfile
import threading
from typing import Any, Callable

import numpy as np
import soundfile as sf
import torch
import torchaudio

from voicesculptor_emotion import config
from voicesculptor_emotion import labels

LOG = logging.getLogger(__name__)

# emotion2vec 只接受 16 kHz 输入，其他采样率先重采样。
SAMPLE_RATE = 16000

# 低于该 RMS（约 -50 dBFS）视为静音，不送模型。
SILENCE_RMS_DB = -50.0
SILENCE_RMS = 10**(SILENCE_RMS_DB / 20)


def default_model_factory(**kwargs: Any) -> Any:
    """Builds a FunASR ``AutoModel``.

    ``funasr`` is imported here rather than at module scope so that tests can
    inject a fake model without loading the real dependency.

    Args:
      **kwargs: Keyword arguments forwarded to ``funasr.AutoModel``.

    Returns:
      The model object created by FunASR.
    """
    from funasr import AutoModel  # pylint: disable=import-outside-toplevel
    return AutoModel(**kwargs)


class EmotionClassifier:
    """Thread-safe wrapper around one emotion2vec model.

    Args:
      settings: Service settings; when omitted they are read from the
        environment.
      model_factory: Callable that builds the model on first use. It defaults
        to FunASR ``AutoModel``; tests inject a fake to avoid the real model.
    """

    def __init__(self,
                 settings: config.Settings | None = None,
                 model_factory: Callable[..., Any] = default_model_factory):
        if settings is None:
            settings = config.Settings.from_env()
        self._settings = settings
        self._model_factory = model_factory
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        """Returns the configured FunASR model id."""
        return self._settings.model

    @property
    def device(self) -> str:
        """Returns the configured torch device string."""
        return self._settings.device

    def is_loaded(self) -> bool:
        """Reports whether the model has been created in this process."""
        return self._model is not None

    def load(self) -> None:
        """Creates the model if it does not exist yet.

        Concurrent callers block until the first model is ready, so a port
        that accepts connections always has a loaded model behind it.
        """
        with self._lock:
            self._model_locked()

    def _model_locked(self) -> Any:
        """Returns the model, building it on first use.

        Callers must hold ``self._lock``.

        Returns:
          The underlying FunASR model object.
        """
        if self._model is None:
            LOG.info('Loading emotion model %s on %s', self.model_name,
                     self.device)
            self._model = self._model_factory(
                model=self.model_name,
                hub='ms',
                device=self.device,
                disable_update=True,
            )
        return self._model

    def classify(self, wav: np.ndarray,
                 sr: int) -> tuple[str, dict[str, float]]:
        """Classifies one waveform.

        Args:
          wav: Audio samples; mono or shape ``(frames, channels)``.
          sr: Sample rate of ``wav``.

        Returns:
          The top English label and a mapping from English label to score.

        Raises:
          RuntimeError: Propagated from the model when inference fails.
        """
        samples = np.asarray(wav, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if sr != SAMPLE_RATE:
            tensor = torch.from_numpy(np.ascontiguousarray(samples))
            samples = torchaudio.functional.resample(tensor, sr,
                                                     SAMPLE_RATE).numpy()
        result = self._infer(samples)
        scores: dict[str, float] = {}
        for raw_label, score in zip(result['labels'], result['scores']):
            scores[labels.normalize_label(raw_label)] = round(float(score), 4)
        top = max(scores, key=scores.get)
        return top, scores

    def _infer(self, samples: np.ndarray) -> Any:
        """Runs the model on ``samples`` through a temporary 16 kHz wav file.

        Args:
          samples: Mono 16 kHz float32 samples.

        Returns:
          The first result entry produced by ``generate``.
        """
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp.close()
        try:
            sf.write(tmp.name, samples, SAMPLE_RATE)
            with self._lock:
                return self._model_locked().generate(
                    tmp.name,
                    granularity='utterance',
                    extract_embedding=False,
                )[0]
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass
