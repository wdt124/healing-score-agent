### runnable组件 crisis_step

from langchain_core.runnables import RunnableLambda
from app.core.safety import detect_high_risk, detect_medium_risk


def _safety_and_level(inputs: dict) -> dict:
    user_text = inputs["user_text"]
    score = inputs["persistent_score"]

    if detect_high_risk(user_text):
        score = 95.0
    elif detect_medium_risk(user_text) and score < 60:
        score = 60.0

    if score >= 73:
        risk_level = "high"
    elif score >= 63:
        risk_level = "medium"
    elif score >= 53:
        risk_level = "low"
    else:
        risk_level = "normal"

    return {**inputs, "persistent_score": score, "risk_level": risk_level}


crisis_step = RunnableLambda(_safety_and_level)