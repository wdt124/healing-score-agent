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
        "reference_modules": [],
    },
    "supportive_checkin": {
        "required_actions": ["表达共情与支持"],
        "forbidden_actions": ["淡化用户感受", "急于给出建议"],
        "response_constraints": "温和支持，鼓励用户继续表达感受。",
        "reference_modules": ["emotion-support", "meditation-scripts"],
    },
    "safety_planning": {
        "required_actions": [
            "确认用户当前感受",
            "确认用户当前是否安全",
            "提供现实支持建议",
            "鼓励联系身边可信任的人",
        ],
        "forbidden_actions": ["轻率安慰", "淡化风险", "给出医学诊断"],
        "response_constraints": "加入安全确认，引导用户关注现实支持资源，确认当前安全状态。",
        "reference_modules": ["emotion-support", "cbt-techniques"],
    },
    "crisis_intervention": {
        "required_actions": [
            "优先表达关切和陪伴感",
            "明确建议联系现实中的可信任对象或心理援助热线",
            "回复中须包含至少一个热线号码（12356 或 400-161-9995）",
        ],
        "forbidden_actions": [
            "做轻率安慰",
            "淡化风险",
            "给出医学诊断",
            "使用普通疗愈话术",
        ],
        "response_constraints": "优先安全确认，明确建议寻求现实帮助（热线/医疗资源），回复中必须出现热线号码，避免普通疗愈话术。",
        "reference_modules": ["crisis-resources", "suicide-prevention"],
    },
    "emergency_escalation": {
        "required_actions": [
            "强烈建议立即寻求紧急现实帮助",
            "提供明确的紧急联系方式（120/110 或心理热线）",
            "建议联系身边可信任的人陪同",
        ],
        "forbidden_actions": [
            "做任何形式的安抚和拖延",
            "淡化危机的紧急性",
            "给出医学诊断",
        ],
        "response_constraints": "强烈建议立即拨打 120/110 或心理热线（12356），明确给出紧急联系方式，建议联系身边人陪同。",
        "reference_modules": ["crisis-resources", "suicide-prevention"],
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
        reference_modules=policy["reference_modules"],
    )


def safety_policy_step_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
    assessment: RiskAssessment = inputs["risk_assessment"]
    decision = decide_safety_policy(assessment)
    return {**inputs, "safety_decision": decision}
