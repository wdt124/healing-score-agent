from unittest.mock import patch
from app.services.pipeline_service import run_pipeline


@patch("app.services.llm_service._call_ollama", return_value="我理解你的感受，请多说说你最近的情况。")
@patch("app.services.pipeline_service.score_text_and_audio")
def test_pipeline_returns_required_fields(mock_score, mock_ollama):
    mock_score.return_value = {
        "status": "success",
        "engine_used": "mock",
        "predicted_sds_score": 55.0,
        "risk_level": "轻度",
        "details": {
            "text_features_extracted": {"depressed": 2, "sleep": 1},
            "audio_features_summary": "mock",
        },
    }

    result = run_pipeline("我最近很难过，感觉没有希望了")

    assert "reply" in result
    assert "risk_level" in result
    assert "score" in result
    assert "evidence" in result
    assert "model_provider" in result
    assert "model_name" in result

    assert result["risk_level"] in ["low", "medium", "high"]
    assert isinstance(result["score"], (int, float))
    assert isinstance(result["evidence"], list)
    assert isinstance(result["reply"], str)
    assert isinstance(result["model_provider"], str)
    assert isinstance(result["model_name"], str)