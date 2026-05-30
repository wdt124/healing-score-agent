"""规则监测引擎

将 app/core/safety.py 的 bool 关键词检测升级为结构化 RiskSignal 输出。
- 扫描用户文本，匹配直接高危 / 中风险辅助规则模式
- 对每个命中检查上下文误报（否定/转述/假设/过去已解决）
- 检测保护因素
- 返回带置信度和元数据的 RiskSignal 列表
"""

from typing import List, Tuple, Optional
from app.risk.schemas import RiskSignal
from app.risk.rule_definitions import (
    ALL_SIGNAL_RULES,
    ALL_PROTECTIVE_RULES,
    CONTEXT_MARKERS,
)

# 每种上下文对应的窗口大小（检查关键词语前面多少个字符）
CONTEXT_WINDOW_BEFORE = {
    "negated_risk": 8,
    "quoted_or_reported": 15,
    "hypothetical": 15,
    "past_resolved": 15,
}


def _check_context(
    user_text: str,
    match_start: int,
) -> Optional[str]:
    """检查一个匹配位置附近是否存在上下文误报。

    Returns:
        如果命中误报上下文则返回其 key（如 "negated_risk"），否则返回 None。
    """
    # 按优先级检查：先否定，再转述，再假设，再过去已解决
    for ctx_key in ["negated_risk", "quoted_or_reported", "hypothetical", "past_resolved"]:
        ctx = CONTEXT_MARKERS[ctx_key]
        window = CONTEXT_WINDOW_BEFORE[ctx_key]
        before_start = max(0, match_start - window)
        before_text = user_text[before_start:match_start]

        for word in ctx["context_words"]:
            if word in before_text:
                return ctx_key

    return None


def _find_all_matches(text: str, pattern: str) -> List[int]:
    """返回 pattern 在 text 中所有匹配的起始位置"""
    positions: List[int] = []
    start = 0
    while True:
        pos = text.find(pattern, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


def scan_signals(user_text: str) -> List[RiskSignal]:
    """扫描用户文本，返回所有匹配的风险信号（含上下文置信度调整）"""
    signals: List[RiskSignal] = []

    for rule in ALL_SIGNAL_RULES:
        matched_patterns: List[Tuple[str, int]] = []
        for pattern in rule.patterns:
            positions = _find_all_matches(user_text, pattern)
            for pos in positions:
                matched_patterns.append((pattern, pos))

        if not matched_patterns:
            continue

        # 取第一个匹配位置作为上下文检测的输入
        first_match = min(matched_patterns, key=lambda x: x[1])
        first_pos = first_match[1]
        ctx_key = _check_context(user_text, first_pos)

        confidence = rule.severity
        evidence = first_match[0]
        metadata: dict = {
            "rule_name": rule.name,
            "rule_category": rule.category,
            "matched_patterns": [p for p, _ in matched_patterns],
        }

        if ctx_key is not None:
            ctx_info = CONTEXT_MARKERS[ctx_key]
            metadata["context_flag"] = ctx_key
            metadata["context_note"] = ctx_info["label"]
            # 降低置信度；否定 > 转述 > 假设 > 过去已解决
            confidence_reduction = {
                "negated_risk": 0.85,
                "quoted_or_reported": 0.7,
                "hypothetical": 0.8,
                "past_resolved": 0.6,
            }
            confidence = max(0.05, confidence * (1.0 - confidence_reduction.get(ctx_key, 0.5)))

        signals.append(RiskSignal(
            source="rule",
            name=rule.name,
            label=f"[{rule.category}] {rule.description}: {evidence}",
            severity=rule.severity,
            confidence=round(confidence, 2),
            evidence=evidence,
            metadata=metadata,
        ))

    return signals


def scan_protective_factors(user_text: str) -> List[RiskSignal]:
    """扫描保护因素"""
    signals: List[RiskSignal] = []

    for rule in ALL_PROTECTIVE_RULES:
        for pattern in rule.patterns:
            if pattern in user_text:
                signals.append(RiskSignal(
                    source="rule",
                    name=rule.name,
                    label=f"[{rule.category}] {rule.description}: {pattern}",
                    severity=0.0,
                    confidence=0.7,
                    evidence=pattern,
                    metadata={
                        "rule_name": rule.name,
                        "rule_category": rule.category,
                    },
                ))
                break  # 每条保护因素规则只记录一次

    return signals


def scan_all(user_text: str) -> dict:
    """一次性扫描所有规则，返回风险信号和保护因素"""
    risk_signals = scan_signals(user_text)
    protective_signals = scan_protective_factors(user_text)

    # 统计上下文相关的误报标记
    context_flags = []
    for s in risk_signals:
        if "context_flag" in s.metadata:
            context_flags.append(s.metadata["context_flag"])

    has_negation = "negated_risk" in context_flags
    has_quoted = "quoted_or_reported" in context_flags
    has_hypothetical = "hypothetical" in context_flags
    has_past = "past_resolved" in context_flags

    # 所有高风险信号都被否定时，应显著降低整体风险评估
    high_signals = [s for s in risk_signals if s.severity >= 0.85]
    all_high_negated = (
        len(high_signals) > 0
        and all(
            s.metadata.get("context_flag") == "negated_risk"
            for s in high_signals
        )
    )

    return {
        "risk_signals": risk_signals,
        "protective_signals": protective_signals,
        "context_flags": {
            "has_negation": has_negation,
            "has_quoted": has_quoted,
            "has_hypothetical": has_hypothetical,
            "has_past_resolved": has_past,
            "all_high_negated": all_high_negated,
        },
    }