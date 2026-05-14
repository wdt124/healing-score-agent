import os
from typing import Optional
from app.models.scoring_engine import UnifiedDepressionEngine
from app.core.config import settings
from app.core.safety import detect_high_risk, detect_medium_risk

current_dir = os.path.dirname(os.path.abspath(__file__))
v1_path = os.path.abspath(os.path.join(current_dir, "..", "models", "eatd_rf_model_v1.joblib"))
v2_path = os.path.abspath(os.path.join(current_dir, "..", "models", "eatd_multimodal_rf_model_v2.joblib"))

_engine: Optional[UnifiedDepressionEngine] = None


def _get_engine() -> UnifiedDepressionEngine:
    global _engine
    if _engine is None:
        _engine = UnifiedDepressionEngine(
            v1_model_path=v1_path,
            v2_model_path=v2_path,
            api_key=settings.dashscope_api_key,
        )
    return _engine


def score_text_and_audio(text: str, audio_path: Optional[str] = None) -> dict:
    # 高危关键词硬拦截：命中直接返回高危，不经过ML模型
    if detect_high_risk(text):
        return {
            "status": "success",
            "engine_used": "Rule_Keyword_High_Risk",
            "predicted_sds_score": 95.0,
            "risk_level": "重度",
            "details": {
                "text_features_extracted": {},
                "audio_features_summary": "高危关键词硬拦截，跳过ML评分",
                "keyword_triggered": True,
            },
        }

    result = _get_engine().predict(text=text, audio_path=audio_path)

    # 中危关键词兜底：如果ML评分偏低但命中中危关键词，上浮至中度
    if detect_medium_risk(text) and result["predicted_sds_score"] < 60:
        result["predicted_sds_score"] = 60.0
        result["risk_level"] = "中度"
        result["details"]["keyword_escalated"] = True

    return result