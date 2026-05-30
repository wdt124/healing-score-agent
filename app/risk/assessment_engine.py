"""风险评估引擎

综合 SDS 分数 + 规则监测信号 + 趋势信号 → 输出统一 RiskAssessment。
核心原则：计划/手段/时间等直接信号优先于 SDS 分数，
趋势信号作为加权因素（不轻易降级，不忽略慢性恶化）。
"""

from typing import Dict, Any, List
from app.risk.schemas import RiskAssessment, RiskSignal
from app.risk.rule_monitor import scan_all
from app.risk.trend_detector import detect_trends


def _determine_risk_level(
    crisis_level: str,
    persistent_score: float,
    risk_signals: List[RiskSignal],
    context_flags: dict,
) -> str:
    """基于规则信号 + SDS 分数 + 趋势信号综合判定最终风险等级"""
    # 收集直接高危信号（不被否定/转述/假设的）
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

    # 趋势信号
    trend_names = {s.name for s in risk_signals if s.source == "trend"}
    has_rapid = "rapid_worsening" in trend_names
    has_repeated = "repeated_high_risk_signal" in trend_names
    has_sustained = "sustained_elevated_risk" in trend_names

    # 所有高危信号都被否定 → 回退，但趋势信号存在时不应完全降为 normal
    if context_flags.get("all_high_negated") and not has_cant_stay_safe:
        # 有持续高位 / 反复高危趋势 → 至少保留 medium
        if has_sustained or has_repeated:
            return "medium"
        return "normal"

    # 方法 + (时间 或 准备) → critical
    if has_method and (has_time or has_prep):
        return "critical"

    # 自杀意念 + 方法 或 不能保证安全 → critical
    if has_suicide and (has_method or has_cant_stay_safe):
        return "critical"

    # 他伤风险 + 方法 → critical
    if has_harm_others and has_method:
        return "critical"

    # 方法 / 准备 / 不能保证安全 / 他伤 → high
    if has_method or has_prep or has_cant_stay_safe or has_harm_others:
        return "high"

    # 自杀意念 → high（趋势恶化可确认）
    if has_suicide:
        return "high"

    # 时间计划单独出现 → medium（"今晚吃什么"误报保护）
    # 但时间 + 其他信号或趋势恶化 → high
    if has_time:
        if len(direct_signals) >= 2 or len(risk_signals) >= 3 or has_rapid:
            return "high"
        return "medium"

    # 中风险辅助信号
    medium_signals = [
        s for s in risk_signals
        if 0.45 <= s.severity < 0.85
        and s.metadata.get("context_flag") != "negated_risk"
    ]

    high_sds = persistent_score >= 73
    medium_sds = persistent_score >= 63

    # 趋势信号加权：有快速恶化 + 中风险信号 → 至少 medium
    if has_rapid and len(medium_signals) >= 1:
        return "high" if high_sds else "medium"

    # 反复高危 → 不应低于 medium
    if has_repeated:
        return "high" if high_sds else "medium"

    # 长期高位 → 保持不降级
    if has_sustained:
        return "high" if high_sds else "medium"

    # 多个中风险信号 + 高 SDS → high
    if len(medium_signals) >= 3 and high_sds:
        return "high"

    # 至少 2 个中风险信号 + 中等 SDS → medium
    if len(medium_signals) >= 2 and (medium_sds or high_sds):
        return "medium"

    # SDS 高分但无规则信号 → medium
    if high_sds:
        return "medium"

    # crisis_step 的 high 若缺少规则支撑则降为 medium
    if crisis_level == "high" and not direct_signals:
        return "medium"

    return crisis_level


def build_risk_assessment(
    user_text: str,
    risk_level: str,
    persistent_score: float,
    evidence: List[str],
    session_id: str = "default",
) -> RiskAssessment:
    """运行规则监测 + 趋势检测 + SDS 信号，综合构建 RiskAssessment"""
    scan_result = scan_all(user_text)
    trend_signals = detect_trends(session_id)

    risk_signals = scan_result["risk_signals"]
    protective_signals = scan_result["protective_signals"]
    context_flags = scan_result["context_flags"]

    # SDS 分数信号
    sds_signal = None
    if persistent_score >= 73:
        sds_signal = RiskSignal(
            source="sds",
            name="sds_high",
            label=f"SDS 高分 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
            confidence=0.9,
        )
    elif persistent_score >= 53:
        sds_signal = RiskSignal(
            source="sds",
            name="sds_medium",
            label=f"SDS 中等分数 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
            confidence=0.8,
        )

    # 合并所有信号：规则信号 + 趋势信号 + SDS
    all_signals: List[RiskSignal] = risk_signals + trend_signals
    if sds_signal:
        all_signals.append(sds_signal)

    # 确定最终等级
    final_level = _determine_risk_level(
        crisis_level=risk_level,
        persistent_score=persistent_score,
        risk_signals=all_signals,
        context_flags=context_flags,
    )

    # 置信度：融合规则信号置信度 + 趋势信号
    rule_signals_count = len(risk_signals)
    trend_signals_count = len(trend_signals)

    if rule_signals_count > 0:
        avg_confidence = sum(s.confidence for s in risk_signals) / rule_signals_count
        if context_flags.get("has_negation"):
            avg_confidence *= 0.5
    else:
        avg_confidence = 0.6

    # 趋势信号存在时略微提高置信度
    if trend_signals:
        avg_confidence = min(0.95, avg_confidence + 0.05 * trend_signals_count)

    confidence = round(avg_confidence, 2)

    # 主要驱动原因
    primary_drivers = evidence.copy() if evidence else []
    for s in risk_signals:
        if s.severity >= 0.5 and s.metadata.get("context_flag") != "negated_risk":
            primary_drivers.append(s.label)
    for s in trend_signals:
        if s.severity >= 0.5:
            primary_drivers.append(s.label)

    if not primary_drivers:
        primary_drivers.append("SDS 评分评估")

    # 保护因素
    protective_factors = [s.label for s in protective_signals]

    return RiskAssessment(
        level=final_level,
        score=persistent_score,
        sds_score=persistent_score,
        confidence=confidence,
        primary_drivers=primary_drivers,
        signals=all_signals,
        protective_factors=protective_factors,
        escalation_required=final_level in ("high", "critical"),
        assessment_version="risk-assessment-v1",
    )


def risk_assessment_step_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
    session_id = inputs.get("session_id", "default")
    assessment = build_risk_assessment(
        user_text=inputs["user_text"],
        risk_level=inputs["risk_level"],
        persistent_score=inputs["persistent_score"],
        evidence=inputs.get("evidence", []),
        session_id=session_id,
    )
    return {
        **inputs,
        "risk_assessment": assessment,
        "risk_level": assessment.level,
    }