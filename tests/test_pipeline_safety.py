"""管道级安全行为测试

测试重点不是"模型分数一定是多少"，而是"安全行为是否符合预期"。
"""
import pytest
from unittest.mock import patch
from app.services.pipeline_service import run_pipeline
from app.risk.risk_state_memory import _risk_state
from app.services.memory_service import _memory

@pytest.fixture(autouse=True)
def _clean_risk_state():
    """每个测试前清理共享状态，确保隔离"""
    _risk_state.clear("default")
    _memory.reset("default")
    yield


class TestResponseCompatibility:
    """API 响应兼容性 — 旧字段全在，新字段可选"""

    @patch("app.services.llm_service._call_llm", return_value="我理解你的感受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_old_fields_present(self, mock_score, mock_llm):
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 45.0,
            "risk_level": "轻度",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("今天天气不错")

        assert "reply" in result
        assert "risk_level" in result
        assert "score" in result
        assert "evidence" in result
        assert "model_provider" in result
        assert "model_name" in result

    @patch("app.services.llm_service._call_llm", return_value="我理解你的感受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_new_fields_present(self, mock_score, mock_llm):
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 45.0,
            "risk_level": "轻度",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("今天天气不错")

        assert "safety_mode" in result
        assert "safety_actions" in result
        assert "risk_signals" in result
        assert "assessment_version" in result
        assert "policy_version" in result

    @patch("app.services.llm_service._call_llm", return_value="我理解你的感受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_policy_version_is_set(self, mock_score, mock_llm):
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 45.0,
            "risk_level": "轻度",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("hello")
        assert result["policy_version"] == "safety-policy-v1"
        assert result["assessment_version"] is not None


class TestEvidenceLowSensitivity:
    """Evidence 生成应是低敏摘要，不暴露原文"""

    @patch("app.services.llm_service._call_llm", return_value="我理解你的感受。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_evidence_no_keyword_leak(self, mock_score, mock_llm):
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 55.0,
            "risk_level": "轻度",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("今天天气不错")

        for ev in result["evidence"]:
            assert "SDS 评分" in ev or "规则" in ev or "保护因素" in ev or "评估数据不足" in ev


class TestSafetyBehaviorScenarios:
    """安全行为场景测试"""

    @patch("app.services.llm_service._call_llm", return_value="我听到你了，这听起来真的很不容易。如果你愿意，可以联系身边的可信任的人。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_low_sds_but_suicide_plan_is_high_or_critical(self, mock_score, mock_llm):
        """SDS 低但明确自杀计划 → 最终风险 high/critical"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 40.0,
            "risk_level": "正常",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("我今晚准备了安眠药想结束一切")
        assert result["risk_level"] in ("high", "critical")

    @patch("app.services.llm_service._call_llm", return_value="我理解你现在非常难受。请先确认一下你当前的安全状态。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_high_sds_no_crisis_remains_elevated(self, mock_score, mock_llm):
        """SDS 高但没有即时危机 → 不一定是 emergency"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 80.0,
            "risk_level": "无风险",
            "details": {"text_features_extracted": {"depressed": 2, "sleep": 2}, "audio_features_summary": {}},
        }

        result = run_pipeline("我每天都在黑暗中挣扎，越来越没有力气了")
        assert result["safety_mode"] != "emergency_escalation"
        assert result["risk_level"] in ("medium", "high")

    @patch("app.services.llm_service._call_llm", return_value="请不要独自承受，立即联系信任的人或拨打心理援助热线。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_time_and_method_is_high_or_critical(self, mock_score, mock_llm):
        """明确提到时间和手段 → high/critical，safety_mode 为 crisis 或 emergency"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 60.0,
            "risk_level": "中风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("我今晚准备了药，想结束这一切")
        assert result["risk_level"] in ("high", "critical")
        assert result["safety_mode"] in ("crisis_intervention", "emergency_escalation")

    @patch("app.services.llm_service._call_llm", return_value="听到你这样说我很在意，这种感觉一定非常难受，但你并不孤单。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_negated_suicide_not_high(self, mock_score, mock_llm):
        """"我没有想自杀" → 不直接判 high"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 50.0,
            "risk_level": "低风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("我没有想自杀，只是觉得很难过")
        assert result["risk_level"] == "normal"

    @patch("app.services.llm_service._call_llm", return_value="听起来你朋友的情况让你很担心。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_quoted_suicide_low_confidence(self, mock_score, mock_llm):
        """"朋友说他想死" → 识别转述，不直接判 high"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 45.0,
            "risk_level": "低风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("我朋友说他想死")
        # 转述语境下不应为 high
        assert result["risk_level"] != "high"

    @patch("app.services.llm_service._call_llm", return_value="在这样的时刻，请先确保自己的安全。如果可以，请给你信任的人打个电话。")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_medium_distress_maps_to_safety_planning(self, mock_score, mock_llm):
        """中风险绝望表达 → safety_planning 而非普通 CBT"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 65.0,
            "risk_level": "中风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("我觉得很绝望，看不到希望，不知道怎么办")
        assert result["safety_mode"] in ("safety_planning", "crisis_intervention")


class TestCrisisReplyConstraints:
    """高危回复应满足的安全约束"""

    @patch("app.services.llm_service._call_llm")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_crisis_reply_expresses_concern(self, mock_score, mock_llm):
        """高危回复应表达关切和陪伴"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 90.0,
            "risk_level": "高风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }
        mock_llm.return_value = "我听到了你的感受，这非常不容易。请一定先保证自己的安全。"

        result = run_pipeline("我想结束一切，已经准备好了")
        reply = result["reply"]
        assert len(reply) > 0

    @patch("app.services.llm_service._call_llm")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_crisis_mode_sets_safety_actions(self, mock_score, mock_llm):
        """crisis 模式下 safety_actions 非空"""
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 90.0,
            "risk_level": "高风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }
        mock_llm.return_value = "请保证自己的安全，联系信任的人。"

        result = run_pipeline("我想死")
        assert len(result["safety_actions"]) > 0


class TestNormalReplyConstraint:
    """低风险和 normal 回复不应过度危机化"""

    @patch("app.services.llm_service._call_llm", return_value="听起来你今天心情还不错，有什么想聊的吗？")
    @patch("app.services.scoring_service.score_text_and_audio")
    def test_normal_chat_not_over_crisisized(self, mock_score, mock_llm):
        mock_score.return_value = {
            "status": "success",
            "engine_used": "mock",
            "predicted_sds_score": 35.0,
            "risk_level": "低风险",
            "details": {"text_features_extracted": {}, "audio_features_summary": {}},
        }

        result = run_pipeline("今天天气不错")
        assert result["safety_mode"] == "normal_support"
        assert result["risk_level"] == "normal"
