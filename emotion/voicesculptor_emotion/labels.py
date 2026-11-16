"""Emotion label helpers shared by the API and the classifier."""

from typing import Final

# emotion2vec_plus 9 类；只有前 5 类与 app 的 EMOTION_INSTRUCT 键对应，其余仅展示。
EN2CN: Final[dict[str, str]] = {
    'angry': '生气',
    'happy': '开心',
    'neutral': '平静',
    'sad': '难过',
    'surprised': '惊讶',
    'disgusted': '厌恶',
    'fearful': '恐惧',
    'other': '其他',
    'unknown': '未知',
}

# 模型可能返回的“无标签”记号，统一映射成 unknown。
_UNKNOWN_TOKENS = frozenset(('<unk>', 'unk', ''))


def normalize_label(label: object) -> str:
    """Normalizes a raw model label to a bare lowercase category.

    Args:
      label: Raw label emitted by FunASR, e.g. ``'生气/angry'`` or
        ``'<unk>'``.

    Returns:
      The lowercase category name; unknown tokens become ``'unknown'``.
    """
    text = str(label).rsplit('/', maxsplit=1)[-1].strip().lower()
    return 'unknown' if text in _UNKNOWN_TOKENS else text


def to_cn(label: str) -> str:
    """Returns the Chinese display name for ``label``.

    Args:
      label: Normalized English category name.

    Returns:
      The Chinese label, or ``label`` itself when it is unknown. ``None`` is
      never returned.
    """
    return EN2CN.get(label, label)
