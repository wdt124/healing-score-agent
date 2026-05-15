
### 调用接口 run_pipeline

from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableLambda
from app.services.scoring_service import scoring_step
from app.services.llm_service import generate_supportive_reply
from app.services.memory_service import memory_step
from app.services.crisis_service import crisis_step
from app.core.config import settings


def _format_evidence(details: dict) -> list:
    evidence = []
    text_features = details.get("text_features_extracted", {})
    if text_features:
        feature_labels = {
            "anhedonia": "快感缺失", "depressed": "情绪低落", "sleep": "睡眠问题",
            "fatigue": "疲劳", "appetite": "食欲变化", "guilt": "内疚感",
            "concentrate": "注意力困难", "movement": "运动迟缓"
        }
        high_items = [(k, v) for k, v in sorted(text_features.items(), key=lambda x: x[1], reverse=True) if v >= 1]
        for k, v in high_items[:4]:
            evidence.append(f"{feature_labels.get(k, k)}: {v}/3分")

    audio_summary = details.get("audio_features_summary")
    if isinstance(audio_summary, dict):
        evidence.append(
            f"音频特征: 基频均值 {audio_summary.get('pitch_mean_hz', 'N/A')}Hz, "
            f"能量均值 {audio_summary.get('energy_mean', 'N/A')}"
        )

    return evidence if evidence else ["评估数据不足"]

reply_step = RunnableLambda(lambda x: {
    "reply": generate_supportive_reply(
        user_text=x["user_text"],
        risk_level=x["risk_level"],
        persistent_score=int(x["persistent_score"]),
        evidence=_format_evidence(x["score_result"]["details"]),
    ),
    "score_result": x["score_result"],
    "persistent_score": x["persistent_score"],
    "risk_level": x["risk_level"],
    "evidence": _format_evidence(x["score_result"]["details"]),
})

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
        "evidence": result.get("evidence", _format_evidence(score_res["details"])),
        "model_provider": settings.llm_provider,
        "model_name": settings.llm_model,
    }