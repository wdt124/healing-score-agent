"""风险评估引擎

综合 SDS 分数 + 规则监测信号 + 趋势信号 → 输出统一 RiskAssessment。

核心原则：
  - 计划/手段/时间等直接信号优先于 SDS 分数
  - 趋势信号作为加权因素，防止不合理快速降级
  - 规则命中时对 SDS 分数做安全修正
"""

from typing import Dict, Any, List
from app.risk.schemas import RiskAssessment, RiskSignal
from app.risk.rule_monitor import scan_all
from app.risk.trend_detector import detect_trends
from app.risk.thresholds import SDS_THRESHOLDS
from app.services.memory_service import _score_smoother


def _apply_rule_based_score_adjustment(
    persistent_score: float,
    scan_result: dict,
    session_id: str,
) -> float:
    """根据规则扫描结果修正 SDS 分数。

    高危规则命中（非否定上下文）→ 强制提升至 95 分
    中危规则命中 + 当前分 < 60 → 提升至 60 分
    其余情况保持原分。
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
        adjusted = 95.0
        _score_smoother.set(session_id, adjusted)
        return adjusted
    if medium_signals and persistent_score < 60:
        adjusted = 60.0
        _score_smoother.set(session_id, adjusted)
        return adjusted
    return persistent_score


def _determine_risk_level(
    persistent_score: float,
    risk_signals: List[RiskSignal],
    context_flags: dict,
) -> str:
    """基于规则信号 + SDS 分数 + 趋势信号综合判定风险等级"""
    # 直接高危信号（排除否定/转述/假设上下文）
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

    # 所有高危信号被否定 → 降级（但趋势信号存在时至少保留 medium）
    if context_flags.get("all_high_negated") and not has_cant_stay_safe:
        return "medium" if (has_sustained or has_repeated) else "normal"

    # ── critical 判定 ──
    if has_method and (has_time or has_prep):
        return "critical"
    if has_suicide and (has_method or has_cant_stay_safe):
        return "critical"
    if has_harm_others and has_method:
        return "critical"

    # ── high 判定 ──
    if has_method or has_prep or has_cant_stay_safe or has_harm_others:
        return "high"
    if has_suicide:
        return "high"

    # ── 中风险辅助信号 ──
    medium_signals = [
        s for s in risk_signals
        if 0.45 <= s.severity < 0.85
        and s.metadata.get("context_flag") != "negated_risk"
    ]

    high_sds = SDS_THRESHOLDS.is_high(persistent_score)
    medium_sds = SDS_THRESHOLDS.is_elevated(persistent_score)

    # 时间计划单独出现 → medium（防"今晚吃什么"误报），结合其他信号 → high
    if has_time:
        return "high" if (len(direct_signals) >= 2 or len(risk_signals) >= 3 or has_rapid) else "medium"

    # 趋势加权
    if has_rapid and len(medium_signals) >= 1:
        return "high" if high_sds else "medium"
    if has_repeated or has_sustained:
        return "high" if high_sds else "medium"

    # 多中危信号 + 高 SDS → high
    if len(medium_signals) >= 3 and high_sds:
        return "high"
    if len(medium_signals) >= 2 and (medium_sds or high_sds):
        return "medium"

    # SDS 高分无规则信号 → medium
    if high_sds:
        return "medium"

    # 纯 SDS 判定
    return SDS_THRESHOLDS.classify(persistent_score)


def build_risk_assessment(
    persistent_score: float,
    scan_result: dict,
    session_id: str = "default",
) -> RiskAssessment:
    """综合规则监测 + 趋势检测 + SDS 分数，构建 RiskAssessment。

    Args:
        persistent_score: 经 EMA 平滑 + 规则修正后的 SDS 分数
        scan_result: rule_monitor.scan_all() 的返回结果（外部传入，避免重复扫描）
        session_id: 会话 ID
    """
    risk_signals = scan_result["risk_signals"]
    protective_signals = scan_result["protective_signals"]
    context_flags = scan_result["context_flags"]

    trend_signals = detect_trends(session_id)

    # SDS 分数信号
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

    # 合并信号
    all_signals: List[RiskSignal] = risk_signals + trend_signals
    if sds_signal:
        all_signals.append(sds_signal)

    # 确定风险等级
    final_level = _determine_risk_level(
        persistent_score=persistent_score,
        risk_signals=all_signals,
        context_flags=context_flags,
    )

    # 主要驱动原因
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
    """管道步骤：规则扫描 → 分数修正 → 综合评级。

    注意：scan_all(user_text) 在此处只调用一次，结果同时传给
    分数修正和 build_risk_assessment，避免重复扫描。
    """
    session_id = inputs.get("session_id", "default")
    user_text = inputs["user_text"]
    persistent_score = inputs["persistent_score"]

    # 规则扫描（仅此一次）
    scan_result = scan_all(user_text)

    # 分数修正
    adjusted_score = _apply_rule_based_score_adjustment(
        persistent_score=persistent_score,
        scan_result=scan_result,
        session_id=session_id,
    )

    # 综合评估（复用同一份 scan_result）
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
