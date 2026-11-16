"""情绪枚举、指令模板与择优方向。

这里是情绪相关常量的唯一来源，前端只是把 EMOTIONS 原样展示。
"""

EMOTIONS: tuple[str, ...] = ('撒娇', '开心', '难过', '生气', '平静', '惊讶')

DEFAULT_EMOTION = '平静'

EMOTION_INSTRUCT = {
    '撒娇': 'You are a helpful assistant. 请用非常可爱、撒娇的语气说一句话。',
    '开心': 'You are a helpful assistant. 请非常开心地说一句话。',
    '难过': 'You are a helpful assistant. 请非常伤心地说一句话。',
    '生气': 'You are a helpful assistant. 请非常生气地说一句话。',
    '平静': 'You are a helpful assistant. 请用平静、温柔的语气慢慢说一句话。',
    '惊讶': 'You are a helpful assistant. 请用非常惊讶、意外的语气说一句话。',
}

# 情绪参考音色 id 后缀：hybrid 模式据此给说话人缓存命名。
EMO_CODE = {
    '撒娇': 'coq',
    '开心': 'hap',
    '难过': 'sad',
    '生气': 'ang',
    '平静': 'cal',
    '惊讶': 'sur',
}

# 情绪强度的方向：+1 越大越有情绪，-1 越平稳越像。
AROUSAL = {'撒娇': 1, '开心': 1, '生气': 1, '惊讶': 1, '难过': -1, '平静': -1}
