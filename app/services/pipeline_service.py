"""管道编排服务

组装 5 步管道，编排 评分→记忆→风险评估→安全策略→回复 的完整链路。
同时负责：API 响应组装、风险观察落盘、审计日志写入。
"""

from typing import Dict, Any, Optional, List
from app.services.scoring_service import scoring_step
from app.services.memory_service import memory_step
from app.services.llm_service import reply_step
from langchain_core.runnables import RunnableLambda
from app.risk.assessment_engine import risk_assessment_step_fn
from app.safety.policy_engine import safety_policy_step_fn
from app.risk.risk_state_memory import _risk_state, RiskObservation
from app.risk.thresholds import SDS_THRESHOLDS
from app.models.schemas import RiskSignalBrief
from app.risk.audit import write_audit_record
from app.core.config import settings
import time

risk_assessment_step = RunnableLambda(risk_assessment_step_fn)
safety_policy_step = RunnableLambda(safety_policy_step_fn)

# 管道: scoring → memory → risk_assessment(含规则分数修正) → safety_policy → reply
chain = (scoring_step
         | memory_step
         | risk_assessment_step
         | safety_policy_step
         | reply_step)


def _build_api_evidence_summary(
    persistent_score: float,
    assessment,
) -> List[str]:
    """生成 API 响应的低敏证据摘要。

    注意：这是面向 API 客户端的低敏摘要，不暴露用户原文或内部评分细节。
    LLM 注入用的详细诊断上下文由 llm_service._build_llm_diagnostic_context 生成。
    """
    evidence: List[str] = []

    evidence.append(SDS_THRESHOLDS.interval_label(persistent_score))

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
    """将本轮风险评估结果落盘到 RiskStateMemory"""
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")
    score_res = result.get("score_result", {})

    signal_names = [s.name for s in assessment.signals] if assessment else []
    protective_factors = assessment.protective_factors if assessment else []
    primary_drivers = assessment.primary_drivers if assessment else []

    observation = RiskObservation(
        session_id=session_id,
        timestamp=time.time(),
        instant_sds_score=score_res.get("predicted_sds_score", 0),
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
    """执行完整评分→安全→回复管道，返回 ChatResponse 所需字段"""
    result: Dict[str, Any] = chain.invoke({
        "user_text": user_text,
        "audio_path": audio_path,
        "session_id": session_id or "default",
    })

    score_res: Dict[str, Any] = result["score_result"]
    assessment = result.get("risk_assessment")
    safety = result.get("safety_decision")

    # 风险观察落盘
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

    # API 低敏 evidence
    evidence = _build_api_evidence_summary(persistent_score, assessment)

    # API 精简风险信号
    risk_signals_brief: List[RiskSignalBrief] = []
    if assessment is not None:
        for s in assessment.signals:
            if s.severity >= 0.4:
                risk_signals_brief.append(RiskSignalBrief(
                    name=s.name,
                    source=s.source,
                    severity=s.severity,
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
    }
