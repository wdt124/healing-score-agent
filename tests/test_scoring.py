import json
from app.services.scoring_service import score_text_and_audio


def test_score_text_only():
    """测试纯文本评分（不传音频），验证返回结构完整性。"""
    text = "我最近总是感到很悲伤，对什么都提不起兴趣，晚上也睡不好觉。"

    result = score_text_and_audio(text)

    print("返回结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 验证返回结构
    assert result["status"] == "success"
    assert "predicted_sds_score" in result
    assert "risk_level" in result
    assert "engine_used" in result
    assert "details" in result
    assert result["details"]["audio_features_summary"] == "No audio input detected"