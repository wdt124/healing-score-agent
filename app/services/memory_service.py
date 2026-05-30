
### runnable组件 memory_step
'''memory_step:
        input:
            user_text
            score_result
            session_id
        output:
            user_text
            session_id
            score_result
            instant_score
            persistent_score

'''

import atexit
import json
import os
import time
from typing import Dict, List
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


class PersistentScoreMemory:
    """EMA平滑

    First turn: persistent_score = instant_score
    Subsequent: persistent_score = a * persistent_score + b * instant_score
    """

    def __init__(self, a: float = 0.85, b: float = 0.15, ttl_seconds: float = 3600.0):
        self.a = a
        self.b = b
        self._store: Dict[str, float] = {}
        self._last_access: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds

    def _touch(self, session_id: str) -> None:
        self._last_access[session_id] = time.time()

    def update_persistent(self, session_id: str, instant_score: float) -> float:
        self._touch(session_id)
        if session_id not in self._store:
            self._store[session_id] = instant_score
        else:
            self._store[session_id] = (
                self.a * self._store[session_id] + self.b * instant_score
            )
        return self._store[session_id]

    def get(self, session_id: str) -> float | None:
        self._touch(session_id)
        return self._store.get(session_id)

    def set(self, session_id: str, score: float) -> None:
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


class ConversationMemory:
    """存储每轮对话历史到文件，支持跨重启持久化。

    会话在 TTL 内未活动则自动过期，防止内存/磁盘无限增长。
    """

    def __init__(self, filepath: str = "", ttl_seconds: float = 3600.0):
        if not filepath:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(current_dir, "..", "..", "data", "conversation_history.json")
        self._filepath = os.path.abspath(filepath)
        self._store: Dict[str, List[BaseMessage]] = {}
        self._last_access: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds
        self._load_from_file()

    def _load_from_file(self) -> None:
        """启动时从文件恢复对话历史"""
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            for session_id, turns in data.items():
                messages: List[BaseMessage] = []
                for turn in turns:
                    messages.append(HumanMessage(content=turn["user"]))
                    messages.append(AIMessage(content=turn["assistant"]))
                self._store[session_id] = messages
                self._last_access[session_id] = now
        except (json.JSONDecodeError, KeyError):
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
        """每次对话后持久化到文件"""
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        serializable: Dict[str, list] = {}
        for session_id, messages in self._store.items():
            turns = []
            # messages 按 HumanMessage, AIMessage 交替排列
            for i in range(0, len(messages), 2):
                user_msg = messages[i].content if i < len(messages) else ""
                assistant_msg = messages[i + 1].content if i + 1 < len(messages) else ""
                turns.append({"user": user_msg, "assistant": assistant_msg})
            serializable[session_id] = turns
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    def add_turn(self, session_id: str, user_text: str, assistant_reply: str) -> None:
        self._touch(session_id)
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(HumanMessage(content=user_text))
        self._store[session_id].append(AIMessage(content=assistant_reply))
        self._save_to_file()

    def get_history_text(self, session_id: str, max_turns: int = 10) -> str:
        """将历史对话格式化为文本，注入 LLM 输入

        Args:
            session_id: 会话 ID
            max_turns: 最多保留最近 N 轮对话（每轮 = 用户 + 助手），
                      避免超出 LLM 上下文窗口。
        """
        self._touch(session_id)
        messages = self._store.get(session_id, [])
        if not messages:
            return ""
        # 每轮 2 条消息（用户 + 助手），保留最近 max_turns 轮
        max_messages = max_turns * 2
        recent_messages = messages[-max_messages:]
        lines = ["[以下为此前对话记录，用于理解上下文]"]
        for msg in recent_messages:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._last_access.pop(session_id, None)
        self._save_to_file()

    def clear_all(self) -> None:
        self._store.clear()
        self._last_access.clear()
        if os.path.exists(self._filepath):
            os.remove(self._filepath)


_conversation_memory = ConversationMemory()
_memory = PersistentScoreMemory(a=0.85, b=0.15)


def _cleanup() -> None:
    _conversation_memory.clear_all()


atexit.register(_cleanup)

memory_step = RunnableLambda(lambda inputs: {
    **inputs,
    "instant_score": inputs["score_result"]["predicted_sds_score"],
    "persistent_score": _memory.update_persistent(
        inputs.get("session_id", "default"),
        inputs["score_result"]["predicted_sds_score"],
    ),
})