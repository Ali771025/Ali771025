import time

from flight_dashboard.auth import create_token, decode_token, hash_password, verify_password
from flight_dashboard.chat import _safe_response
from flight_dashboard.models import AdvisoryAction, Role
from flight_dashboard.settings import Settings


def test_password_hash_and_token():
    encoded = hash_password("strong-password")
    assert verify_password("strong-password", encoded)
    assert not verify_password("bad", encoded)
    settings = Settings(jwt_secret="x" * 40)
    token = create_token("expert", Role.FLIGHT_EXPERT, settings)
    assert decode_token(token, settings)["sub"] == "expert"


def test_model_command_content_is_blocked():
    result = _safe_response(
        {"answer": "send vehicle_command now", "risk_level": "INFO", "suggested_action": "CONTINUE"},
        "conversation", "test-model",
    )
    assert result.suggested_action == AdvisoryAction.ABSTAIN
    assert "مسدود" in result.answer
