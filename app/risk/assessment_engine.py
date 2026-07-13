"""风险评估引擎

综合持续趋势分 + 当前轮规则信号 + 历史趋势信号，输出统一 RiskAssessment。

核心原则：
  - 模型分数与安全风险等级是两套不同信号，不互相改写
  - 计划/手段/时间等直接危险信号优先于分数
  - 历史趋势只能作为辅助证据，不能在当前轮低分且无当前风险信号时单独抬级
  - 引用文本由 pipeline 在进入本模块前剥离，避免把被引用内容误判为当前意图
"""

from typing import Dict, Any, List
from app.risk.schemas import RiskAssessment, RiskSignal
from app.risk.rule_monitor import scan_all
from app.risk.trend_detector import detect_trends
from app.risk.thresholds import SDS_THRESHOLDS


INVALID_CONTEXT_FLAGS = {"negated_risk", "quoted_or_reported", "hypothetical"}


def _is_current_valid_rule_signal(signal: RiskSignal) -> bool:
    return (
        signal.source == "rule"
        and signal.metadata.get("context_flag") not in INVALID_CONTEXT_FLAGS
    )


def _determine_risk_level(
    persistent_score: float,
    risk_signals: List[RiskSignal],
    context_flags: dict,
) -> str:
    """基于当前规则信号、持续分与历史趋势综合判定风险等级。"""
    current_rule_signals = [s for s in risk_signals if _is_current_valid_rule_signal(s)]
    direct_signals = [s for s in current_rule_signals if s.severity >= 0.85]
    direct_names = {s.name for s in direct_signals}

    has_suicide = "suicide_ideation" in direct_names
    has_self_harm = "self_harm_ideation" in direct_names
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
        return SDS_THRESHOLDS.classify(persistent_score)

    # critical：必须有明确意图/无法保持安全，并与方法、时间或准备行为形成组合。
    if has_suicide and (has_method or has_prep or has_cant_stay_safe):
        return "critical"
    if has_self_harm and (has_method or has_prep or has_cant_stay_safe):
        return "critical"
    if has_harm_others and (has_method or has_prep):
        return "critical"
    if (has_suicide or has_self_harm) and has_time:
        return "critical"

    # high：明确意念、无法保证安全、明确伤人意图，或明确方法/准备行为。
    if has_suicide or has_self_harm or has_cant_stay_safe or has_harm_others:
        return "high"
    if has_method or has_prep:
        return "high"

    # bare time expression 只是修饰信息，不能单独把“今晚”等普通表达判为中风险。

    current_medium_signals = [
        s for s in current_rule_signals
        if 0.45 <= s.severity < 0.85
    ]

    high_score = SDS_THRESHOLDS.is_high(persistent_score)
    elevated_score = SDS_THRESHOLDS.is_elevated(persistent_score)
    low_or_above_score = persistent_score >= SDS_THRESHOLDS.LOW

    # 历史趋势只有在当前轮仍有相应证据或分数已升高时才抬级。
    if has_rapid and (current_medium_signals or low_or_above_score):
        return "high" if high_score else "medium"
    if (has_repeated or has_sustained) and (current_medium_signals or low_or_above_score):
        return "high" if high_score else "medium"

    if len(current_medium_signals) >= 3 and high_score:
        return "high"
    if len(current_medium_signals) >= 2 and (elevated_score or high_score):
        return "medium"

    # 单个中风险辅助信号不会覆盖一个很低的模型分；多个/持续信号才会升级。
    if high_score:
        return "medium"

    return SDS_THRESHOLDS.classify(persistent_score)


def build_risk_assessment(
    persistent_score: float,
    scan_result: dict,
    session_id: str = "default",
) -> RiskAssessment:
    """综合规则监测、历史趋势和持续模型分，构建 RiskAssessment。"""
    risk_signals = scan_result["risk_signals"]
    protective_signals = scan_result["protective_signals"]
    context_flags = scan_result["context_flags"]

    trend_signals = detect_trends(session_id)

    score_signal = None
    if SDS_THRESHOLDS.is_high(persistent_score):
        score_signal = RiskSignal(
            source="sds",
            name="sds_high",
            label=f"SDS 代理分较高 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
        )
    elif persistent_score >= SDS_THRESHOLDS.LOW:
        score_signal = RiskSignal(
            source="sds",
            name="sds_medium",
            label=f"SDS 代理分处于关注区间 ({persistent_score:.0f})",
            severity=persistent_score / 100.0,
        )

    all_signals: List[RiskSignal] = risk_signals + trend_signals
    if score_signal:
        all_signals.append(score_signal)

    final_level = _determine_risk_level(
        persistent_score=persistent_score,
        risk_signals=all_signals,
        context_flags=context_flags,
    )

    primary_drivers: List[str] = []
    for signal in risk_signals:
        if (
            signal.severity >= 0.5
            and signal.metadata.get("context_flag") not in INVALID_CONTEXT_FLAGS
        ):
            primary_drivers.append(signal.label)
    for signal in trend_signals:
        if signal.severity >= 0.5:
            primary_drivers.append(signal.label)
    if not primary_drivers:
        primary_drivers.append("持续模型评分")

    return RiskAssessment(
        level=final_level,
        score=persistent_score,
        primary_drivers=primary_drivers,
        signals=all_signals,
        protective_factors=[s.label for s in protective_signals],
        escalation_required=final_level in ("high", "critical"),
        assessment_version="risk-assessment-v2",
    )


def risk_assessment_step_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """管道步骤：扫描当前用户文本，再结合趋势与持续模型分评级。"""
    session_id = inputs.get("session_id", "default")
    user_text = inputs["user_text"]
    smoothed_score = float(inputs.get("smoothed_score", inputs["persistent_score"]))

    scan_result = scan_all(user_text)
    assessment = build_risk_assessment(
        persistent_score=smoothed_score,
        scan_result=scan_result,
        session_id=session_id,
    )

    return {
        **inputs,
        "risk_assessment": assessment,
        "risk_level": assessment.level,
        # persistent_score 始终保持为规则修正前的持续模型分。
        "persistent_score": smoothed_score,
        "risk_adjusted_score": smoothed_score,
    }
