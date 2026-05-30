"""趋势检测引擎测试"""
import pytest
import time
from app.risk.risk_state_memory import _risk_state, RiskObservation
from app.risk.trend_detector import detect_trends


def _feed_observations(session_id: str, rounds: list[dict]) -> None:
    """快捷方法：向 _risk_state 写入多轮观察"""
    _risk_state.clear(session_id)
    for r in rounds:
        _risk_state.add_observation(session_id, RiskObservation(
            session_id=session_id,
            timestamp=r.get("timestamp", time.time()),
            instant_sds_score=r.get("instant_sds_score", 50.0),
            persistent_sds_score=r.get("persistent_sds_score", 50.0),
            risk_level=r.get("risk_level", "normal"),
            safety_mode=r.get("safety_mode", ""),
            signal_names=r.get("signal_names", []),
            protective_names=r.get("protective_names", []),
            primary_drivers=r.get("primary_drivers", []),
        ))


class TestRapidWorsening:
    """趋势信号：快速恶化"""

    def test_three_rounds_continuous_score_increase(self):
        test_sess = "test_rapid_score"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 50.0, "risk_level": "low"},
            {"persistent_sds_score": 58.0, "risk_level": "low"},
            {"persistent_sds_score": 70.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "rapid_worsening" in names

        rapid = [s for s in signals if s.name == "rapid_worsening"][0]
        assert rapid.source == "trend"
        assert rapid.metadata["trend_type"] == "score_increase"
        _risk_state.clear(test_sess)

    def test_level_jump_from_low_to_high(self):
        test_sess = "test_rapid_jump"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 45.0, "risk_level": "low"},
            {"persistent_sds_score": 50.0, "risk_level": "low"},
            {"persistent_sds_score": 88.0, "risk_level": "high"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "rapid_worsening" in names
        _risk_state.clear(test_sess)

    def test_no_rapid_with_fewer_than_3_rounds(self):
        test_sess = "test_no_rapid_short"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 50.0, "risk_level": "low"},
            {"persistent_sds_score": 60.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "rapid_worsening" not in names
        _risk_state.clear(test_sess)


class TestRepeatedHighRisk:
    """趋势信号：反复高危"""

    def test_two_suicide_in_three_rounds(self):
        test_sess = "test_repeated_suicide"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 90.0, "risk_level": "high", "signal_names": ["suicide_ideation"]},
            {"persistent_sds_score": 50.0, "risk_level": "low", "signal_names": []},
            {"persistent_sds_score": 88.0, "risk_level": "high", "signal_names": ["suicide_ideation"]},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "repeated_high_risk_signal" in names

        s = [x for x in signals if x.name == "repeated_high_risk_signal"][0]
        assert s.metadata["count"] >= 2
        _risk_state.clear(test_sess)

    def test_three_hopelessness_in_five_rounds(self):
        test_sess = "test_repeated_hopeless"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 60.0, "risk_level": "medium", "signal_names": ["hopelessness"]},
            {"persistent_sds_score": 58.0, "risk_level": "low", "signal_names": ["hopelessness"]},
            {"persistent_sds_score": 62.0, "risk_level": "medium", "signal_names": ["hopelessness"]},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "repeated_high_risk_signal" in names
        _risk_state.clear(test_sess)

    def test_no_repeated_with_one_off_signal(self):
        test_sess = "test_no_repeat"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 90.0, "risk_level": "high", "signal_names": ["suicide_ideation"]},
            {"persistent_sds_score": 45.0, "risk_level": "low", "signal_names": []},
            {"persistent_sds_score": 50.0, "risk_level": "low", "signal_names": []},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "repeated_high_risk_signal" not in names
        _risk_state.clear(test_sess)


class TestSustainedElevatedRisk:
    """趋势信号：长期高位"""

    def test_three_consecutive_medium(self):
        test_sess = "test_sustained"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 65.0, "risk_level": "medium"},
            {"persistent_sds_score": 68.0, "risk_level": "medium"},
            {"persistent_sds_score": 70.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "sustained_elevated_risk" in names
        _risk_state.clear(test_sess)

    def test_three_consecutive_mixed_elevated(self):
        test_sess = "test_sustained_mixed"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 65.0, "risk_level": "medium"},
            {"persistent_sds_score": 80.0, "risk_level": "high"},
            {"persistent_sds_score": 75.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "sustained_elevated_risk" in names
        _risk_state.clear(test_sess)

    def test_interrupted_elevated_not_triggered(self):
        test_sess = "test_not_sustained"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 65.0, "risk_level": "medium"},
            {"persistent_sds_score": 50.0, "risk_level": "low"},
            {"persistent_sds_score": 68.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "sustained_elevated_risk" not in names
        _risk_state.clear(test_sess)

    def test_four_rounds_high_sds(self):
        test_sess = "test_sustained_sds"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 65.0, "risk_level": "medium"},
            {"persistent_sds_score": 68.0, "risk_level": "medium"},
            {"persistent_sds_score": 63.0, "risk_level": "medium"},
            {"persistent_sds_score": 70.0, "risk_level": "medium"},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "sustained_elevated_risk" in names
        _risk_state.clear(test_sess)


