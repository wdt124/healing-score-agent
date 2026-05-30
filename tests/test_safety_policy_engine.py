"""安全策略引擎测试"""
import pytest
from app.risk.schemas import RiskAssessment
from app.safety.policy_engine import decide_safety_policy


def _make_assessment(level: str) -> RiskAssessment:
    return RiskAssessment(
        level=level,
        score=50.0,
        sds_score=50.0,
        confidence=0.7,
        primary_drivers=["测试"],
        signals=[],
        protective_factors=[],
        escalation_required=level in ("high", "critical"),
    )


class TestLevelToModeMapping:
    """风险等级到安全模式的映射"""

    def test_normal_maps_to_normal_support(self):
        decision = decide_safety_policy(_make_assessment("normal"))
        assert decision.mode == "normal_support"

    def test_low_maps_to_supportive_checkin(self):
        decision = decide_safety_policy(_make_assessment("low"))
        assert decision.mode == "supportive_checkin"

    def test_medium_maps_to_safety_planning(self):
        decision = decide_safety_policy(_make_assessment("medium"))
        assert decision.mode == "safety_planning"

    def test_high_maps_to_crisis_intervention(self):
        decision = decide_safety_policy(_make_assessment("high"))
        assert decision.mode == "crisis_intervention"

    def test_critical_maps_to_emergency_escalation(self):
        decision = decide_safety_policy(_make_assessment("critical"))
        assert decision.mode == "emergency_escalation"

    def test_unknown_level_falls_back_to_normal_support(self):
        decision = decide_safety_policy(_make_assessment("unknown_xyz"))
        assert decision.mode == "normal_support"


class TestCrisisInterventionMode:
    """crisis_intervention 模式下的安全约束"""

    def test_forbids_light_reassurance(self):
        decision = decide_safety_policy(_make_assessment("high"))
        forbidden = " ".join(decision.forbidden_actions)
        assert "轻率安慰" in forbidden or "淡化风险" in forbidden

    def test_forbids_medical_diagnosis(self):
        decision = decide_safety_policy(_make_assessment("high"))
        forbidden = " ".join(decision.forbidden_actions)
        assert "医学诊断" in forbidden

    def test_forbids_ordinary_healing_talk(self):
        decision = decide_safety_policy(_make_assessment("high"))
        forbidden = " ".join(decision.forbidden_actions)
        assert "普通疗愈话术" in forbidden

    def test_requires_express_concern(self):
        decision = decide_safety_policy(_make_assessment("high"))
        required = " ".join(decision.required_actions)
        assert "关切" in required or "陪伴" in required

    def test_requires_suggest_real_support(self):
        decision = decide_safety_policy(_make_assessment("high"))
        required = " ".join(decision.required_actions)
        assert "热线" in required or "可信任" in required

    def test_offers_crisis_resources(self):
        decision = decide_safety_policy(_make_assessment("high"))
        assert len(decision.resources_to_offer) > 0

    def test_has_response_constraints(self):
        decision = decide_safety_policy(_make_assessment("high"))
        assert len(decision.response_constraints) > 0

    def test_audit_tags_include_high_risk(self):
        decision = decide_safety_policy(_make_assessment("high"))
        assert any("risk:high" in tag for tag in decision.audit_tags)
        assert any("safety:crisis" in tag for tag in decision.audit_tags)


class TestEmergencyEscalationMode:
    """emergency_escalation 模式"""

    def test_forbids_any_reassurance(self):
        decision = decide_safety_policy(_make_assessment("critical"))
        forbidden = " ".join(decision.forbidden_actions)
        assert "安抚" in forbidden or "拖延" in forbidden

    def test_requires_immediate_help(self):
        decision = decide_safety_policy(_make_assessment("critical"))
        required = " ".join(decision.required_actions)
        assert "紧急" in required

    def test_offers_emergency_numbers(self):
        decision = decide_safety_policy(_make_assessment("critical"))
        resources = " ".join(decision.resources_to_offer)
        assert "110" in resources or "120" in resources


class TestNormalSupportMode:
    """normal_support 模式"""

    def test_no_constraints_for_normal(self):
        decision = decide_safety_policy(_make_assessment("normal"))
        assert decision.required_actions == []
        assert decision.forbidden_actions == []

    def test_no_resources_for_normal(self):
        decision = decide_safety_policy(_make_assessment("normal"))
        assert decision.resources_to_offer == []


class TestSafetyDecisionStructure:
    """SafetyDecision 结构完整性"""

    def test_has_all_fields(self):
        decision = decide_safety_policy(_make_assessment("medium"))
        assert hasattr(decision, "mode")
        assert hasattr(decision, "required_actions")
        assert hasattr(decision, "forbidden_actions")
        assert hasattr(decision, "response_constraints")
        assert hasattr(decision, "resources_to_offer")
        assert hasattr(decision, "follow_up_questions")
        assert hasattr(decision, "audit_tags")


class TestSafetyPlanningMode:
    """safety_planning 模式"""

    def test_forbids_light_reassurance(self):
        decision = decide_safety_policy(_make_assessment("medium"))
        forbidden = " ".join(decision.forbidden_actions)
        assert "轻率安慰" in forbidden

    def test_encourages_real_support(self):
        decision = decide_safety_policy(_make_assessment("medium"))
        required = " ".join(decision.required_actions)
        assert "现实支持" in required or "可信任" in required