"""风险规则定义

按四个优先级组织：
  direct_high_risk: 高危直接信号（明确意念、方法、准备行为等）
  medium_auxiliary: 中风险辅助信号（绝望/负担/孤立等）
  protective: 保护因素
  false_positive_context: 否定/转述/假设/过去已解决等上下文

原则：避免用“今晚”“准备了”“吃药”“刀”“绳子”等普通词单独触发危机等级。
时间和方法相关规则必须尽量使用具有明确危险语义的短语。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Rule:
    name: str
    category: str
    severity: float
    patterns: List[str] = field(default_factory=list)
    description: str = ""


DIRECT_HIGH_RISK_RULES: List[Rule] = [
    Rule(
        name="suicide_ideation",
        category="direct_high_risk",
        severity=0.95,
        patterns=[
            "想死", "不想活", "结束生命", "结束自己",
            "离开这个世界", "死了算了", "一了百了",
            "不想存在", "不如死了", "死掉算了",
            "活不下去", "不想活下去", "活着没意义",
            "想结束一切", "死掉也好", "自杀",
        ],
        description="明确的自杀意念表达",
    ),
    Rule(
        name="self_harm_ideation",
        category="direct_high_risk",
        severity=0.85,
        patterns=[
            "伤害自己", "自残", "割腕", "割自己",
            "划自己", "撞墙", "打自己",
        ],
        description="明确的自伤意念",
    ),
    Rule(
        name="has_method",
        category="direct_high_risk",
        severity=0.95,
        patterns=[
            "吃药自杀", "过量服药", "吞很多药",
            "从楼上跳下去", "想跳楼", "准备跳楼",
            "想跳河", "准备跳河", "想跳海", "准备跳海",
            "烧炭自杀", "准备烧炭", "上吊自杀", "准备上吊",
            "喝农药", "喝百草枯", "割腕自杀",
        ],
        description="提到明确的自杀方式或工具用途",
    ),
    Rule(
        name="has_time",
        category="direct_high_risk",
        severity=0.90,
        patterns=[
            "今晚就自杀", "今天就结束", "现在就去死",
            "马上去死", "今晚结束自己", "明天就自杀",
            "天亮之前结束", "今晚实施",
        ],
        description="提到明确的实施时间",
    ),
    Rule(
        name="has_preparation",
        category="direct_high_risk",
        severity=0.92,
        patterns=[
            "写遗书", "写了遗书", "告别信",
            "安排后事", "准备好自杀", "已经准备自杀",
            "把药都准备好了", "准备了自杀用的东西",
        ],
        description="已进行明确的危机准备行为",
    ),
    Rule(
        name="cannot_stay_safe",
        category="direct_high_risk",
        severity=0.88,
        patterns=[
            "控制不住自己", "怕自己会伤害自己", "不知道会做什么",
            "无法保证安全", "保证不了自己的安全", "可能会伤害自己",
            "不知道能控制多久",
        ],
        description="表示无法保证自身安全",
    ),
    Rule(
        name="harm_to_others",
        category="direct_high_risk",
        severity=0.90,
        patterns=[
            "想杀人", "同归于尽", "带他们一起死", "想伤害别人",
        ],
        description="有明确伤害他人的风险",
    ),
]


MEDIUM_AUXILIARY_RULES: List[Rule] = [
    Rule(
        name="hopelessness",
        category="medium_auxiliary",
        severity=0.55,
        patterns=[
            "没希望", "绝望", "没有希望", "看不到希望",
            "撑不下去", "熬不下去", "没有未来",
            "走投无路", "毫无希望", "前途渺茫",
        ],
        description="绝望感",
    ),
    Rule(
        name="burdensomeness",
        category="medium_auxiliary",
        severity=0.50,
        patterns=[
            "负担", "拖累", "累赘", "连累",
            "没有我会更好", "大家会轻松",
            "害了大家", "耽误了大家",
        ],
        description="自觉是他人负担",
    ),
    Rule(
        name="social_isolation",
        category="medium_auxiliary",
        severity=0.50,
        patterns=[
            "没有人", "没人关心", "没人能联系",
            "孤立", "孤单一人", "没人理解",
            "一个人扛", "没人帮我", "没人陪我",
            "没人能帮", "没人能",
        ],
        description="社交孤立感",
    ),
    Rule(
        name="severe_insomnia",
        category="medium_auxiliary",
        severity=0.45,
        patterns=[
            "彻夜失眠", "整晚没睡", "好几天没睡",
            "严重失眠", "完全睡不着", "失眠很久",
        ],
        description="严重失眠",
    ),
    Rule(
        name="functional_impairment",
        category="medium_auxiliary",
        severity=0.45,
        patterns=[
            "无法工作", "没法上班", "出不了门",
            "没法吃饭", "起不来床", "什么都做不了",
            "没法正常", "完全废了",
        ],
        description="功能严重受损",
    ),
    Rule(
        name="panic_or_breakdown",
        category="medium_auxiliary",
        severity=0.55,
        patterns=[
            "崩溃", "要疯了", "扛不住", "撑不住",
            "控制不住", "快要疯了", "快崩溃",
        ],
        description="濒临崩溃/失控",
    ),
]


PROTECTIVE_RULES: List[Rule] = [
    Rule(
        name="has_support",
        category="protective",
        severity=0.0,
        patterns=[
            "朋友帮", "家人支持", "有人陪", "身边有",
            "联系了朋友", "告诉了家人", "有人关心",
            "陪我", "支持我", "理解我的人",
            "在帮我", "帮了我",
        ],
        description="有现实支持系统",
    ),
    Rule(
        name="help_seeking",
        category="protective",
        severity=0.0,
        patterns=[
            "想求助", "找帮助", "看医生", "预约",
            "咨询", "想找人聊聊", "打算去",
        ],
        description="主动求助意愿",
    ),
    Rule(
        name="future_orientation",
        category="protective",
        severity=0.0,
        patterns=[
            "为了将来", "以后想", "还打算", "还有计划",
            "为了家人", "还有牵挂", "放不下",
        ],
        description="对未来仍有期待或牵挂",
    ),
    Rule(
        name="coping_strategy",
        category="protective",
        severity=0.0,
        patterns=[
            "运动会", "出去散步", "听音乐", "写日记",
            "深呼吸", "转移注意力", "让自己忙起来",
        ],
        description="有稳定自助方式",
    ),
]


CONTEXT_MARKERS = {
    "negated_risk": {
        "label": "发现否定表达，可能不是真实风险",
        "context_words": ["没有", "不是", "不会", "不想", "从未", "没想过", "从没想过", "并不"],
    },
    "quoted_or_reported": {
        "label": "发现转述/引用，可能是他人在描述而非自身经历",
        "context_words": ["我朋友说", "有人说", "听说", "据说", "他跟我说", "别人说"],
    },
    "hypothetical": {
        "label": "发现假设/条件表达，可能不是真实意图",
        "context_words": ["如果", "假如", "假设", "要是", "万一", "一个人要"],
    },
    "past_resolved": {
        "label": "提到过去经历但当前可能已解决",
        "context_words": ["以前", "曾经", "过去", "但现在", "不过现在", "已经好了", "已经过去了"],
    },
}


ALL_SIGNAL_RULES: List[Rule] = DIRECT_HIGH_RISK_RULES + MEDIUM_AUXILIARY_RULES
ALL_PROTECTIVE_RULES: List[Rule] = PROTECTIVE_RULES
