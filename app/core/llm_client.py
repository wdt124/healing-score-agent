"""统一 LLM 客户端管理

集中管理 ChatOpenAI 实例，避免 scoring_engine 和 llm_service 各自创建独立的连接池。
按用途提供不同配置（temperature / max_tokens）。
"""

from typing import Optional
from langchain_openai import ChatOpenAI
from app.core.config import settings


class LLMClientManager:
    """统一管理所有 LLM 客户端实例。

    用法:
        scoring_client = LLMClientManager.get_scoring_client()
        reply_client = LLMClientManager.get_reply_client()
    """

    _scoring_client: Optional[ChatOpenAI] = None
    _reply_client: Optional[ChatOpenAI] = None

    @classmethod
    def _build_client(
        cls,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @classmethod
    def get_scoring_client(cls) -> ChatOpenAI:
        """评分/特征提取用客户端 (temperature=0.0，确定性输出)"""
        if cls._scoring_client is None:
            cls._scoring_client = cls._build_client(temperature=0.0, max_tokens=256)
        return cls._scoring_client

    @classmethod
    def get_reply_client(cls) -> ChatOpenAI:
        """对话回复用客户端 (temperature=0.7，适度变化)"""
        if cls._reply_client is None:
            cls._reply_client = cls._build_client(temperature=0.7, max_tokens=512)
        return cls._reply_client

    @classmethod
    def reset(cls) -> None:
        """重置所有客户端（测试用）"""
        cls._scoring_client = None
        cls._reply_client = None
