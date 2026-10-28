"""Validated declarative organization-quality rules. No executable expressions."""
from copy import deepcopy

DEFAULT_RULES = {
    'weights': [30, 25, 20, 15, 10],
    'personal_weights': [45, 30, 25], 'personal_min_dimensions': 2, 'personal_maintenance_days': 30,
    'good_threshold': 80, 'fair_threshold': 60,
    'recent_days': 90, 'min_dimensions': 3, 'backup_count': 2,
    'completeness_threshold': 80, 'strength_weight': 50,
    'support_scores': {'反对': 0, '中立': 40, '支持': 75, '积极支持': 100},
    'templates': {
        '主管单位': [],
        '业主单位': ['定技术', '定标', '签验收', '批付款', '运营接管'],
        '设计单位': ['定技术', '需求提出', '影响者'],
        '总包单位': ['定技术', '采购经办', '签验收', '批付款'],
        '厂商': ['定技术', '采购经办', '签验收'],
    },
}
ROLES = ['定标', '定技术', '签验收', '批付款', '影响者', '需求提出', '采购经办', '运营接管', '安全评估协调']


def validate_rules(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_RULES):
        raise ValueError('请完整提交评估规则，不能包含未知字段')
    def integer(v, low, high, label):
        if type(v) is not int or not low <= v <= high:
            raise ValueError(f'{label}必须为 {low}–{high} 的整数')
    weights = value['weights']
    if not isinstance(weights, list) or len(weights) != 5:
        raise ValueError('请提供五项维度权重')
    for weight in weights:
        integer(weight, 0, 100, '权重')
    if sum(weights) != 100:
        raise ValueError('五项权重之和必须为 100')
    personal = value['personal_weights']
    if not isinstance(personal, list) or len(personal) != 3:
        raise ValueError('个人评估需提供三项权重')
    for weight in personal:
        integer(weight, 0, 100, '个人维度权重')
    if sum(personal) != 100:
        raise ValueError('个人评估权重之和必须为 100')
    integer(value['personal_min_dimensions'], 1, 3, '个人最低可评维度')
    integer(value['personal_maintenance_days'], 1, 365, '默认个人维系周期')
    if value['personal_min_dimensions'] > sum(w > 0 for w in personal):
        raise ValueError('个人最低可评维度不能超过个人启用维度数')
    for key, low, high, label in [
        ('good_threshold', 1, 100, '较好阈值'), ('fair_threshold', 0, 99, '一般阈值'),
        ('recent_days', 1, 365, '互动窗口'), ('min_dimensions', 1, 5, '最低可评维度'),
        ('backup_count', 2, 10, '主备人数'), ('completeness_threshold', 0, 100, '完整度提示线'),
        ('strength_weight', 0, 100, '关系强度占比'),
    ]:
        integer(value[key], low, high, label)
    if value['good_threshold'] <= value['fair_threshold']:
        raise ValueError('较好阈值必须大于一般阈值')
    if value['min_dimensions'] > sum(w > 0 for w in weights):
        raise ValueError('最低可评维度不能超过已启用维度数')
    scores = value['support_scores']
    if not isinstance(scores, dict) or set(scores) != set(DEFAULT_RULES['support_scores']):
        raise ValueError('请完整填写四类支持程度分值')
    ordered = [scores[k] for k in DEFAULT_RULES['support_scores']]
    for score in ordered:
        integer(score, 0, 100, '支持程度分值')
    if ordered != sorted(ordered):
        raise ValueError('支持程度分值应从反对到积极支持依次不降低')
    templates = value['templates']
    if not isinstance(templates, dict) or set(templates) != set(DEFAULT_RULES['templates']):
        raise ValueError('请完整提交五类组织的岗位模板')
    for roles in templates.values():
        if not isinstance(roles, list) or len(roles) > len(ROLES) or any(not isinstance(role, str) or role not in ROLES for role in roles) or len(set(roles)) != len(roles):
            raise ValueError('岗位模板包含重复或无效角色')
    return deepcopy(value)
