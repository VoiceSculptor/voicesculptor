"""一次 TTS 请求的完整编排：排队、合成、重试与择优。"""

import base64
import dataclasses
import logging
import threading
import time

from voicesculptor.audio import prosody
from voicesculptor.audio import wav
from voicesculptor.clients.cosyvoice import CosyVoiceClient
from voicesculptor.clients.emotion import EmotionClient
from voicesculptor.config import Settings
from voicesculptor.errors import BusyError
from voicesculptor.errors import EngineEmptyError
from voicesculptor.errors import EngineUnavailableError
from voicesculptor.errors import ModelUnavailableError
from voicesculptor.errors import VoiceSculptorError
from voicesculptor.speaker.encoder import cosine_similarity
from voicesculptor.speaker.encoder import SpeakerEncoder
from voicesculptor.synthesis import planner
from voicesculptor.synthesis.ranking import Candidate
from voicesculptor.synthesis.ranking import rank_candidates
from voicesculptor.synthesis.request import TtsRequest
from voicesculptor.voices.store import VoiceStore

LOG = logging.getLogger(__name__)

MIN_PCM_BYTES = 2400
MAX_CANDIDATES = 4
LENGTH_RETRIES = 2
CHARS_PER_SECOND = 5.8
MIN_EXPECTED_SECONDS = 0.8
SHORT_RATIO = 0.55
LONG_RATIO = 2.5
REFERENCE_KINDS = ('zero_shot', 'cross_lingual')


