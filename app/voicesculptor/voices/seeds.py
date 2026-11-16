"""内置的 6 个情绪种子音色定义。"""

import os
import typing

from voicesculptor import config


class SeedVoice(typing.NamedTuple):
    """一个内置音色的静态定义。

    Attributes:
        vid: 音色 id，同时是 voices 下的目录名。
        name: 展示名称，也作为该参考音频的默认情绪。
        source_path: 内置参考音频的绝对路径。
        prompt: 参考音频的日文转录文本。
    """

    vid: str
    name: str
    source_path: str
    prompt: str


SEED_VOICES: tuple[SeedVoice, ...] = (
    SeedVoice(
        vid='coquettish',
        name='撒娇',
        source_path=os.path.join(config.ROXY_ORIG, 'coquettish.wav'),
        prompt='ルディ、ちょっと背中を貸してもらっていいですか',
    ),
    SeedVoice(
        vid='happy',
        name='开心',
        source_path=os.path.join(config.ROXY_ORIG, 'happy.wav'),
        prompt='はいそうですねルディ身長大きくなりましたね',
    ),
    SeedVoice(
        vid='sad',
        name='难过',
        source_path=os.path.join(config.ROXY_SEL, 'sad_v2.wav'),
        prompt='なるほど、これは鍛えがいがありそうですね',
    ),
    SeedVoice(
        vid='angry',
        name='生气',
        source_path=os.path.join(config.ROXY_ORIG, 'angry.wav'),
        prompt='もし妊娠でもしてしまったらどうする気なのですかまったく',
    ),
    SeedVoice(
        vid='calm',
        name='平静',
        source_path=os.path.join(config.ROXY_SEL, 'calm_v2.wav'),
        prompt='ルディなら自力で立ち直るって言ってましたけど',
    ),
    SeedVoice(
        vid='surprise',
        name='惊讶',
        source_path=os.path.join(config.ROXY_ORIG, 'surprise.wav'),
        prompt='えっと、ルーデオスさん、その、ありがとうございました',
    ),
)
