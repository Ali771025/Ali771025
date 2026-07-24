from __future__ import annotations
import os
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Optional
import yaml

_RTSP_CRED_RE = re.compile(r"rtsp://(?P<user>[^:]+):(?P<pwd>[^@]+)@")

def mask_url(url: str) -> str:
    if not url:
        return url
    # mask password in rtsp://user:pass@...
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}:****@{netloc}"
            masked = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            return masked
    except Exception:
        pass
    # fallback regex
    return _RTSP_CRED_RE.sub(r"rtsp://\g<user>:****@", url)

def load_secrets_file(path: Optional[str]) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text()) or {}
        return data
    except Exception:
        return {}

def expand_source_with_secrets(source: str, env_user_var: str = "CAMERA_USER", env_pass_var: str = "CAMERA_PASSWORD", secrets_file: Optional[str] = None) -> str:
    if not source:
        return source
    # replace placeholder CAMERA_USER etc if in source and env present
    user = os.environ.get(env_user_var)
    pwd = os.environ.get(env_pass_var)
    sec = load_secrets_file(secrets_file)
    # secrets file may contain rtsp_user, rtsp_password or user, password
    file_user = sec.get("rtsp_user") or sec.get("user")
    file_pwd = sec.get("rtsp_password") or sec.get("password")

    effective_user = file_user or user
    effective_pwd = file_pwd or pwd

    # If source contains literal placeholders CAMERA_USER etc
    if "CAMERA_USER" in source and effective_user:
        source = source.replace("CAMERA_USER", effective_user)
    if "CAMERA_PASSWORD" in source and effective_pwd:
        source = source.replace("CAMERA_PASSWORD", effective_pwd)

    # If source is rtsp and lacks credentials but env provides, inject? we don't inject if already has @
    # For case source like rtsp://ip/... and we have user/pwd, we can inject
    if source.startswith("rtsp://") and "@" not in source.split("/")[2] if len(source.split("/"))>2 else True:
        if effective_user and effective_pwd:
            # inject after scheme
            try:
                # rtsp://host/path -> rtsp://user:pass@host/path
                rest = source[len("rtsp://"):]
                source = f"rtsp://{effective_user}:{effective_pwd}@{rest}"
            except Exception:
                pass
    return source
