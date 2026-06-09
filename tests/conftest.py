"""pytest 共享配置和 fixtures"""
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


# ── 共享 mock factories ──────────────────────────

def make_score_result(predicted_sds_score: float) -> dict:
    """创建 mock score_text_and_audio 的返回结构"""
    return {
        "status": "success",
        "engine_used": "mock",
        "predicted_sds_score": predicted_sds_score,
        "details": {
            "text_features_extracted": {},
            "audio_features_summary": {},
        },
    }


# ── 共享 fixtures ─────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_state():
    """每个测试前清理全局单例状态，确保测试隔离"""
    from app.risk.risk_state_memory import _risk_state
    from app.services.memory_service import _score_smoother
    _risk_state.clear("default")
    _score_smoother.reset("default")
    yield
