"""EMA 分数平滑器

对瞬时 SDS 评分做指数移动平均(EMA)平滑，减少单次评分的波动性。
纯内存计算，不涉及文件 I/O。
"""

import time
from typing import Dict


class ScoreSmoother:
    """EMA (指数移动平均) SDS 分数平滑器

    First turn: persistent_score = instant_score
    Subsequent: persistent_score = alpha * persistent_score + beta * instant_score

    默认 alpha=0.85, beta=0.15，使历史权重远大于当前轮的波动。
    """

    def __init__(self, alpha: float = 0.85, beta: float = 0.15, ttl_seconds: float = 3600.0):
        self.alpha = alpha
        self.beta = beta
        self._store: Dict[str, float] = {}
        self._last_access: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds

    def _touch(self, session_id: str) -> None:
        self._last_access[session_id] = time.time()

    def update(self, session_id: str, instant_score: float) -> float:
        """更新并返回平滑后的 persistent score。"""
        self._touch(session_id)
        if session_id not in self._store:
            self._store[session_id] = instant_score
        else:
            self._store[session_id] = (
                self.alpha * self._store[session_id] + self.beta * instant_score
            )
        return self._store[session_id]

    def get(self, session_id: str) -> float | None:
        self._touch(session_id)
        return self._store.get(session_id)

    def set(self, session_id: str, score: float) -> None:
        """直接设置分数（如危机修正），绕过 EMA。"""
        self._touch(session_id)
        self._store[session_id] = score

    def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)
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
            self._last_access.pop(sid, None)
        return len(expired)
