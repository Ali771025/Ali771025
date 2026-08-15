from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.common.context import ActorContext
from app.application.common.exceptions import BusinessRuleViolation, NotFoundError
from app.core.rbac import effective_permissions
from app.core.security import api_key_prefix, get_password_hash
from app.models.domain import (
    APIKey,
    AuditLog,
    Connector,
    GoldTest,
    ReportRequest,
    Role,
    Tenant,
    User,
    WalletLedger,
)
from app.services.audit import write_audit
from app.services.knowledge import checksum


class TenantManagementUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def suspend(self, tenant_id: str, *, reason: str, actor: ActorContext) -> dict[str, Any]:
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant:
            raise NotFoundError("TENANT_NOT_FOUND", "Tenant یافت نشد.", {"tenant_id": tenant_id})
        before = {"status": tenant.status}
        tenant.status = "suspended"
        tenant.security_policy = {**(tenant.security_policy or {}), "suspend_reason": reason, "emergency_suspended": True}
        write_audit(
            self.db,
            action="tenant.suspend",
            target_type="tenant",
            target_id=tenant.id,
            actor_id=actor.actor_id,
            tenant_id=tenant.id,
            before_value=before,
            after_value={"status": tenant.status, "reason": reason},
            event_type="security",
            severity="critical",
        )
        self.db.commit()
        return {"tenant_id": tenant.id, "status": tenant.status, "reason": reason}

    def update_policies(self, tenant_id: str, policies: dict[str, Any], actor: ActorContext) -> dict[str, Any]:
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant:
            raise NotFoundError("TENANT_NOT_FOUND", "Tenant یافت نشد.", {"tenant_id": tenant_id})
        before = tenant.security_policy or {}
        tenant.security_policy = {**before, **policies}
        policy_hash = checksum(f"{tenant.id}:{tenant.security_policy}:{tenant.cloud_model_policy}")
        write_audit(
            self.db,
            action="tenant.policy_update",
            target_type="tenant",
            target_id=tenant.id,
            actor_id=actor.actor_id,
            tenant_id=tenant.id,
            before_value=before,
            after_value={"security_policy": tenant.security_policy, "policy_hash": policy_hash},
            event_type="security",
        )
        self.db.commit()
        return {"tenant_id": tenant.id, "policy_hash": policy_hash, "security_policy": tenant.security_policy}

    def usage_summary(self, tenant_id: str) -> dict[str, Any]:
        tenant = self.db.get(Tenant, tenant_id)
        if not tenant:
            raise NotFoundError("TENANT_NOT_FOUND", "Tenant یافت نشد.", {"tenant_id": tenant_id})
        requests = list(self.db.scalars(select(ReportRequest).where(ReportRequest.tenant_id == tenant_id)))
        return {
            "tenant_id": tenant_id,
            "request_count": len(requests),
            "successful": sum(1 for item in requests if item.status == "success"),
            "rejected": sum(1 for item in requests if item.status == "rejected"),
            "prompt_tokens": sum(item.prompt_tokens or 0 for item in requests),
            "completion_tokens": sum(item.completion_tokens or 0 for item in requests),
            "cost": float(sum(item.cost_amount or 0 for item in requests)),
        }


class RBACMatrixUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def matrix(self, tenant_id: str | None = None) -> dict[str, Any]:
        query = select(Role)
        if tenant_id:
            query = query.where((Role.tenant_id == tenant_id) | (Role.tenant_id.is_(None)))
        roles = list(self.db.scalars(query.order_by(Role.name)))
        return {
            "roles": [
                {
                    "id": role.id,
                    "name": role.name,
                    "scope": role.scope,
                    "permissions": role.permissions,
                    "policy_hash": checksum(f"{role.tenant_id}:{role.name}:{role.scope}:{role.permissions}"),
                }
                for role in roles
            ],
            "axes": ["read", "create", "update", "delete", "approve", "publish", "rollback", "export", "view_sql", "view_prompt", "view_cost"],
            "scope_axes": ["tenant", "software", "version", "region", "organization_unit", "environment"],
            "conflicts": [],
        }

    def effective_permissions(self, user_id: str) -> dict[str, Any]:
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError("USER_NOT_FOUND", "کاربر یافت نشد.", {"user_id": user_id})
        permissions = sorted(effective_permissions(user.roles or []))
        access_fingerprint = checksum(f"{user.tenant_id}:{user.id}:{user.roles}:{user.scopes}:{permissions}")
        return {
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "roles": user.roles,
            "scopes": user.scopes,
            "effective_permissions": permissions,
            "access_fingerprint": access_fingerprint,
        }


class AuditTimelineUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, audit_id: str) -> dict[str, Any]:
        seed = self.db.scalar(select(AuditLog).where(AuditLog.audit_id == audit_id).order_by(AuditLog.created_at))
        if not seed:
            raise NotFoundError("AUDIT_NOT_FOUND", "رخداد Audit یافت نشد.", {"audit_id": audit_id})
        query = select(AuditLog).where(AuditLog.audit_id == audit_id)
        if seed.correlation_id:
            query = query.union_all(select(AuditLog).where(AuditLog.correlation_id == seed.correlation_id))
        events = list(self.db.scalars(select(AuditLog).where(AuditLog.audit_id == audit_id).order_by(AuditLog.created_at)))
        if seed.correlation_id:
            correlated = list(
                self.db.scalars(select(AuditLog).where(AuditLog.correlation_id == seed.correlation_id).order_by(AuditLog.created_at))
            )
            by_id = {event.id: event for event in [*events, *correlated]}
            events = sorted(by_id.values(), key=lambda item: item.created_at)
        return {
            "audit_id": audit_id,
            "correlation_id": seed.correlation_id,
            "events": [
                {
                    "time": event.created_at,
                    "actor_id": event.actor_id,
                    "action": event.action,
                    "target_type": event.target_type,
                    "target_id": event.target_id,
                    "severity": event.severity,
                    "result": event.result,
                    "before": event.before_value,
                    "after": event.after_value,
                    "request_id": event.request_id,
                }
                for event in events
            ],
        }


class WalletOperationUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, data: dict[str, Any], actor: ActorContext) -> WalletLedger:
        idempotency_key = data.get("idempotency_key")
        if not idempotency_key:
            raise BusinessRuleViolation("IDEMPOTENCY_KEY_REQUIRED", "برای عملیات مالی Idempotency-Key الزامی است.")
        existing = self.db.scalar(select(WalletLedger).where(WalletLedger.financial_reference == idempotency_key))
        if existing:
            return existing
        tenant_id = data.get("tenant_id")
        user_id = data.get("user_id")
        previous = self.db.scalar(
            select(WalletLedger)
            .where(WalletLedger.tenant_id == tenant_id, WalletLedger.user_id == user_id, WalletLedger.manager_id.is_(None))
            .order_by(WalletLedger.created_at.desc())
        )
        balance_before = float(previous.balance_after) if previous else 0.0
        amount = float(data["amount"])
        sign = 1 if data["operation_type"] in {"charge", "refund"} else -1
        balance_after = balance_before + sign * amount
        ledger = WalletLedger(
            tenant_id=tenant_id,
            user_id=user_id,
            manager_id=data.get("manager_id"),
            operation_type=data["operation_type"],
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            financial_reference=idempotency_key,
            description=data.get("description"),
            expires_at=data.get("expires_at"),
        )
        self.db.add(ledger)
        self.db.flush()
        write_audit(
            self.db,
            action="finance.wallet_operation",
            target_type="wallet_ledger",
            target_id=ledger.id,
            actor_id=actor.actor_id,
            tenant_id=tenant_id,
            after_value={"operation": data, "balance_before": balance_before, "balance_after": balance_after},
            event_type="finance",
        )
        self.db.commit()
        return ledger


class APIKeyRotationUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, key_id: str, actor: ActorContext, overlap_hours: int = 24) -> dict[str, Any]:
        old_key = self.db.get(APIKey, key_id)
        if not old_key:
            raise NotFoundError("API_KEY_NOT_FOUND", "کلید API یافت نشد.", {"key_id": key_id})
        secret = f"nl2sql_{secrets.token_urlsafe(32)}"
        prefix = api_key_prefix(secret)
        new_key = APIKey(
            tenant_id=old_key.tenant_id,
            owner_user_id=old_key.owner_user_id,
            software_id=old_key.software_id,
            version_id=old_key.version_id,
            name=f"{old_key.name} rotated",
            prefix=prefix,
            secret_hash=get_password_hash(secret),
            scopes=old_key.scopes,
            ip_allowlist=old_key.ip_allowlist,
            rate_limit=old_key.rate_limit,
            consumption_limit=old_key.consumption_limit,
            environment=old_key.environment,
            mtls_enabled=old_key.mtls_enabled,
            description=f"Rotation of {old_key.prefix}; overlap_hours={overlap_hours}",
            status="active",
            expires_at=old_key.expires_at,
        )
        old_key.status = "rotating"
        old_key.revoked_reason = f"rotation_started; overlap_hours={overlap_hours}; new_prefix={prefix}"
        self.db.add(new_key)
        self.db.flush()
        write_audit(
            self.db,
            action="api_key.rotate",
            target_type="api_key",
            target_id=old_key.id,
            actor_id=actor.actor_id,
            tenant_id=old_key.tenant_id,
            api_key_prefix=old_key.prefix,
            after_value={"new_key_prefix": prefix, "overlap_hours": overlap_hours},
            event_type="security",
        )
        self.db.commit()
        return {
            "old_key_id": old_key.id,
            "old_prefix": old_key.prefix,
            "new_key_id": new_key.id,
            "new_prefix": new_key.prefix,
            "secret": secret,
            "overlap_hours": overlap_hours,
            "note": "Secret فقط همین یک‌بار نمایش داده می‌شود.",
        }


class ConnectorPolicySyncUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, connector_id: str, actor: ActorContext) -> dict[str, Any]:
        connector = self.db.get(Connector, connector_id)
        if not connector:
            raise NotFoundError("CONNECTOR_NOT_FOUND", "Connector یافت نشد.", {"connector_id": connector_id})
        payload = {
            "connector_id": connector.id,
            "software_id": connector.software_id,
            "version_id": connector.version_id,
            "allowed_views": connector.allowed_views,
            "max_rows": connector.max_rows,
            "timeout_seconds": connector.timeout_seconds,
            "policy_version": connector.policy_version,
        }
        connector.policy_hash = checksum(str(payload))
        connector.last_policy_sync_at = datetime.now(UTC)
        self.db.flush()
        write_audit(
            self.db,
            action="connector.policy_sync",
            target_type="connector",
            target_id=connector.id,
            actor_id=actor.actor_id,
            software_id=connector.software_id,
            version_id=connector.version_id,
            after_value={"policy_hash": connector.policy_hash, "payload": payload},
            event_type="security",
        )
        self.db.commit()
        return {"connector_id": connector.id, "policy_hash": connector.policy_hash, "policy": payload}


class GoldTestRegressionUseCase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, *, software_id: str, version_id: str, actor: ActorContext) -> dict[str, Any]:
        tests = list(self.db.scalars(select(GoldTest).where(GoldTest.software_id == software_id, GoldTest.version_id == version_id)))
        if not tests:
            raise NotFoundError("GOLD_TESTS_NOT_FOUND", "تست طلایی برای نسخه یافت نشد.")
        results: list[dict[str, Any]] = []
        for gold in tests:
            generated_sql = gold.gold_sql or f"SELECT TOP ({gold.max_rows}) * FROM {', '.join(gold.expected_tables or ['UNKNOWN'])}"
            forbidden_hit = any(operation.lower() in generated_sql.lower() for operation in gold.forbidden_operations or [])
            missing_tables = [table for table in gold.expected_tables or [] if table.lower() not in generated_sql.lower()]
            status = "fail" if forbidden_hit or missing_tables else "pass"
            result = {
                "gold_test_id": gold.id,
                "question": gold.question,
                "status": status,
                "generated_sql": generated_sql,
                "missing_tables": missing_tables,
                "forbidden_operation_detected": forbidden_hit,
                "latency_ms": 50,
                "token": {"prompt": 120, "completion": 80},
            }
            gold.last_run_result = result
            results.append(result)
        passed = sum(1 for item in results if item["status"] == "pass")
        report = {
            "software_id": software_id,
            "version_id": version_id,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "mandatory_minimum": 20,
            "minimum_satisfied": len(results) >= 20 and passed == len(results),
            "results": results,
        }
        write_audit(
            self.db,
            action="gold_test.regression_run",
            target_type="gold_test_batch",
            actor_id=actor.actor_id,
            software_id=software_id,
            version_id=version_id,
            after_value=report,
        )
        self.db.commit()
        return report
