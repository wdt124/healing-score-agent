"""EMA 分数平滑器

对瞬时 SDS 评分做平滑，减少单次评分的波动性。
前几轮使用累计均值完成 warm-up，避免第一轮分数在 EMA 中长期占据过高权重；
warm-up 结束后再切换为指数移动平均。
"""

import time
from typing import Dict


class ScoreSmoother:
    """带 warm-up 的 EMA 分数平滑器。

    First turn: persistent_score = instant_score
    Warm-up turns: cumulative mean of all observed scores
    Subsequent turns: persistent_score = alpha * persistent_score + beta * instant_score

    默认 warmup_turns=3。这样第二、三轮不会被第一轮以 85% 权重锁住，
    第四轮开始再进入稳定 EMA。
    """

    def __init__(
        self,
        alpha: float = 0.85,
        beta: float = 0.15,
        ttl_seconds: float = 3600.0,
        warmup_turns: int = 3,
    ):
        if warmup_turns < 1:
            raise ValueError("warmup_turns must be >= 1")
        self.alpha = alpha
        self.beta = beta
        self.warmup_turns = warmup_turns
        self._store: Dict[str, float] = {}
        self._count: Dict[str, int] = {}
        self._last_access: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds

    def _touch(self, session_id: str) -> None:
        self._last_access[session_id] = time.time()

    def update(self, session_id: str, instant_score: float) -> float:
        """更新并返回平滑后的 persistent score。"""
        self._touch(session_id)
        instant_score = float(instant_score)
        previous_count = self._count.get(session_id, 0)
        current_count = previous_count + 1

        if previous_count == 0:
            smoothed = instant_score
        elif current_count <= self.warmup_turns:
            previous_mean = self._store[session_id]
            smoothed = (
                previous_mean * previous_count + instant_score
            ) / current_count
        else:
            smoothed = (
                self.alpha * self._store[session_id]
                + self.beta * instant_score
            )

        self._store[session_id] = smoothed
        self._count[session_id] = current_count
        return smoothed

    def get(self, session_id: str) -> float | None:
        self._touch(session_id)
        return self._store.get(session_id)

    def set(self, session_id: str, score: float) -> None:
        """直接设置分数（如危机修正），绕过 warm-up/EMA。"""
        self._touch(session_id)
        self._store[session_id] = float(score)
        self._count[session_id] = max(
            self._count.get(session_id, 0),
            self.warmup_turns,
        )

    def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._count.pop(session_id, None)
        self._last_access.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """移除超过 TTL 未访问的会话，返回移除数量。"""
        now = time.time()
        expired = [
            sid for sid, last in self._last_access.items()
            if now - last > self._ttl_seconds
        ]
        for sid in expired:
            self._store.pop(sid, None)
            self._count.pop(sid, None)
            self._last_access.pop(sid, None)
        return len(expired)
