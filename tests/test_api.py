from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Healing Score Agent is running"}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _mock_score_result(risk_level_cn, score):
    return {
        "status": "success",
        "engine_used": "mock",
        "predicted_sds_score": score,
        "risk_level": risk_level_cn,
        "details": {
            "text_features_extracted": {},
            "audio_features_summary": "mock",
        },
    }


@patch("app.services.llm_service._call_llm", return_value="我理解你的感受，请多说说你最近的情况。")
@patch("app.services.scoring_service.score_text_and_audio")
def test_chat_message_low_risk(mock_score, mock_llm):
    mock_score.return_value = _mock_score_result("轻度", 55.0)

    payload = {"user_text": "我今天有点累，但还好", "session_id": "test-low-001"}
    response = client.post("/chat/message", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["risk_level"] == "low"
    assert data["score"] == 55


@patch("app.services.llm_service._call_llm", return_value="我能感受到你正在经历一段困难的时期。")
@patch("app.services.scoring_service.score_text_and_audio")
def test_chat_message_medium_risk(mock_score, mock_llm):
    mock_score.return_value = _mock_score_result("中度", 65.0)

    payload = {"user_text": "我最近很难过，感觉没有希望了", "session_id": "test-medium-001"}
    response = client.post("/chat/message", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["risk_level"] == "medium"
    assert data["score"] == 65


@patch("app.services.llm_service._call_llm", return_value="我很担心你，请拨打12356心理援助热线，有人可以帮你。")
@patch("app.services.scoring_service.score_text_and_audio")
def test_chat_message_high_risk(mock_score, mock_llm):
    mock_score.return_value = _mock_score_result("重度", 95.0)

    payload = {"user_text": "我觉得活着没意义，我不想活了", "session_id": "test-high-001"}
    response = client.post("/chat/message", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["risk_level"] == "high"
    assert data["score"] == 95