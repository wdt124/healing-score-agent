
### runnable组件 memory_step

from typing import Dict
from langchain_core.runnables import RunnableLambda


class PersistentScoreMemory:
    """EMA平滑

    First turn: persistent_score = instant_score
    Subsequent: persistent_score = a * persistent_score + b * instant_score
    """

    def __init__(self, a: float = 0.85, b: float = 0.15):
        self.a = a
        self.b = b
        self._store: Dict[str, float] = {}

    def update_persistent(self, session_id: str, instant_score: float) -> float:
        if session_id not in self._store:
            self._store[session_id] = instant_score
        else:
            self._store[session_id] = (
                self.a * self._store[session_id] + self.b * instant_score
            )
        return self._store[session_id]

    def get(self, session_id: str) -> float | None:
        return self._store.get(session_id)

    def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)


_memory = PersistentScoreMemory(a=0.85, b=0.15)

memory_step = RunnableLambda(lambda inputs: {
    **inputs,
    "instant_score": inputs["score_result"]["predicted_sds_score"],
    "persistent_score": _memory.update_persistent(
        inputs.get("session_id", "default"),
        inputs["score_result"]["predicted_sds_score"],
    ),
})