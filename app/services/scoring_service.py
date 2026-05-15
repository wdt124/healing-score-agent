
### runnable组件 scoring_step

import os
from typing import Optional
from app.models.scoring_engine import UnifiedDepressionEngine
from app.core.config import settings
from langchain_core.runnables import RunnableLambda

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
    result = _get_engine().predict(text=text, audio_path=audio_path)
    return result

scoring_step = RunnableLambda(lambda inputs: {
    "user_text": inputs["user_text"],
    "score_result": score_text_and_audio(
        text=inputs["user_text"],
        audio_path=inputs.get("audio_path"),
    ),
})