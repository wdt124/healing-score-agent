"""风险状态记忆

与 ConversationMemory 分离，只保存风险观察（分数/等级/信号摘要），
不保存完整用户原文，降低敏感数据扩散。
"""

import json
import os
import time
from typing import Dict, List
from dataclasses import dataclass, field, asdict


@dataclass
class RiskObservation:
    session_id: str
    timestamp: float
    instant_sds_score: float
    persistent_sds_score: float
    risk_level: str
    safety_mode: str = ""
    signal_names: List[str] = field(default_factory=list)
    protective_names: List[str] = field(default_factory=list)
    primary_drivers: List[str] = field(default_factory=list)

    def to_serializable(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RiskObservation":
        return cls(**d)


class RiskStateMemory:
    """存储每轮风险观察，不存用户原文。

    提供窗口查询方法，供 trend_detector 使用。
    """

    def __init__(self, filepath: str = "", ttl_seconds: float = 3600.0):
        if not filepath:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(current_dir, "..", "..", "data", "risk_history.json")
        self._filepath = os.path.abspath(filepath)
        self._store: Dict[str, List[RiskObservation]] = {}
        self._last_access: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds
        self._load_from_file()

    def _load_from_file(self) -> None:
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            for session_id, records in data.items():
                self._store[session_id] = [
                    RiskObservation.from_dict(r) for r in records
                ]
                self._last_access[session_id] = now
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _touch(self, session_id: str) -> None:
        self._last_access[session_id] = time.time()

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
        if expired:
            self._save_to_file()
        return len(expired)

    def _save_to_file(self) -> None:
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        serializable: Dict[str, list] = {}
        for session_id, observations in self._store.items():
            serializable[session_id] = [o.to_serializable() for o in observations]
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    def add_observation(self, session_id: str, observation: RiskObservation) -> None:
        self._touch(session_id)
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(observation)
        self._save_to_file()

    def get_recent_observations(self, session_id: str, limit: int = 5) -> List[RiskObservation]:
        self._touch(session_id)
        records = self._store.get(session_id, [])
        return records[-limit:]

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._last_access.pop(session_id, None)
        self._save_to_file()

    def clear_all(self) -> None:
        self._store.clear()
        self._last_access.clear()
        if os.path.exists(self._filepath):
            os.remove(self._filepath)


_risk_state = RiskStateMemory()