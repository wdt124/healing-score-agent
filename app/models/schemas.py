from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    audio_path: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    risk_level: str
    score: float
    evidence: List[str]
    model_provider: str
    model_name: str
