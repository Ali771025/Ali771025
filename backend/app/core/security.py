from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PII_PATTERNS = [
    (re.compile(r"09\d{9}"), "***REDACTED_MOBILE***"),
    (re.compile(r"\b\d{10,}\b"), "***REDACTED_ID***"),
]

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "credential",
    "connection_string",
    "authorization",
    "signature",
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_token(subject: str, minutes: int, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return create_token(subject, settings.access_token_expire_minutes, {"typ": "access", **(extra_claims or {})})


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return create_token(subject, settings.refresh_token_expire_minutes, {"typ": "refresh", **(extra_claims or {})})


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc


def redact(value: Any) -> Any:
    """Redact secrets recursively before storing audit logs or returning details."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        masked = value
        for pattern, replacement in PII_PATTERNS:
            masked = pattern.sub(replacement, masked)
        if len(masked) > 180:
            return f"{masked[:120]}…{masked[-20:]}"
        return masked
    return value


def api_key_prefix(secret: str) -> str:
    return secret[:8]
