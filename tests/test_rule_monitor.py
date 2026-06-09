"""规则监测引擎测试"""
import pytest
from app.risk.rule_monitor import scan_signals, scan_protective_factors, scan_all


class TestDirectHighRisk:
    """高危直接信号"""

    def test_suicide_ideation(self):
        signals = scan_signals("我想死")
        names = {s.name for s in signals}
        assert "suicide_ideation" in names

    def test_has_method_and_time(self):
        signals = scan_signals("我今晚准备吃药")
        names = {s.name for s in signals}
        assert "has_method" in names
        assert "has_time" in names

    def test_has_preparation(self):
        signals = scan_signals("我已经写好了遗书")
        names = {s.name for s in signals}
        assert "has_preparation" in names

    def test_cannot_stay_safe(self):
        signals = scan_signals("我控制不住自己")
        names = {s.name for s in signals}
        assert "cannot_stay_safe" in names

    def test_self_harm_ideation(self):
        signals = scan_signals("我想伤害自己")
        names = {s.name for s in signals}
        assert "self_harm_ideation" in names


class TestMediumAuxiliary:
    """中风险辅助信号"""

    def test_hopelessness(self):
        signals = scan_signals("我觉得没有希望了")
        names = {s.name for s in signals}
        assert "hopelessness" in names

    def test_burdensomeness(self):
        signals = scan_signals("我是大家的负担")
        names = {s.name for s in signals}
        assert "burdensomeness" in names

    def test_social_isolation(self):
        signals = scan_signals("没有人关心我")
        names = {s.name for s in signals}
        assert "social_isolation" in names

    def test_multiple_medium_signals(self):
        signals = scan_signals("我撑不下去了，没人能帮我")
        names = {s.name for s in signals}
        # 至少命中 hopelessness 和 social_isolation
        assert "hopelessness" in names
        assert "social_isolation" in names


class TestFalsePositiveReduction:
    """降低误报规则"""

    def test_negated_risk_context_flag(self):
        """否定表达的 suicide_ideation 应被标记 context_flag='negated_risk'"""
        result = scan_all("我没有想自杀")
        risk_signals = result["risk_signals"]
        # 否定语境下 suicide_ideation 应存在但带有 negated_risk 标记
        suicide_signals = [s for s in risk_signals if s.name == "suicide_ideation"]
        assert len(suicide_signals) >= 1
        for s in suicide_signals:
            assert s.metadata.get("context_flag") == "negated_risk", (
                f"否定表达应有 negated_risk 标记，"
                f"实际为 {s.metadata.get('context_flag')}"
            )
        assert result["context_flags"]["has_negation"] is True

    def test_quoted_or_reported(self):
        result = scan_all("我朋友说他想死")
        assert result["context_flags"]["has_quoted"] is True

    def test_hypothetical(self):
        result = scan_all("如果一个人想死怎么办")
        assert result["context_flags"]["has_hypothetical"] is True

    def test_past_resolved(self):
        result = scan_all("我以前想过自杀，但现在没有了")
        assert result["context_flags"]["has_past_resolved"] is True

    def test_negated_ideation_should_not_be_standalone_high(self):
        """否定表达不应直接判定为高危"""
        result = scan_all("我没有想自杀，只是觉得难过")
        assert result["context_flags"]["all_high_negated"] is True


class TestProtectiveFactors:
    """保护因素"""

    def test_has_support(self):
        signals = scan_protective_factors("我朋友一直在帮我")
        names = {s.name for s in signals}
        assert "has_support" in names

    def test_help_seeking(self):
        signals = scan_protective_factors("我想去看医生")
        names = {s.name for s in signals}
        assert "help_seeking" in names

    def test_future_orientation(self):
        signals = scan_protective_factors("为了家人我会坚持下去")
        names = {s.name for s in signals}
        assert "future_orientation" in names

    def test_coping_strategy(self):
        signals = scan_protective_factors("我会出去散步转移注意力")
        names = {s.name for s in signals}
        assert "coping_strategy" in names


class TestNormalText:
    """普通文本不应产生误报"""

    def test_casual_talk_no_false_positive(self):
        signals = scan_signals("今天天气真不错，心情挺好的")
        assert len(signals) == 0

    def test_mild_complaint_not_severe(self):
        signals = scan_signals("今天有点累，想休息一下")
        # "很累" 是旧关键词，但规则定义中不应误匹配
        names = {s.name for s in signals}
        assert "panic_or_breakdown" not in names
