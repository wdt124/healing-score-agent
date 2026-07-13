"""风险评估引擎

综合持续趋势分 + 规则监测信号 + 趋势信号 → 输出统一 RiskAssessment。

核心原则：
  - 计划/手段/时间等直接信号优先于分数
  - 趋势信号作为加权因素，防止不合理快速降级
  - 规则命中时只修正本轮用于风险评估的分数
  - 规则修正不反写模型分数平滑器，避免污染后续评分曲线
"""

from typing import Dict, Any, List
from app.risk.schemas import RiskAssessment, RiskSignal
from app.risk.rule_monitor import scan_all
from app.risk.trend_detector import detect_trends
from app.risk.thresholds import SDS_THRESHOLDS


def _apply_rule_based_score_adjustment(
    persistent_score: float,
    scan_result: dict,
) -> float:
    """根据规则扫描结果修正本轮风险评估分数。

    高危规则命中（非否定上下文）→ 本轮风险评估分提升至 95
    中危规则命中 + 当前分 < 60 → 本轮风险评估分提升至 60
    其余情况保持原分。

    注意：这里不修改分数平滑器。规则信号属于安全层证据，
    不应回写并污染后续的模型趋势分。
    """
    high_signals = [
        s for s in scan_result["risk_signals"]
        if s.severity >= 0.85
        and s.metadata.get("context_flag") != "negated_risk"
    ]
    medium_signals = [
        s for s in scan_result["risk_signals"]
        if 0.45 <= s.severity < 0.85
        and s.metadata.get("context_flag") != "negated_risk"
    ]

    if high_signals:
        return 95.0
    if medium_signals and persistent_score < 60:
        return 60.0
    return persistent_score


def _determine_risk_level(
    persistent_score: float,
    risk_signals: List[RiskSignal],
    context_flags: dict,
) -> str:
    """基于规则信号 + 持续分 + 趋势信号综合判定风险等级"""
    direct_signals = [
        s for s in risk_signals
        if s.severity >= 0.85
        and s.metadata.get("context_flag") not in ("negated_risk", "quoted_or_reported", "hypothetical")
    ]
    direct_names = {s.name for s in direct_signals}

    has_suicide = "suicide_ideation" in direct_names
    has_method = "has_method" in direct_names
    has_time = "has_time" in direct_names
    has_prep = "has_preparation" in direct_names
    has_cant_stay_safe = "cannot_stay_safe" in direct_names
    has_harm_others = "harm_to_others" in direct_names

    trend_names = {s.name for s in risk_signals if s.source == "trend"}
    has_rapid = "rapid_worsening" in trend_names
    has_repeated = "repeated_high_risk_signal" in trend_names
    has_sustained = "sustained_elevated_risk" in trend_names

    if context_flags.get("all_high_negated") and not has_cant_stay_safe:
        return "medium" if (has_sustained or has_repeated) else "normal"

    if has_method and (has_time or has_prep):
        return "critical"
    if has_suicide and (has_method or has_cant_stay_safe):
        return "critical"
    if has_harm_others and has_method:
        return "critical"

    if has_method or has_prep or has_cant_stay_safe or has_harm_others:
        return "high"
    if has_suicide:
        return "high"

    medium_signals = [
        s for s in risk_signals
        if 0.45 <= s.severity < 0.85
        and s.metadata.get("context_flag") != "negated_risk"
    ]

    high_sds = SDS_THRESHOLDS.is_high(persistent_score)
    medium_sds = SDS_THRESHOLDS.is_elevated(persistent_score)

    if has_time:
        return "high" if (len(direct_signals) >= 2 or len(risk_signals) >= 3 or has_rapid) else "medium"

    if has_rapid and len(medium_signals) >= 1:
        return "high" if high_sds else "medium"
    if has_repeated or has_sustained:
        return "high" if high_sds else "medium"

    if len(medium_signals) >= 3 and high_sds:
        return "high"
    if len(medium_signals) >= 2 and (medium_sds or high_sds):
        return "medium"

    if high_sds:
        return "medium"

    return SDS_THRESHOLDS.classify(persistent_score)


def build_risk_assessment(
    persistent_score: float,
    scan_result: dict,
    session_id: str = "default",
) -> RiskAssessment:
    """综合规则监测 + 趋势检测 + 本轮风险评估分，构建 RiskAssessment。"""
    risk_signals = scan_result["risk_signals"]
    protective_signals = scan_result["protective_signals"]
    context_flags = scan_result["context_flags"]

    trend_signals = detect_trends(session_id)

    sds_signal = None
    if SDS_THRESHOLDS.is_high(persistent_score):
        sds_signal = RiskSignal(
            source="sds",
            name="sds_high",
            label=f"SDS 高分 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
        )
    elif persistent_score >= SDS_THRESHOLDS.LOW:
        sds_signal = RiskSignal(
            source="sds",
            name="sds_medium",
            label=f"SDS 中等分数 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
        )

    all_signals: List[RiskSignal] = risk_signals + trend_signals
    if sds_signal:
        all_signals.append(sds_signal)

    final_level = _determine_risk_level(
        persistent_score=persistent_score,
        risk_signals=all_signals,
        context_flags=context_flags,
    )

    primary_drivers: List[str] = []
    for s in risk_signals:
        if s.severity >= 0.5 and s.metadata.get("context_flag") != "negated_risk":
            primary_drivers.append(s.label)
    for s in trend_signals:
        if s.severity >= 0.5:
            primary_drivers.append(s.label)
    if not primary_drivers:
        primary_drivers.append("SDS 评分评估")

    return RiskAssessment(
        level=final_level,
        score=persistent_score,
        primary_drivers=primary_drivers,
        signals=all_signals,
        protective_factors=[s.label for s in protective_signals],
        escalation_required=final_level in ("high", "critical"),
        assessment_version="risk-assessment-v1",
    )


def risk_assessment_step_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """管道步骤：规则扫描 → 本轮风险分修正 → 综合评级。"""
    session_id = inputs.get("session_id", "default")
    user_text = inputs["user_text"]
    persistent_score = inputs["persistent_score"]

    scan_result = scan_all(user_text)

    adjusted_score = _apply_rule_based_score_adjustment(
        persistent_score=persistent_score,
        scan_result=scan_result,
    )

    assessment = build_risk_assessment(
        persistent_score=adjusted_score,
        scan_result=scan_result,
        session_id=session_id,
    )

    return {
        **inputs,
        "risk_assessment": assessment,
        "risk_level": assessment.level,
        "persistent_score": adjusted_score,
    }
