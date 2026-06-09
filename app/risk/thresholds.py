"""SDS 评分阈值与等级判定

集中管理所有评分阈值，确保全项目使用单一来源。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SDSThresholds:
    """SDS 抑郁评分阈值，用于分数→风险等级的映射"""

    HIGH: float = 73.0
    MEDIUM: float = 63.0
    LOW: float = 53.0  # 低于此值为 normal

    def classify(self, score: float) -> str:
        """将 SDS 分数映射为风险等级字符串"""
        if score >= self.HIGH:
            return "high"
        if score >= self.MEDIUM:
            return "medium"
        if score >= self.LOW:
            return "low"
        return "normal"

    def interval_label(self, score: float) -> str:
        """返回分数所处区间的中文标签（用于低敏 evidence）"""
        if score >= self.HIGH:
            return "SDS 评分处于高区间"
        elif score >= self.MEDIUM:
            return "SDS 评分处于中高区间"
        elif score >= self.LOW:
            return "SDS 评分处于中等区间"
        else:
            return "SDS 评分处于低区间"

    def is_high(self, score: float) -> bool:
        return score >= self.HIGH

    def is_elevated(self, score: float) -> bool:
        """>= medium 阈值"""
        return score >= self.MEDIUM


# 全局单例
SDS_THRESHOLDS = SDSThresholds()
