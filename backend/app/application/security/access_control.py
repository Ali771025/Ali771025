from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.core.rbac import effective_permissions
from app.models.domain import SoftwareProduct, Tenant, User


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason_code: str | None = None
    message: str | None = None
    effective_permissions: set[str] = field(default_factory=set)
    effective_scopes: set[str] = field(default_factory=set)
    max_rows: int = 20
    timeout_seconds: int = 10
    policy_hash: str = ""
    access_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class AccessFingerprint:
    tenant_id: str | None
    software_id: str | None
    user_id: str
    roles: list[str]
    scopes: list[str]
    access_context: dict[str, Any]
    policy_hash: str

    def value(self) -> str:
        payload = {
            "tenant_id": self.tenant_id,
            "software_id": self.software_id,
            "user_id": self.user_id,
            "roles": sorted(self.roles),
            "scopes": sorted(self.scopes),
            "access_context": self.access_context,
            "policy_hash": self.policy_hash,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AccessControlService:
    """Centralized tenant/software/user authorization for report generation and admin actions."""

    def evaluate_report_access(
        self,
        *,
        tenant: Tenant | None,
        software: SoftwareProduct | None,
        user: User | None,
        external_user_id: str,
        access_context: dict[str, Any],
        required_scope: str | None,
        requested_limit: int | None = None,
    ) -> AccessDecision:
        if not tenant:
            return AccessDecision(False, "UNKNOWN_TENANT", "سازمان درخواست معتبر نیست.")
        if tenant.status != "active":
            return AccessDecision(False, "TENANT_INACTIVE", "سازمان غیرفعال یا معلق است.")
        if not software:
            return AccessDecision(False, "UNKNOWN_SOFTWARE", "نرم‌افزار درخواست معتبر نیست.")
        if software.status != "active":
            return AccessDecision(False, "SOFTWARE_INACTIVE", "نرم‌افزار غیرفعال است.")
        if software.tenant_id and software.tenant_id != tenant.id:
            return AccessDecision(False, "SOFTWARE_TENANT_MISMATCH", "نرم‌افزار متعلق به این سازمان نیست.")
        if tenant.allowed_software_ids and software.id not in tenant.allowed_software_ids:
            return AccessDecision(False, "SOFTWARE_NOT_ALLOWED_FOR_TENANT", "این نرم‌افزار برای سازمان مجاز نیست.")

        roles = list(access_context.get("roles") or [])
        scopes = set(access_context.get("scopes") or [])
        if user:
            if user.status != "active":
                return AccessDecision(False, "USER_INACTIVE", "کاربر غیرفعال است.")
            if user.tenant_id and user.tenant_id != tenant.id:
                return AccessDecision(False, "USER_TENANT_MISMATCH", "کاربر متعلق به این Tenant نیست.")
            roles = sorted(set(roles) | set(user.roles or []))
            scopes |= set(user.scopes or [])
        elif external_user_id:
            # On-premise callers may send the source software user id before user mapping is synced.
            roles = roles or ["report_user"]

        effective = effective_permissions(roles)
        if "report.request" not in effective and "*" not in scopes and required_scope not in scopes:
            return AccessDecision(False, "REPORT_PERMISSION_MISSING", "مجوز ثبت درخواست گزارش وجود ندارد.")
        if required_scope and "*" not in scopes and required_scope not in scopes:
            return AccessDecision(False, "SCOPE_DENIED", "Scope لازم برای موضوع گزارش وجود ندارد.")

        access_policy = software.access_policy or {}
        security_policy = software.security_policy or {}
        max_rows = int(access_policy.get("max_rows", security_policy.get("max_rows", 20)))
        timeout_seconds = int(access_policy.get("timeout_seconds", security_policy.get("timeout_seconds", 10)))
        tenant_limit = tenant.security_policy.get("max_rows") if tenant.security_policy else None
        if tenant_limit:
            max_rows = min(max_rows, int(tenant_limit))
        if requested_limit:
            max_rows = min(max_rows, requested_limit)

        policy_hash = self.policy_hash(tenant=tenant, software=software, roles=roles, scopes=sorted(scopes))
        fingerprint = AccessFingerprint(
            tenant_id=tenant.id,
            software_id=software.id,
            user_id=user.id if user else external_user_id,
            roles=roles,
            scopes=sorted(scopes),
            access_context=access_context,
            policy_hash=policy_hash,
        ).value()

        return AccessDecision(
            True,
            effective_permissions=effective,
            effective_scopes=scopes,
            max_rows=max_rows,
            timeout_seconds=timeout_seconds,
            policy_hash=policy_hash,
            access_fingerprint=fingerprint,
        )

    def policy_hash(self, *, tenant: Tenant | None, software: SoftwareProduct | None, roles: list[str], scopes: list[str]) -> str:
        payload = {
            "tenant": tenant.security_policy if tenant else {},
            "software_access": software.access_policy if software else {},
            "software_security": software.security_policy if software else {},
            "roles": sorted(roles),
            "scopes": sorted(scopes),
        }
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
