"""趋势检测引擎

读取 RiskStateMemory 中的历史观察，产出趋势类 RiskSignal。
四种趋势信号：
  - rapid_worsening: 最近多轮快速恶化
  - repeated_high_risk_signal: 高危信号反复出现
  - sustained_elevated_risk: 长期高位
  - protective_factor_drop: 保护因素减少
"""

from typing import List, Optional
from app.risk.schemas import RiskSignal
from app.risk.risk_state_memory import _risk_state


def _detect_rapid_worsening(session_id: str) -> Optional[RiskSignal]:
    """最近 3 轮 SDS 连续上升，或等级快速跳跃"""
    records = _risk_state.get_recent_observations(session_id, limit=3)
    if len(records) < 3:
        return None

    scores = [r.persistent_sds_score for r in records]

    # SDS 连续上升
    if scores[2] > scores[1] > scores[0]:
        delta = scores[2] - scores[0]
        severity = min(0.9, 0.4 + delta / 100.0)
        return RiskSignal(
            source="trend",
            name="rapid_worsening",
            label=f"最近3轮 SDS 连续上升（{scores[0]:.0f}→{scores[1]:.0f}→{scores[2]:.0f}）",
            severity=severity,
            confidence=0.75,
            evidence=f"score delta: +{delta:.0f} over 3 rounds",
            metadata={"trend_type": "score_increase", "delta": delta},
        )

    # 等级快速跳跃（从 normal/low 直接到 high）
    level_weights = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    levels = [level_weights.get(r.risk_level, 0) for r in records]

    if levels[2] >= 3 and levels[0] <= 1:
        return RiskSignal(
            source="trend",
            name="rapid_worsening",
            label=f"风险等级快速上升（{records[0].risk_level}→{records[-1].risk_level}）",
            severity=0.80,
            confidence=0.75,
            evidence=f"level jump: {records[0].risk_level} → {records[-1].risk_level}",
            metadata={"trend_type": "level_jump"},
        )

    return None


def _detect_repeated_high_risk_signal(session_id: str) -> Optional[RiskSignal]:
    """最近 5 轮中，高危信号反复出现"""
    records = _risk_state.get_recent_observations(session_id, limit=5)
    if len(records) < 3:
        return None

    high_risk_names = {
        "suicide_ideation", "self_harm_ideation", "has_method",
        "has_time", "has_preparation", "cannot_stay_safe", "harm_to_others",
    }

    rounds_with_high = 0
    for r in records:
        if any(name in high_risk_names for name in r.signal_names):
            rounds_with_high += 1

    if rounds_with_high >= 2:
        return RiskSignal(
            source="trend",
            name="repeated_high_risk_signal",
            label=f"最近5轮中{rounds_with_high}轮出现高危信号",
            severity=0.75,
            confidence=0.80 if rounds_with_high >= 3 else 0.65,
            evidence=f"{rounds_with_high}/5 rounds with high-risk signals",
            metadata={"trend_type": "repeated_high", "count": rounds_with_high},
        )

    # 也检查绝望/撑不下去等中风险信号反复出现
    medium_risk_names = {"hopelessness", "panic_or_breakdown", "social_isolation"}
    rounds_with_medium = 0
    for r in records:
        if any(name in medium_risk_names for name in r.signal_names):
            rounds_with_medium += 1

    if rounds_with_medium >= 3:
        return RiskSignal(
            source="trend",
            name="repeated_high_risk_signal",
            label=f"最近5轮中{rounds_with_medium}轮出现中高危信号",
            severity=0.55,
            confidence=0.65,
            evidence=f"{rounds_with_medium}/5 rounds with distress signals",
            metadata={"trend_type": "repeated_medium", "count": rounds_with_medium},
        )

    return None


def _detect_sustained_elevated_risk(session_id: str) -> Optional[RiskSignal]:
    """连续多轮 medium 或 high"""
    records = _risk_state.get_recent_observations(session_id, limit=5)
    if len(records) < 3:
        return None

    # 最近连续 elevated 的轮数
    consecutive = 0
    for r in reversed(records):
        if r.risk_level in ("medium", "high", "critical"):
            consecutive += 1
        else:
            break

    if consecutive >= 3:
        return RiskSignal(
            source="trend",
            name="sustained_elevated_risk",
            label=f"连续{consecutive}轮处于中等及以上风险",
            severity=min(0.85, 0.5 + 0.1 * consecutive),
            confidence=0.70 + 0.05 * min(consecutive, 4),
            evidence=f"{consecutive} consecutive rounds at elevated risk",
            metadata={"trend_type": "sustained", "consecutive_rounds": consecutive},
        )

    # 检查 EMA 分数是否长期高于 medium 阈值
    if len(records) >= 4:
        above_63 = sum(1 for r in records[-4:] if r.persistent_sds_score >= 63)
        if above_63 >= 4:
            return RiskSignal(
                source="trend",
                name="sustained_elevated_risk",
                label=f"近4轮 SDS 分数持续≥63",
                severity=0.60,
                confidence=0.65,
                evidence=f"{above_63}/4 rounds with SDS >= 63",
                metadata={"trend_type": "sustained_sds"},
            )

    return None


def _detect_protective_factor_drop(session_id: str) -> Optional[RiskSignal]:
    """之前有保护因素，最近消失"""
    records = _risk_state.get_recent_observations(session_id, limit=5)
    if len(records) < 3:
        return None

    protective_names = {"has_support", "help_seeking", "future_orientation", "coping_strategy"}

    has_protective_in_past = any(
        any(p in protective_names for p in r.protective_names)
        for r in records[:3]
    )
    recent_records = records[-2:]
    has_protective_recently = any(
        any(p in protective_names for p in r.protective_names)
        for r in recent_records
    )

    if has_protective_in_past and not has_protective_recently:
        # 检查最近是否出现了孤立相关信号
        recent_isolation = any(
            "social_isolation" in r.signal_names for r in recent_records
        )
        severity = 0.65 if recent_isolation else 0.50

        return RiskSignal(
            source="trend",
            name="protective_factor_drop",
            label="保护因素减少，之前存在的支持/求助信号近期消失",
            severity=severity,
            confidence=0.60,
            evidence="protective factors present in earlier rounds but absent recently",
            metadata={"trend_type": "protective_drop"},
        )

    return None


def detect_trends(session_id: str) -> List[RiskSignal]:
    """运行全部趋势检测，返回趋势信号列表"""
    signals: List[RiskSignal] = []

    detectors = [
        _detect_rapid_worsening,
        _detect_repeated_high_risk_signal,
        _detect_sustained_elevated_risk,
        _detect_protective_factor_drop,
    ]

    for detector in detectors:
        result = detector(session_id)
        if result is not None:
            signals.append(result)

    return signals