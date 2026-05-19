
### 调用接口 run_pipeline

from typing import Dict, Any, Optional
from app.services.scoring_service import scoring_step
from app.services.memory_service import memory_step
from app.services.crisis_service import crisis_step
from app.services.llm_service import reply_step

### 管道
chain = (scoring_step
         | memory_step
         | crisis_step
         | reply_step)


def run_pipeline(
    user_text: str,
    audio_path: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    result: Dict[str, Any] = chain.invoke({
        "user_text": user_text,
        "audio_path": audio_path,
        "session_id": session_id or "default",
    })

    score_res: Dict[str, Any] = result["score_result"]

    return {
        "reply": result["reply"],
        "risk_level": result["risk_level"],
        "score": result.get("persistent_score", score_res["predicted_sds_score"]),
        "evidence": result.get("evidence", []),
        "model_provider": "deepseek",
        "model_name": "deepseek-chat",
    }