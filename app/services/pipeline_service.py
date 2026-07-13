from typing import Dict, Any, Optional, List
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


def _build_api_evidence_summary(persistent_score: float, assessment) -> List[str]:
    evidence: List[str] = [SDS_THRESHOLDS.interval_label(persistent_score)]
    if assessment is not None:
        for s in assessment.signals:
            if s.source == "rule" and s.severity >= 0.5 and s.metadata.get("context_flag") != "negated_risk":
                evidence.append(f"命中{s.metadata.get('rule_category', '')}规则: {s.name}")
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


def run_pipeline(
    user_text: str,
    audio_path: Optional[str] = None,
    session_id: Optional[str] = None,
    agent_profile: Optional[dict] = None,
) -> dict:
    result: Dict[str, Any] = chain.invoke({
        "user_text": user_text,
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

    instant_score = float(result.get("instant_score") or score_res.get("predicted_sds_score", 0))
    smoothed_score = float(result.get("smoothed_score") or instant_score)
    persistent_score = float(result.get("persistent_score") or smoothed_score)
    risk_signals_brief: List[RiskSignalBrief] = []
    if assessment is not None:
        for s in assessment.signals:
            if s.severity >= 0.4:
                risk_signals_brief.append(RiskSignalBrief(name=s.name, source=s.source, severity=s.severity))

    return {
        "reply": result["reply"],
        "risk_level": result["risk_level"],
        # 保留 score 字段兼容旧前端；其含义是规则修正后用于风险评估的分数。
        "score": persistent_score,
        "instant_score": instant_score,
        "smoothed_score": smoothed_score,
        "persistent_score": persistent_score,
        "evidence": _build_api_evidence_summary(persistent_score, assessment),
        "model_provider": settings.llm_provider,
        "model_name": settings.llm_model,
        "safety_mode": safety.mode if safety else None,
        "safety_actions": safety.required_actions if safety else [],
        "risk_signals": risk_signals_brief if risk_signals_brief else None,
    }