class TestProtectiveFactorDrop:
    """趋势信号：保护因素减少"""

    def test_support_dropped_then_isolation(self):
        test_sess = "test_protective_drop"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 50.0, "risk_level": "low",
             "protective_names": ["has_support"]},
            {"persistent_sds_score": 55.0, "risk_level": "medium",
             "protective_names": [],
             "signal_names": ["social_isolation"]},
            {"persistent_sds_score": 60.0, "risk_level": "medium",
             "protective_names": [],
             "signal_names": ["social_isolation"]},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "protective_factor_drop" in names
        _risk_state.clear(test_sess)

    def test_lost_help_seeking(self):
        test_sess = "test_help_seeking_drop"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 50.0, "risk_level": "low",
             "protective_names": ["help_seeking"]},
            {"persistent_sds_score": 55.0, "risk_level": "medium",
             "protective_names": []},
            {"persistent_sds_score": 60.0, "risk_level": "medium",
             "protective_names": []},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "protective_factor_drop" in names
        _risk_state.clear(test_sess)

    def test_no_drop_when_protective_stable(self):
        test_sess = "test_no_drop"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 50.0, "risk_level": "low",
             "protective_names": ["has_support"]},
            {"persistent_sds_score": 55.0, "risk_level": "medium",
             "protective_names": ["has_support"]},
            {"persistent_sds_score": 60.0, "risk_level": "medium",
             "protective_names": ["has_support"]},
        ])

        signals = detect_trends(test_sess)
        names = {s.name for s in signals}
        assert "protective_factor_drop" not in names
        _risk_state.clear(test_sess)


class TestTrendAwareAssessment:
    """趋势对风险评估等级的影响"""

    def test_sustained_elevated_keeps_medium_in_assessment(self):
        """验证：连续 medium 后，仅 SDS 正常不应立即降到 normal

        通过 integration test：构造连续 medium 历史，
        然后用一条看似正常的文本调用 build_risk_assessment，
        确认 sustained 信号会阻止降级。
        """
        from app.risk.assessment_engine import build_risk_assessment

        test_sess = "test_assess_sustained"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 65.0, "risk_level": "medium",
             "signal_names": ["hopelessness"]},
            {"persistent_sds_score": 68.0, "risk_level": "medium",
             "signal_names": ["hopelessness", "social_isolation"]},
            {"persistent_sds_score": 70.0, "risk_level": "medium",
             "signal_names": ["panic_or_breakdown"]},
        ])

        # 当前轮文本看起来"正常"，分数也低
        assessment = build_risk_assessment(
            user_text="今天还可以",
            risk_level="normal",
            persistent_score=50.0,
            evidence=[],
            session_id=test_sess,
        )

        # sustained 信号应至少保持 medium
        assert assessment.level in ("medium", "high"), (
            f"长期高位不应因单轮正常而降级，实际等级: {assessment.level}"
        )
        _risk_state.clear(test_sess)

    def test_high_then_low_not_immediate_normal(self):
        """验证：high 后下一轮分数低，不应立即降到 normal"""
        from app.risk.assessment_engine import build_risk_assessment

        test_sess = "test_high_then_low"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 88.0, "risk_level": "high",
             "signal_names": ["suicide_ideation"]},
        ])

        assessment = build_risk_assessment(
            user_text="我今天心情好多了",
            risk_level="low",
            persistent_score=50.0,
            evidence=[],
            session_id=test_sess,
        )

        assert assessment.level in ("medium", "high", "low"), (
            f"前轮高危应保留一定警惕性，实际等级: {assessment.level}"
        )
        _risk_state.clear(test_sess)

    def test_normal_conversation_no_false_trend(self):
        """普通多轮对话不应产生趋势误报"""
        from app.risk.assessment_engine import build_risk_assessment

        test_sess = "test_no_false_trend"
        _feed_observations(test_sess, [
            {"persistent_sds_score": 45.0, "risk_level": "normal"},
            {"persistent_sds_score": 48.0, "risk_level": "normal"},
            {"persistent_sds_score": 42.0, "risk_level": "normal"},
        ])

        assessment = build_risk_assessment(
            user_text="今天天气不错",
            risk_level="normal",
            persistent_score=50.0,
            evidence=[],
            session_id=test_sess,
        )

        assert assessment.level == "normal"
        # 不应出现趋势信号
        trend_signals = [s for s in assessment.signals if s.source == "trend"]
        assert len(trend_signals) == 0, f"普通对话不应产生趋势信号: {[s.name for s in trend_signals]}"
        _risk_state.clear(test_sess)