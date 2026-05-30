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
    resources_to_offer: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    audit_tags: List[str] = Field(default_factory=list)