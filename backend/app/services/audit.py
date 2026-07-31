from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import redact
from app.models.domain import AuditLog


def new_audit_id() -> str:
    return f"audit-{uuid.uuid4()}"


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    audit_id: str | None = None,
    actor_id: str | None = None,
    actor_type: str = "user",
    target_id: str | None = None,
    tenant_id: str | None = None,
    software_id: str | None = None,
    version_id: str | None = None,
    before_value: dict[str, Any] | None = None,
    after_value: dict[str, Any] | None = None,
    result: str = "success",
    rejection_reason: str | None = None,
    request: Request | None = None,
    event_type: str = "business",
    severity: str = "info",
    correlation_id: str | None = None,
    request_id: str | None = None,
    api_key_prefix: str | None = None,
) -> AuditLog:
    audit = AuditLog(
        audit_id=audit_id or new_audit_id(),
        correlation_id=correlation_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        tenant_id=tenant_id,
        software_id=software_id,
        version_id=version_id,
        ip=request.client.host if request and request.client else None,
        api_key_prefix=api_key_prefix,
        event_type=event_type,
        severity=severity,
        before_value=redact(before_value or {}),
        after_value=redact(after_value or {}),
        result=result,
        rejection_reason=rejection_reason,
        request_id=request_id,
        user_agent=request.headers.get("user-agent") if request else None,
        chain=[],
    )
    db.add(audit)
    db.flush()
    return audit
