from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class RiskSignal(BaseModel):
    source: str  # sds / rule / trend / semantic
    name: str = Field(default="")  # unique id: suicide_ideation, has_method, etc.
    label: str  # human-readable label
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    level: str  # normal | low | medium | high | critical
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    primary_drivers: List[str] = Field(default_factory=list)
    signals: List[RiskSignal] = Field(default_factory=list)
    protective_factors: List[str] = Field(default_factory=list)
    escalation_required: bool = False
    assessment_version: str = "risk-assessment-v1"