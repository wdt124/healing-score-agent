import logging
import os
from typing import Optional

from langchain_core.runnables import RunnableLambda

from app.models.scoring_engine import UnifiedDepressionEngine

logger = logging.getLogger(__name__)

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
        )
    return _engine


def score_text_and_audio(text: str, audio_path: Optional[str] = None) -> dict:
    result = _get_engine().predict(text=text, audio_path=audio_path)
    logger.info("instance_score: %s", result["predicted_sds_score"])
    return result


def _score_step_fn(inputs: dict) -> dict:
    return {
        **inputs,
        "score_result": score_text_and_audio(
            text=inputs["user_text"],
            audio_path=inputs.get("audio_path"),
        ),
    }


scoring_step = RunnableLambda(_score_step_fn)
