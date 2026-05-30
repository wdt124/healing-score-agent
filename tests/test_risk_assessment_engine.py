"""风险评估引擎集成测试"""
import pytest
from app.risk.assessment_engine import build_risk_assessment
from app.risk.risk_state_memory import _risk_state


def _assess(user_text: str, risk_level: str = "normal", persistent_score: float = 40.0,
            session_id: str = "test_engine_session"):
    return build_risk_assessment(
        user_text=user_text,
        risk_level=risk_level,
        persistent_score=persistent_score,
        evidence=[],
        session_id=session_id,
    )


@pytest.fixture(autouse=True)
def _clean_risk_state():
    """每个测试前清理共享风险状态，确保隔离"""
    _risk_state.clear("test_engine_session")
    yield


class TestLevelDetermination:
    """综合风险等级判定"""

    def test_method_and_time_is_critical(self):
        assessment = _assess("我今晚准备吃药")
        assert assessment.level == "critical"

    def test_suicide_and_method_is_critical(self):
        assessment = _assess("我想死了，准备了安眠药")
        assert assessment.level == "critical"

    def test_suicide_alone_is_high(self):
        assessment = _assess("我真的想死")
        assert assessment.level == "high"

    def test_cannot_stay_safe_is_high(self):
        assessment = _assess("我控制不住自己了")
        assert assessment.level == "high"

    def test_multiple_medium_signals_with_high_sds_is_high(self):
        assessment = _assess(
            "我绝望了，没人帮我，完全崩溃了",
            persistent_score=75.0,
        )
        assert assessment.level == "high"

    def test_medium_signals_with_medium_sds_is_medium(self):
        assessment = _assess(
            "我觉得没希望，没人关心我",
            persistent_score=65.0,
        )
        assert assessment.level == "medium"

    def test_negated_suicide_is_normal(self):
        assessment = _assess("我没有想自杀")
        # 否定后不应保持 high
        assert assessment.level == "normal"

    def test_normal_text_is_normal(self):
        assessment = _assess("今天天气不错", persistent_score=30.0)
        assert assessment.level == "normal"

    def test_low_sds_persists(self):
        assessment = _assess("最近有点累", persistent_score=55.0)
        assert assessment.level in ("normal", "low")

    def test_high_sds_no_signals_is_medium(self):
        assessment = _assess("每天都觉得没劲", persistent_score=76.0)
        assert assessment.level == "medium"


class TestRiskAssessmentOutput:
    """RiskAssessment 结构验证"""

    def test_has_required_fields(self):
        assessment = _assess("我想死")
        assert hasattr(assessment, "level")
        assert hasattr(assessment, "score")
        assert hasattr(assessment, "sds_score")
        assert hasattr(assessment, "confidence")
        assert hasattr(assessment, "signals")
        assert hasattr(assessment, "protective_factors")
        assert hasattr(assessment, "escalation_required")
        assert hasattr(assessment, "assessment_version")

    def test_signals_are_populated_for_risk(self):
        assessment = _assess("我想死")
        rule_signals = [s for s in assessment.signals if s.source == "rule"]
        assert len(rule_signals) > 0

    def test_escalation_for_high(self):
        assessment = _assess("我想死")
        assert assessment.escalation_required is True

    def test_no_escalation_for_normal(self):
        assessment = _assess("今天天气不错", persistent_score=30.0)
        assert assessment.escalation_required is False

    def test_protective_factors_detected(self):
        assessment = _assess("我很难过但是朋友一直在帮我")
        assert len(assessment.protective_factors) > 0

    def test_version_stamp(self):
        assessment = _assess("你好")
        assert assessment.assessment_version == "risk-assessment-v1"