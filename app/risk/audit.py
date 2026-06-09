"""审计日志

每轮对话保存一条结构化审计记录，不存用户原文，
用于回归追踪、行为审计和策略版本管理。
"""

import json
import os
import time
from typing import List
from dataclasses import dataclass, field, asdict
from app.core.config import settings


@dataclass
class RiskAuditRecord:
    session_id: str
    timestamp: float
    assessment_version: str
    policy_version: str
    final_level: str
    safety_mode: str
    triggered_signal_names: List[str] = field(default_factory=list)
    primary_drivers: List[str] = field(default_factory=list)
    model_used: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RiskAuditRecord":
        return cls(**d)


class AuditLogger:
    """附加式审计日志，不覆盖旧记录"""

    def __init__(self, filepath: str = ""):
        if not filepath:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(current_dir, "..", "..", "data", "risk_audit.jsonl")
        self._filepath = os.path.abspath(filepath)

    def log(self, record: RiskAuditRecord) -> None:
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def read_recent(self, limit: int = 20) -> List[RiskAuditRecord]:
        if not os.path.exists(self._filepath):
            return []
        records: List[RiskAuditRecord] = []
        with open(self._filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(RiskAuditRecord.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return records[-limit:]

    def clear(self) -> None:
        if os.path.exists(self._filepath):
            os.remove(self._filepath)


_audit_logger = AuditLogger()


def write_audit_record(
    session_id: str,
    assessment_version: str,
    policy_version: str,
    final_level: str,
    safety_mode: str,
    signal_names: List[str],
    primary_drivers: List[str],
    model_used: str = "",
) -> None:
    if not model_used:
        model_used = settings.llm_model
    record = RiskAuditRecord(
        session_id=session_id,
        timestamp=time.time(),
        assessment_version=assessment_version,
        policy_version=policy_version,
        final_level=final_level,
        safety_mode=safety_mode,
        triggered_signal_names=signal_names,
        primary_drivers=primary_drivers,
        model_used=model_used,
    )
    _audit_logger.log(record)