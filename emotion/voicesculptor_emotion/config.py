"""Runtime settings for the emotion service."""

import dataclasses
import os

# 默认模型与设备；启动器或测试可用环境变量覆盖。
DEFAULT_MODEL = 'iic/emotion2vec_plus_large'
DEFAULT_DEVICE = 'cpu'


@dataclasses.dataclass(frozen=True)
class Settings:
    """Settings read from the process environment.

    Attributes:
      model: FunASR model id (or local directory) to load.
      device: Torch device used for inference, e.g. ``cuda`` or ``cpu``.
    """

    model: str = DEFAULT_MODEL

    device: str = DEFAULT_DEVICE

    @classmethod
    def from_env(cls) -> 'Settings':
        """Builds settings from ``EMOTION_MODEL`` and ``EMOTION_DEVICE``.

        Returns:
          A frozen ``Settings`` instance with environment overrides applied.
        """
        return cls(
            model=os.environ.get('EMOTION_MODEL', DEFAULT_MODEL),
            device=os.environ.get('EMOTION_DEVICE', DEFAULT_DEVICE),
        )
