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
        "required_actions": ["准确承接用户主要困扰", "给出一个低风险的现实小步骤"],
        "forbidden_actions": ["只做空泛安慰", "急于诊断或贴标签"],
        "response_constraints": "通用心理支持。先承接主要情绪或处境，再根据内容选择稳定情绪、问题解决、行为激活、关系边界、责任修复、哀伤陪伴或现实求助中的一种策略。",
        "reference_modules": ["transdiagnostic-support"],
    },
    "supportive_checkin": {
        "required_actions": ["表达共情与支持", "识别用户当前最需要的帮助", "提供一个可执行的小步骤"],
        "forbidden_actions": ["淡化用户感受", "急于给出大量建议", "把所有问题归因于抑郁"],
        "response_constraints": "温和支持，但不要停在共情。结合用户内容选择一种微干预：稳定、问题解决、行为激活、认知澄清、关系边界、修复导向或现实支持。",
        "reference_modules": ["emotion-support", "transdiagnostic-support", "meditation-scripts"],
    },
    "safety_planning": {
        "required_actions": [
            "确认用户当前感受",
            "确认用户当前是否安全",
            "识别现实支持资源",
            "鼓励联系身边可信任的人",
            "必要时引导制定简短安全计划",
        ],
        "forbidden_actions": ["轻率安慰", "淡化风险", "给出医学诊断", "仅用风险等级替代个体化支持"],
        "response_constraints": "加入安全确认，引导用户关注现实支持资源；如有自伤或失控风险，围绕触发因素、应对策略、可联系的人和环境安全做简短安全计划。",
        "reference_modules": ["emotion-support", "transdiagnostic-support", "cbt-techniques"],
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
