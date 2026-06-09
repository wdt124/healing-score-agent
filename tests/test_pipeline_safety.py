"""管道集成测试 — API 兼容性、安全行为、回复约束"""
import pytest
from unittest.mock import patch

from tests.conftest import make_score_result


class TestResponseCompatibility:
    """API 响应结构 — 旧字段兼容 + 新字段必在"""

    @patch("app.services.llm_service._call_llm", return_value="我理解你的感受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_all_response_fields_present(self, mock_score, _mock_llm):
        """验证响应的全部必需字段"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(45.0)

        result = run_pipeline("今天天气不错")

        assert result["reply"] == "我理解你的感受。"
        assert result["risk_level"] in ("normal", "low", "medium", "high", "critical")
        assert isinstance(result["score"], (int, float))
        assert isinstance(result["evidence"], list)
        assert result["safety_mode"] == "normal_support"
        assert result["safety_actions"] == []


class TestEvidenceLowSensitivity:
    """Evidence 是低敏摘要 — 不暴露原文或匹配关键词"""

    @patch("app.services.llm_service._call_llm", return_value="你好。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_evidence_contains_only_summary_terms(self, mock_score, _mock_llm):
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(55.0)

        result = run_pipeline("今天天气不错")

        for ev in result["evidence"]:
            assert any(keyword in ev for keyword in
                       ("SDS 评分", "规则", "保护因素", "评估数据不足"))


class TestSafetyBehaviorScenarios:
    """安全行为场景 — 验证风险判定不受 SDS 分数单独主导"""

    @patch("app.services.llm_service._call_llm", return_value="请先保证安全，联系信任的人。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_suicide_plan_overrides_low_sds(self, mock_score, _mock_llm):
        """低 SDS + 明确自杀计划 → high/critical"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(40.0)

        result = run_pipeline("我今晚准备了安眠药想结束一切")
        assert result["risk_level"] in ("high", "critical")

    @patch("app.services.llm_service._call_llm", return_value="我理解你现在非常难受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_high_sds_no_plan_not_emergency(self, mock_score, _mock_llm):
        """高 SDS 但无计划 → 不触发 emergency"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(80.0)

        result = run_pipeline("我每天都在黑暗中挣扎，越来越没有力气了")
        assert result["safety_mode"] != "emergency_escalation"
        assert result["risk_level"] in ("medium", "high")

    @patch("app.services.llm_service._call_llm", return_value="请立即联系信任的人或拨打心理援助热线。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_time_and_method_crisis(self, mock_score, _mock_llm):
        """时间 + 手段 → high+/crisis+"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(60.0)

        result = run_pipeline("我今晚准备了药，想结束这一切")
        assert result["risk_level"] in ("high", "critical")
        assert result["safety_mode"] in ("crisis_intervention", "emergency_escalation")

    @patch("app.services.llm_service._call_llm", return_value="听到你这样说我很在意。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_negated_suicide_normal(self, mock_score, _mock_llm):
        """"我没有想自杀" → 不判 high"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(50.0)

        result = run_pipeline("我没有想自杀，只是觉得很难过")
        assert result["risk_level"] == "normal"

    @patch("app.services.llm_service._call_llm", return_value="听起来你朋友的情况让你很担心。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_quoted_suicide_not_high(self, mock_score, _mock_llm):
        """"朋友说他想死" → 转述语境，不判 high"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(45.0)

        result = run_pipeline("我朋友说他想死")
        assert result["risk_level"] != "high"

    @patch("app.services.llm_service._call_llm", return_value="请先确保安全，给你信任的人打个电话。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_medium_distress_safety_planning(self, mock_score, _mock_llm):
        """中风险绝望 → safety_planning 及以上"""
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(65.0)

        result = run_pipeline("我觉得很绝望，看不到希望，不知道怎么办")
        assert result["safety_mode"] in ("safety_planning", "crisis_intervention")


class TestCrisisReplyConstraints:
    """高危回复的安全硬约束"""

    @patch("app.services.llm_service._call_llm")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_crisis_has_non_empty_safety_actions(self, mock_score, mock_llm):
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(90.0)
        mock_llm.return_value = "请保证自己的安全，联系信任的人。"

        result = run_pipeline("我想死")
        assert len(result["safety_actions"]) > 0

    @patch("app.services.llm_service._call_llm")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_crisis_reply_non_empty(self, mock_score, mock_llm):
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(90.0)
        mock_llm.return_value = "我听到了你的感受。请一定先保证安全。"

        result = run_pipeline("我想结束一切，已经准备好了")
        assert len(result["reply"]) > 0


class TestNormalNotOverCrisisized:
    """normal 输入不应被过度危机化"""

    @patch("app.services.llm_service._call_llm", return_value="听起来你今天心情还不错。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_normal_chat_normal_support(self, mock_score, _mock_llm):
        from app.services.pipeline_service import run_pipeline
        mock_score.return_value = make_score_result(35.0)

        result = run_pipeline("今天天气不错")
        assert result["safety_mode"] == "normal_support"
        assert result["risk_level"] == "normal"
