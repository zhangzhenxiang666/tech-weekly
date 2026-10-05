"""Column extension points. Keep site layout out of content modules."""
from html import escape

NOTES = {
    'rust': '关注版本与生态变化。版本号、兼容性与实践建议应分别标注，发布消息以官方来源为准。',
    'github': '热度不是质量评分。周增与日增分开记录，保留抓取时间与统计口径。',
    'ai': '区分正式发布、预览与可用范围；价格和能力描述保留时间与核验边界。',
}
FIELDS = {
    'rust': {'version': '版本', 'compatibility': '兼容性'},
    'github': {'language': '语言', 'license': '许可证', 'stars_delta': 'Star 变化', 'metric_window': '统计窗口'},
    'ai': {'availability': '可用范围', 'pricing': '价格口径', 'verification': '核验状态'},
}

def note(module):
    return NOTES.get(module, '保留信息来源与时间，让每一期都可以回溯。')

def metadata(module, values):
    labels = FIELDS.get(module, {})
    return ''.join(f'<span>{escape(labels[k])}：{escape(str(v))}</span>' for k, v in values.items() if k in labels)
