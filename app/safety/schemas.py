from pydantic import BaseModel, Field
from typing import List


class SafetyDecision(BaseModel):
    mode: str = Field(
        default="normal_support",
        description="normal_support | supportive_checkin | safety_planning | crisis_intervention | emergency_escalation",
    )
    required_actions: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    response_constraints: str = Field(default="")
    reference_modules: List[str] = Field(
        default_factory=list,
        description="需要注入 LLM prompt 的知识库参考模块名列表",
    )