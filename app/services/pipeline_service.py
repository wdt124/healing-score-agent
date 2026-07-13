from typing import Dict, Any, Optional, List, Tuple
import time

from langchain_core.runnables import RunnableLambda

from app.core.config import settings
from app.models.schemas import RiskSignalBrief
from app.risk.assessment_engine import risk_assessment_step_fn
from app.risk.audit import write_audit_record
from app.risk.risk_state_memory import _risk_state, RiskObservation
from app.risk.thresholds import SDS_THRESHOLDS
from app.safety.policy_engine import safety_policy_step_fn
from app.services.llm_service import reply_step
from app.services.memory_service import memory_step
from app.services.scoring_service import scoring_step

risk_assessment_step = RunnableLambda(risk_assessment_step_fn)
safety_policy_step = RunnableLambda(safety_policy_step_fn)

chain = scoring_step | memory_step | risk_assessment_step | safety_policy_step | reply_step


QUOTE_CURRENT_MARKER = "\n\n[用户当前输入]\n"


def _split_analysis_and_reply_text(raw_text: str) -> Tuple[str, str]:
    """将旧前端拼接的引用格式拆开。

    scoring/risk 只分析当前用户输入；reply 仍能看到引用上下文。
    这样引用到含有“自杀/今晚/吃药”等词的旧消息时，不会被误判成当前意图。
    """
    text = str(raw_text or "").strip()
    if text.startswith("[引用") and QUOTE_CURRENT_MARKER in text:
        _, current_text = text.split(QUOTE_CURRENT_MARKER, 1)
        current_text = current_text.strip()
        return current_text or "请根据引用内容进行回应。", text
    return text, text


def _build_api_evidence_summary(persistent_score: float, assessment) -> List[str]:
    evidence: List[str] = [SDS_THRESHOLDS.interval_label(persistent_score)]
    if assessment is not None:
        for signal in assessment.signals:
            if (
                signal.source == "rule"
                and signal.severity >= 0.5
                and signal.metadata.get("context_flag") not in (
                    "negated_risk", "quoted_or_reported", "hypothetical"
                )
            ):
                evidence.append(
                    f"命中{signal.metadata.get('rule_category', '')}规则: {signal.name}"
                )
            elif signal.source == "trend" and signal.severity >= 0.5:
                evidence.append(signal.label)
        if assessment.protective_factors:
            evidence.append(f"当前存在保护因素 ({len(assessment.protective_factors)} 项)")
    return evidence or ["评估数据不足"]


def _save_risk_observation(session_id: str, result: Dict[str, Any]) -> None:
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")
    score_res = result.get("score_result", {})
    observation = RiskObservation(
        session_id=session_id,
        timestamp=time.time(),
        instant_sds_score=score_res.get("predicted_sds_score", 0),
        persistent_sds_score=result["persistent_score"],
        risk_level=result["risk_level"],
        safety_mode=safety.mode if safety else "",
        signal_names=[s.name for s in assessment.signals] if assessment else [],
        protective_names=assessment.protective_factors if assessment else [],
        primary_drivers=assessment.primary_drivers if assessment else [],
    )
    _risk_state.add_observation(session_id, observation)


def _number_or_fallback(value, fallback: float) -> float:
    return float(fallback if value is None else value)


def run_pipeline(
    user_text: str,
    audio_path: Optional[str] = None,
    session_id: Optional[str] = None,
    agent_profile: Optional[dict] = None,
) -> dict:
    analysis_text, reply_user_text = _split_analysis_and_reply_text(user_text)

    result: Dict[str, Any] = chain.invoke({
        "user_text": analysis_text,
        "reply_user_text": reply_user_text,
        "audio_path": audio_path,
        "session_id": session_id or "default",
        "agent_profile": agent_profile or {},
    })

    score_res: Dict[str, Any] = result["score_result"]
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")
    _save_risk_observation(session_id or "default", result)

    write_audit_record(
        session_id=session_id or "default",
        assessment_version=assessment.assessment_version if assessment else "unknown",
        policy_version="safety-policy-v1",
        final_level=result["risk_level"],
        safety_mode=safety.mode if safety else "unknown",
        signal_names=[s.name for s in assessment.signals] if assessment else [],
        primary_drivers=assessment.primary_drivers if assessment else [],
    )

    instant_score = _number_or_fallback(
        result.get("instant_score"),
        score_res.get("predicted_sds_score", 0),
    )
    smoothed_score = _number_or_fallback(result.get("smoothed_score"), instant_score)
    risk_adjusted_score = _number_or_fallback(
        result.get("risk_adjusted_score"),
        smoothed_score,
    )

    risk_signals_brief: List[RiskSignalBrief] = []
    if assessment is not None:
        for signal in assessment.signals:
            if signal.severity >= 0.4:
                risk_signals_brief.append(
                    RiskSignalBrief(
                        name=signal.name,
                        source=signal.source,
                        severity=signal.severity,
                    )
                )

    return {
        "reply": result["reply"],
        "risk_level": result["risk_level"],
        # score 保持兼容；模型评分和风险等级不再通过数值强制互相改写。
        "score": risk_adjusted_score,
        "instant_score": instant_score,
        "smoothed_score": smoothed_score,
        "persistent_score": smoothed_score,
        "risk_adjusted_score": risk_adjusted_score,
        "evidence": _build_api_evidence_summary(smoothed_score, assessment),
        "model_provider": settings.llm_provider,
        "model_name": settings.llm_model,
        "safety_mode": safety.mode if safety else None,
        "safety_actions": safety.required_actions if safety else [],
        "risk_signals": risk_signals_brief if risk_signals_brief else None,
    }
