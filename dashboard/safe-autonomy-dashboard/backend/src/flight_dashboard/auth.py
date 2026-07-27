from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import Role
from .settings import Settings, get_settings


bearer = HTTPBearer(auto_error=False)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(rounds))
        return hmac.compare_digest(_b64(digest), expected)
    except (ValueError, TypeError):
        return False


def create_token(username: str, role: Role, settings: Settings) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(
        json.dumps(
            {"sub": username, "role": role.value, "iat": now, "exp": now + settings.jwt_ttl_seconds},
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64(hmac.new(settings.jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str, settings: Settings) -> dict:
    try:
        header_b64, payload, signature = token.split(".")
        header = json.loads(_unb64(header_b64))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("unsupported algorithm or token type")
        expected = _b64(
            hmac.new(settings.jwt_secret.encode(), f"{header_b64}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(payload))
        now = int(time.time())
        if claims.get("exp", 0) < now:
            raise ValueError("expired")
        if "iat" in claims and claims["iat"] > now + 60:
            raise ValueError("token issued in the future")
        Role(claims["role"])
        return claims
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نشست نامعتبر یا منقضی است") from exc


@dataclass(frozen=True)
class CurrentUser:
    username: str
    display_name: str
    role: Role


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ورود الزامی است")
    claims = decode_token(credentials.credentials, settings)
    role = Role(claims["role"])
    display = "کارشناس پرواز" if role == Role.FLIGHT_EXPERT else "مدیر پرواز"
    return CurrentUser(claims["sub"], display, role)


def require_role(*roles: Role):
    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="سطح دسترسی کافی نیست")
        return user

    return dependency

