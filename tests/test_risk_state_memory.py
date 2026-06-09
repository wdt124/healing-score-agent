"""风险状态记忆测试"""
import pytest
import time
from app.risk.risk_state_memory import RiskStateMemory, RiskObservation


class TestRiskObservation:
    def test_create_observation(self):
        obs = RiskObservation(
            session_id="test_sess",
            timestamp=time.time(),
            instant_sds_score=70.0,
            persistent_sds_score=68.0,
            risk_level="medium",
            safety_mode="safety_planning",
            signal_names=["hopelessness", "social_isolation"],
            protective_names=["has_support"],
            primary_drivers=["SDS 评分评估"],
        )
        assert obs.risk_level == "medium"
        assert obs.safety_mode == "safety_planning"
        assert len(obs.signal_names) == 2
        assert "has_support" in obs.protective_names

    def test_serialization_roundtrip(self):
        obs = RiskObservation(
            session_id="test_sess",
            timestamp=1234567890.0,
            instant_sds_score=55.0,
            persistent_sds_score=55.0,
            risk_level="low",
            signal_names=["sds_medium"],
            protective_names=[],
            primary_drivers=["SDS 评分评估"],
        )
        d = obs.to_serializable()
        obs2 = RiskObservation.from_dict(d)
        assert obs2.session_id == obs.session_id
        assert obs2.timestamp == obs.timestamp
        assert obs2.instant_sds_score == obs.instant_sds_score
        assert obs2.risk_level == obs.risk_level


class TestRiskStateMemory:
    def test_add_and_get_observations(self):
        mem = RiskStateMemory()
        test_session = "test_mem_add_get"
        mem.clear(test_session)

        for i in range(5):
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(1000 + i),
                instant_sds_score=50.0 + i * 5,
                persistent_sds_score=50.0 + i * 3,
                risk_level="low" if i < 3 else "medium",
                signal_names=["sds_medium"] if i >= 2 else [],
            ))

        recent = mem.get_recent_observations(test_session, limit=3)
        assert len(recent) == 3
        assert recent[-1].persistent_sds_score == 62.0  # 50 + 4*3

        mem.clear(test_session)

    def test_empty_memory_clean(self):
        mem = RiskStateMemory()
        recent = mem.get_recent_observations("nonexistent", limit=3)
        assert recent == []