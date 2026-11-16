"""候选合成结果的评分与择优。"""

import dataclasses

from voicesculptor import emotions
from voicesculptor.audio import prosody

DEFAULT_RANK = -2.0
EXPRESSION_RANGE_WEIGHT = 0.6
EXPRESSION_RMS_WEIGHT = 0.4
SIMILARITY_WEIGHT = 0.3
EMOTION_MATCH_BONUS = 1.0
SIMILARITY_MARGIN = 0.05
SIMILARITY_PENALTY = -10.0


@dataclasses.dataclass
class Candidate:
    """一个候选音频及其评分依据。"""

    pcm: bytes
    sim: float | None
    expr: tuple[float, float]
    det: str | None
    rank: float = DEFAULT_RANK


def rank_candidates(candidates: list[Candidate], emotion: str,
                    use_emotion_rank: bool) -> Candidate:
    """按情绪唤醒度与声纹相似度打分，返回排名最高的候选。

    Args:
        candidates: 至少一个候选，按生成顺序排列。
        emotion: 目标情绪。
        use_emotion_rank: 是否启用情绪与相似度参与评分。

    Returns:
        分数最高的候选（其 rank 字段会被就地更新）。
    """
    if use_emotion_rank and emotion in emotions.AROUSAL:
        z_ranges = prosody.zscore([item.expr[0] for item in candidates])
        z_rms = prosody.zscore([item.expr[1] for item in candidates])
        z_sims = prosody.zscore(
            [0.0 if item.sim is None else item.sim for item in candidates])
        sign = emotions.AROUSAL[emotion]
        for index, item in enumerate(candidates):
            item.rank = sign * (EXPRESSION_RANGE_WEIGHT * z_ranges[index] +
                                EXPRESSION_RMS_WEIGHT * z_rms[index]
                               ) + SIMILARITY_WEIGHT * z_sims[index]
    else:
        for item in candidates:
            item.rank = DEFAULT_RANK if item.sim is None else item.sim
    if use_emotion_rank:
        sims = [item.sim for item in candidates if item.sim is not None]
        top = max(sims) if sims else 0.0
        for item in candidates:
            if item.det == emotion:
                item.rank += EMOTION_MATCH_BONUS
            if item.sim is not None and item.sim < top - SIMILARITY_MARGIN:
                item.rank += SIMILARITY_PENALTY
    return max(candidates, key=lambda item: item.rank)
