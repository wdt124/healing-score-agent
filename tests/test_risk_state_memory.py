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

    def test_get_score_delta(self):
        mem = RiskStateMemory()
        test_session = "test_score_delta"
        mem.clear(test_session)

        scores = [60.0, 65.0, 72.0]
        for s in scores:
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(s),
                instant_sds_score=s,
                persistent_sds_score=s,
                risk_level="medium",
            ))

        delta = mem.get_score_delta(test_session, window=3)
        assert delta == 12.0  # 72 - 60

        # Not enough records
        delta2 = mem.get_score_delta("empty_session", window=3)
        assert delta2 is None

        mem.clear(test_session)

    def test_count_signal(self):
        mem = RiskStateMemory()
        test_session = "test_count_signal"
        mem.clear(test_session)

        for i in range(5):
            sigs = ["suicide_ideation"] if i % 2 == 0 else []
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(i),
                instant_sds_score=90.0 if i % 2 == 0 else 50.0,
                persistent_sds_score=70.0,
                risk_level="high" if i % 2 == 0 else "low",
                signal_names=sigs,
            ))

        count = mem.count_signal(test_session, "suicide_ideation", window=5)
        assert count == 3  # rounds 0, 2, 4

        mem.clear(test_session)

    def test_get_level_trend_worsening(self):
        mem = RiskStateMemory()
        test_session = "test_trend_worsening"
        mem.clear(test_session)

        for level in ["normal", "low", "medium"]:
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(1000 + len(mem.get_recent_observations(test_session))),
                instant_sds_score=50.0,
                persistent_sds_score=60.0,
                risk_level=level,
            ))

        trend = mem.get_level_trend(test_session, window=3)
        assert trend == "worsening"
        mem.clear(test_session)

    def test_get_level_trend_improving(self):
        mem = RiskStateMemory()
        test_session = "test_trend_improving"
        mem.clear(test_session)

        for level in ["high", "medium", "low"]:
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(2000 + len(mem.get_recent_observations(test_session))),
                instant_sds_score=50.0,
                persistent_sds_score=60.0,
                risk_level=level,
            ))

        trend = mem.get_level_trend(test_session, window=3)
        assert trend == "improving"
        mem.clear(test_session)

    def test_get_level_trend_stable(self):
        mem = RiskStateMemory()
        test_session = "test_trend_stable"
        mem.clear(test_session)

        for _ in range(3):
            mem.add_observation(test_session, RiskObservation(
                session_id=test_session,
                timestamp=float(3000 + len(mem.get_recent_observations(test_session))),
                instant_sds_score=65.0,
                persistent_sds_score=65.0,
                risk_level="medium",
            ))

        trend = mem.get_level_trend(test_session, window=3)
        assert trend == "stable"
        mem.clear(test_session)

    def test_empty_memory_returns_none(self):
        mem = RiskStateMemory()
        trend = mem.get_level_trend("nonexistent", window=3)
        assert trend is None

        delta = mem.get_score_delta("nonexistent", window=3)
        assert delta is None

        count = mem.count_signal("nonexistent", "suicide_ideation")
        assert count == 0