class SynthesisPipeline:
    """把一次 TtsRequest 跑成最终的音频与诊断信息。

    实例持有并发信号量，整个进程只应构造一次并复用。

    Args:
        settings: 当前配置。
        store: 音色库。
        encoder: 声纹编码器。
        cosyvoice: 引擎客户端。
        emotion_client: 情绪服务客户端。
    """

    def __init__(self, settings: Settings, store: VoiceStore,
                 encoder: SpeakerEncoder, cosyvoice: CosyVoiceClient,
                 emotion_client: EmotionClient) -> None:
        self._settings = settings
        self._store = store
        self._encoder = encoder
        self._cosyvoice = cosyvoice
        self._emotion_client = emotion_client
        self._gate = threading.BoundedSemaphore(max(1,
                                                    settings.tts_concurrency))

    def run(self, request: TtsRequest) -> dict:
        """执行一次完整合成并返回 JSON 友好的结果字典。

        Raises:
            BusyError: 排队超时。
            VoiceNotFoundError: 音色不存在或参考音频丢失。
            ValidationError: 计划阶段的参数问题（如 split 缺音色）。
            ModelUnavailableError: 评测模型缺失或加载失败。
            EngineEmptyError: 引擎返回空音频。
            EngineUnavailableError: 引擎不可用或超出单请求合成次数。
        """
        if not self._gate.acquire(timeout=self._settings.tts_queue_timeout):
            raise BusyError('合成繁忙：前面还有任务在排队，请稍后重试')
        try:
            return self._run(request)
        finally:
            self._gate.release()

    def _run(self, request: TtsRequest) -> dict:
        """在拿到信号量之后执行规划、合成与择优。"""
        meta, ref_path = self._store.resolve(request.voice_id)
        self._encoder.ensure_loaded()
        plan = planner.make_plan(request, meta, ref_path, self._store)
        warnings: list[str] = []
        calls = [0]
        started = time.time()
        pcm, plan = self._first_audio(plan, request, calls, warnings)
        pcms, requested = self._build_candidates(plan, request, pcm, calls)
        candidates, use_emotion_rank = self._score_candidates(
            pcms, plan, request, warnings)
        best = rank_candidates(candidates, request.emotion, use_emotion_rank)
        if len(best.pcm) < MIN_PCM_BYTES:
            raise EngineEmptyError('合成失败：引擎返回空音频')
        final_wav = wav.wrap_wav(best.pcm)
        detected = best.det if use_emotion_rank else None
        scores = best.scores if use_emotion_rank else None
        if request.verify and not use_emotion_rank:
            detected, scores = self._verify_final(final_wav, warnings)
        return self._response(best, final_wav, plan, request, requested,
                              len(candidates), use_emotion_rank, detected,
                              scores, warnings, started)

    def _response(self, best: Candidate, final_wav: bytes,
                  plan: planner.SynthesisPlan, request: TtsRequest,
                  requested: int, total: int, use_emotion_rank: bool,
                  detected: str | None, scores: dict | None,
                  warnings: list[str], started: float) -> dict:
        """组装最终响应。"""
        return {
            'audio_base64': base64.b64encode(final_wav).decode('ascii'),
            'sim': None if best.sim is None else round(best.sim, 3),
            'duration': round(wav.pcm_duration(best.pcm), 2),
            'latency': round(time.time() - started, 2),
            'engine': 'cosyvoice',
            'mode': plan.kind,
            'ref_voice': str(plan.ref_meta.get('voice_id') or ''),
            'emo_voice': request.emo_voice_id if plan.kind == 'split' else None,
            'emotion_target': request.emotion,
            'emotion_detected': detected,
            'emotion_rank': use_emotion_rank,
            'candidates': total,
            'candidates_requested': requested,
            'emotion_scores': scores,
            'warnings': warnings,
        }

    def _first_audio(
            self, plan: planner.SynthesisPlan, request: TtsRequest,
            calls: list[int],
            warnings: list[str]) -> tuple[bytes, planner.SynthesisPlan]:
        """合成第一段音频，并做时长重试与情绪回退。"""
        try:
            pcm = self._synthesize(plan, request, calls)
        except EngineEmptyError as exc:
            raise EngineEmptyError('合成失败：' + str(exc)) from exc
        except VoiceSculptorError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOG.exception('首次合成失败')
            raise EngineUnavailableError('合成失败: ' + str(exc)) from exc
        expected = self._expected_duration(request)
        retried = False
        attempts = 0
        while (attempts < LENGTH_RETRIES and
               self._duration_bad(pcm, expected) and
               self._can_synthesize(calls)):
            attempts += 1
            candidate = self._try_synth(plan, request, calls, '时长重试失败')
            if candidate is None:
                break
            retried = True
            if self._badness(candidate,
                             expected) < self._badness(pcm, expected):
                pcm = candidate
        if retried:
            warnings.append('合成音频时长异常，已重试')
        if (plan.kind in REFERENCE_KINDS and plan.emotion_prompt and
                wav.pcm_duration(pcm) < expected * SHORT_RATIO and
                self._can_synthesize(calls)):
            fallback = dataclasses.replace(plan,
                                           kind='instruct2',
                                           instruct=plan.emotion_prompt)
            candidate = self._try_synth(fallback, request, calls, '情绪回退合成失败')
            if candidate is not None and len(candidate) > len(pcm):
                pcm = candidate
                plan = fallback
                warnings.append('已回退到 instruct2 模式')
        return pcm, plan

    def _build_candidates(self, plan: planner.SynthesisPlan,
                          request: TtsRequest, first: bytes,
                          calls: list[int]) -> tuple[list[bytes], int]:
        """补齐 best 模式需要的候选数量。"""
        requested = 1
        if request.quality == 'best':
            requested = max(1, min(MAX_CANDIDATES, request.best_n))
        pcms = [first]
        while len(pcms) < requested:
            candidate = self._try_synth(plan, request, calls, '候选生成失败')
            if candidate is None:
                break
            pcms.append(candidate)
        return pcms, requested

    def _score_candidates(self, pcms: list[bytes], plan: planner.SynthesisPlan,
                          request: TtsRequest,
                          warnings: list[str]) -> tuple[list[Candidate], bool]:
        """计算相似度、情绪与韵律，得到可排序的候选。"""
        reference = None
        if request.quality == 'best' or request.verify:
            reference = self._reference_embedding(plan.ref_path)
        use_emotion_rank = (request.verify and self._settings.emotion_rank and
                            len(pcms) > 1)
        candidates = []
        emotion_down = False
        for pcm in pcms:
            sim = None
            if reference is not None:
                try:
                    sim = cosine_similarity(self._encoder.embed_pcm(pcm),
                                            reference)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    LOG.warning('相似度计算失败: %s', exc)
                    warnings.append('相似度计算失败: ' + str(exc))
            det = None
            scores = None
            if use_emotion_rank:
                det, scores = self._detect(pcm)
                if det is None:
                    emotion_down = True
            candidates.append(
                Candidate(pcm=pcm,
                          sim=sim,
                          expr=prosody.prosody(pcm),
                          det=det,
                          scores=scores))
        if emotion_down:
            warnings.append('情绪服务不可用，已跳过情绪择优')
        return candidates, use_emotion_rank

    def _detect(self, pcm: bytes) -> tuple[str | None, dict | None]:
        """识别单段候选的情绪标签与分数；失败时返回 (None, None)。"""
        try:
            payload = self._emotion_client.classify(wav.wrap_wav(pcm))
        except VoiceSculptorError as exc:
            LOG.info('情绪识别失败: %s', exc)
            return None, None
        detected = payload.get('cn')
        scores = payload.get('cn_scores')
        if not isinstance(scores, dict) or not scores:
            scores = None
        return (str(detected) if detected else None), scores

    def _verify_final(self, final_wav: bytes,
                      warnings: list[str]) -> tuple[str | None, dict | None]:
        """对最终音频做一次情绪识别，用于校验与展示分数。"""
        try:
            payload = self._emotion_client.classify(final_wav)
        except VoiceSculptorError as exc:
            warnings.append('情绪服务不可用: ' + str(exc))
            return None, None
        detected = payload.get('cn')
        scores = payload.get('cn_scores')
        if not isinstance(scores, dict) or not scores:
            scores = None
        return (str(detected) if detected else None), scores

    def _reference_embedding(self, ref_path: str):
        """参考音频的声纹向量，失败时统一转成评测模型错误。"""
        try:
            return self._encoder.reference_embedding(ref_path)
        except ModelUnavailableError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise ModelUnavailableError('评测模型加载失败: ' + str(exc)) from exc

    def _synthesize(self, plan: planner.SynthesisPlan, request: TtsRequest,
                    calls: list[int]) -> bytes:
        """调用引擎一次，并检查空音频与单请求次数上限。"""
        limit = self._settings.max_synth_per_req
        if calls[0] >= limit:
            raise EngineUnavailableError(f'已达单请求合成次数上限 {limit}')
        calls[0] += 1
        pcm = wav.even_bytes(
            self._cosyvoice.synthesize(plan.kind, plan.ref_path, plan.prompt,
                                       request.text, plan.instruct,
                                       request.speed, plan.emo_ref,
                                       plan.emo_prompt))
        if len(pcm) < MIN_PCM_BYTES:
            raise EngineEmptyError(f'引擎返回空音频（{len(pcm)} 字节）')
        return pcm

    def _try_synth(self, plan: planner.SynthesisPlan, request: TtsRequest,
                   calls: list[int], message: str) -> bytes | None:
        """尽力合成一次，失败只记日志并返回 None。"""
        try:
            return self._synthesize(plan, request, calls)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOG.warning('%s: %s', message, exc)
            return None

    def _can_synthesize(self, calls: list[int]) -> bool:
        """单请求合成次数是否还有余量。"""
        return calls[0] < self._settings.max_synth_per_req

    @staticmethod
    def _expected_duration(request: TtsRequest) -> float:
        """按每秒 5.8 字估算期望时长（秒）。"""
        return max(MIN_EXPECTED_SECONDS,
                   len(request.text.strip()) / CHARS_PER_SECOND)

    @classmethod
    def _duration_bad(cls, pcm: bytes, expected: float) -> bool:
        """时长是否偏离期望超过 55%~250%。"""
        duration = wav.pcm_duration(pcm)
        return (duration < expected * SHORT_RATIO or
                duration > expected * LONG_RATIO)

    @classmethod
    def _badness(cls, pcm: bytes, expected: float) -> float:
        """时长与期望的相对偏差，越小越接近。"""
        return abs(wav.pcm_duration(pcm) - expected) / expected
