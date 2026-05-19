from typing import List

HIGH_RISK_KEYWORDS: List[str] = [
    "不想活",
    "自杀",
    "结束生命",
    "活着没意义",
    "想死",
    "我想死",
    "不如死了",
    "死了算了",
    "杀了自己",
    "想结束一切",
    "一了百了",
    "没有存在感",
    "死掉也好",
    "我受够了",
]

MEDIUM_RISK_KEYWORDS: List[str] = [
    "失眠",
    "痛苦",
    "绝望",
    "难过",
    "没有希望",
    "撑不下去",
    "很累",
    "崩溃",
    "心累",
    "不开心",
    "烦躁",
    "孤独",
    "情绪低落",
    "无助",
    "没有动力",
    "压力大",
    "想放弃",
]

def detect_high_risk(user_text: str) -> bool:
    return any(keyword in user_text for keyword in HIGH_RISK_KEYWORDS)


def detect_medium_risk(user_text: str) -> bool:
    return any(keyword in user_text for keyword in MEDIUM_RISK_KEYWORDS)


def classify_risk(user_text: str) -> dict:
    if detect_high_risk(user_text):
        return {
            "risk_level": "high",
            "score": 90,
            "triggered_keywords": [
                keyword for keyword in HIGH_RISK_KEYWORDS if keyword in user_text
            ],
        }

    if detect_medium_risk(user_text):
        return {
            "risk_level": "medium",
            "score": 60,
            "triggered_keywords": [
                keyword for keyword in MEDIUM_RISK_KEYWORDS if keyword in user_text
            ],
        }

    return {
        "risk_level": "low",
        "score": 20,
        "triggered_keywords": [],
    }
