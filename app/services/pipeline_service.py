from typing import Dict, Any, Optional, List
from app.services.scoring_service import scoring_step
from app.services.memory_service import memory_step
from app.services.crisis_service import crisis_step
from app.services.llm_service import reply_step
from langchain_core.runnables import RunnableLambda
from app.risk.assessment_engine import risk_assessment_step_fn
from app.safety.policy_engine import safety_policy_step_fn
from app.risk.risk_state_memory import _risk_state, RiskObservation
from app.models.schemas import RiskSignalBrief
from app.risk.audit import write_audit_record
from app.core.config import settings
import time

risk_assessment_step = RunnableLambda(risk_assessment_step_fn)
safety_policy_step = RunnableLambda(safety_policy_step_fn)

chain = (scoring_step
         | memory_step
         | crisis_step
         | risk_assessment_step
         | safety_policy_step
         | reply_step)


def _build_low_sensitivity_evidence(
    persistent_score: float,
    assessment,
) -> List[str]:
    """生成短、可解释、低敏 evidence，不暴露用户原文"""
    evidence: List[str] = []

    if persistent_score >= 73:
        evidence.append("SDS 评分处于高区间")
    elif persistent_score >= 63:
        evidence.append("SDS 评分处于中高区间")
    elif persistent_score >= 53:
        evidence.append("SDS 评分处于中等区间")
    else:
        evidence.append("SDS 评分处于低区间")

    if assessment is not None:
        for s in assessment.signals:
            if s.source == "rule" and s.severity >= 0.5 and s.metadata.get("context_flag") != "negated_risk":
                tag = s.metadata.get("rule_category", "")
                evidence.append(f"命中{tag}规则: {s.name}")
            elif s.source == "trend" and s.severity >= 0.5:
                evidence.append(s.label)

        if assessment.protective_factors:
            evidence.append(f"当前存在保护因素 ({len(assessment.protective_factors)} 项)")

    if not evidence:
        evidence.append("评估数据不足")

    return evidence


def _save_risk_observation(session_id: str, result: Dict[str, Any]) -> None:
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")
    score_res = result.get("score_result", {})

    signal_names = [s.name for s in assessment.signals] if assessment else []
    protective_factors = assessment.protective_factors if assessment else []
    primary_drivers = assessment.primary_drivers if assessment else []

    observation = RiskObservation(
        session_id=session_id,
        timestamp=time.time(),
        instant_sds_score=score_res.get("predicted_sds_score", result.get("score", 0)),
        persistent_sds_score=result["persistent_score"],
        risk_level=result["risk_level"],
        safety_mode=safety.mode if safety else "",
        signal_names=signal_names,
        protective_names=protective_factors,
        primary_drivers=primary_drivers,
    )
    _risk_state.add_observation(session_id, observation)


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
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")

    _save_risk_observation(session_id or "default", result)

    # 审计日志
    signal_names = [s.name for s in assessment.signals] if assessment else []
    write_audit_record(
        session_id=session_id or "default",
        assessment_version=assessment.assessment_version if assessment else "unknown",
        policy_version="safety-policy-v1",
        final_level=result["risk_level"],
        safety_mode=safety.mode if safety else "unknown",
        signal_names=signal_names,
        primary_drivers=assessment.primary_drivers if assessment else [],
    )

    persistent_score = result.get("persistent_score") or score_res.get("predicted_sds_score", 0)

    evidence = _build_low_sensitivity_evidence(persistent_score, assessment)

    risk_signals_brief: List[RiskSignalBrief] = []
    if assessment is not None:
        for s in assessment.signals:
            if s.severity >= 0.4:
                risk_signals_brief.append(RiskSignalBrief(
                    name=s.name,
                    source=s.source,
                    severity=s.severity,
                    confidence=s.confidence,
                ))

    return {
        "reply": result["reply"],
        "risk_level": result["risk_level"],
        "score": persistent_score,
        "evidence": evidence,
        "model_provider": settings.llm_provider,
        "model_name": settings.llm_model,
        "safety_mode": safety.mode if safety else None,
        "safety_actions": safety.required_actions if safety else [],
        "risk_signals": risk_signals_brief if risk_signals_brief else None,
        "assessment_version": assessment.assessment_version if assessment else None,
        "policy_version": "safety-policy-v1",
    }