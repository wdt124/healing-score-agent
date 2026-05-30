from typing import Dict, Any
from app.risk.schemas import RiskAssessment
from app.safety.schemas import SafetyDecision

LEVEL_TO_MODE: Dict[str, str] = {
    "normal": "normal_support",
    "low": "supportive_checkin",
    "medium": "safety_planning",
    "high": "crisis_intervention",
    "critical": "emergency_escalation",
}

MODE_POLICIES: Dict[str, dict] = {
    "normal_support": {
        "required_actions": [],
        "forbidden_actions": [],
        "response_constraints": "普通支持性交流，无特殊约束。",
        "resources_to_offer": [],
        "audit_tags": ["risk:normal"],
    },
    "supportive_checkin": {
        "required_actions": ["表达共情与支持"],
        "forbidden_actions": ["淡化用户感受", "急于给出建议"],
        "response_constraints": "温和支持，鼓励用户继续表达感受。",
        "resources_to_offer": [],
        "audit_tags": ["risk:low"],
    },
    "safety_planning": {
        "required_actions": [
            "确认用户当前感受",
            "提供现实支持建议",
            "鼓励联系身边可信任的人",
        ],
        "forbidden_actions": ["轻率安慰", "淡化风险", "给出医学诊断"],
        "response_constraints": "加入安全确认，引导用户关注现实支持资源。",
        "resources_to_offer": ["心理援助热线", "身边可信任的人"],
        "audit_tags": ["risk:medium", "safety:planning"],
    },
    "crisis_intervention": {
        "required_actions": [
            "优先表达关切和陪伴感",
            "明确建议联系现实中的可信任对象或心理援助热线",
        ],
        "forbidden_actions": [
            "做轻率安慰",
            "淡化风险",
            "给出医学诊断",
            "使用普通疗愈话术",
        ],
        "response_constraints": "优先安全确认，明确建议寻求现实帮助（热线/医疗资源），避免普通疗愈话术。",
        "resources_to_offer": [
            "全国24小时心理援助热线",
            "当地精神卫生中心",
            "紧急联系人",
        ],
        "audit_tags": ["risk:high", "safety:crisis", "escalation:recommended"],
    },
    "emergency_escalation": {
        "required_actions": [
            "强烈建议立即寻求紧急现实帮助",
            "提供明确的紧急联系方式",
        ],
        "forbidden_actions": [
            "做任何形式的安抚和拖延",
            "淡化危机的紧急性",
            "给出医学诊断",
        ],
        "response_constraints": "强烈建议立即寻求紧急现实帮助，明确给出热线和紧急联系方式。",
        "resources_to_offer": [
            "110 / 120 紧急服务",
            "全国24小时心理援助热线",
            "当地精神卫生中心急诊",
        ],
        "audit_tags": ["risk:critical", "safety:emergency", "escalation:immediate"],
    },
}


def decide_safety_policy(assessment: RiskAssessment) -> SafetyDecision:
    mode = LEVEL_TO_MODE.get(assessment.level, "normal_support")
    policy = MODE_POLICIES.get(mode, MODE_POLICIES["normal_support"])

    return SafetyDecision(
        mode=mode,
        required_actions=policy["required_actions"],
        forbidden_actions=policy["forbidden_actions"],
        response_constraints=policy["response_constraints"],
        resources_to_offer=policy["resources_to_offer"],
        audit_tags=policy["audit_tags"],
    )


def safety_policy_step_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
    assessment: RiskAssessment = inputs["risk_assessment"]
    decision = decide_safety_policy(assessment)
    return {**inputs, "safety_decision": decision}