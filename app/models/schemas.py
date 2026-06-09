from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    audio_path: Optional[str] = None


class RiskSignalBrief(BaseModel):
    """API 响应中的精简风险信号，不暴露原文"""
    name: str
    source: str
    severity: float


class ChatResponse(BaseModel):
    # 已有字段，保持兼容
    reply: str
    risk_level: str
    score: float
    evidence: List[str]
    model_provider: str
    model_name: str

    # 新增可选字段
    safety_mode: Optional[str] = None
    safety_actions: Optional[List[str]] = None
    risk_signals: Optional[List[RiskSignalBrief]] = None