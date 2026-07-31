from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, actor_context_from_request
from app.application.use_cases.operations_management import (
    APIKeyRotationUseCase,
    AuditTimelineUseCase,
    ConnectorPolicySyncUseCase,
    GoldTestRegressionUseCase,
    RBACMatrixUseCase,
    TenantManagementUseCase,
    WalletOperationUseCase,
)
from app.core.rbac import Permission, require_permissions
from app.schemas.domain import WalletLedgerRead

router = APIRouter(tags=["عملیات پیشرفته و سطح دسترسی"])


class TenantSuspendCommand(BaseModel):
    reason: str


class TenantPolicyUpdateCommand(BaseModel):
    policies: dict[str, Any]


class WalletOperationCommand(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    manager_id: str | None = None
    operation_type: str = Field(pattern="^(charge|deduct|adjust|refund)$")
    amount: float = Field(gt=0)
    idempotency_key: str
    description: str | None = None
    expires_at: datetime | None = None


class RotateAPIKeyCommand(BaseModel):
    overlap_hours: int = Field(default=24, ge=0, le=168)


class RegressionRunCommand(BaseModel):
    software_id: str
    version_id: str


@router.post("/owner/tenants/{tenant_id}/suspend")
def suspend_tenant(
    tenant_id: str,
    payload: TenantSuspendCommand,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> dict[str, Any]:
    return TenantManagementUseCase(db).suspend(
        tenant_id,
        reason=payload.reason,
        actor=actor_context_from_request(request, current_user),
    )


@router.patch("/owner/tenants/{tenant_id}/policies")
def update_tenant_policies(
    tenant_id: str,
    payload: TenantPolicyUpdateCommand,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> dict[str, Any]:
    return TenantManagementUseCase(db).update_policies(
        tenant_id,
        payload.policies,
        actor=actor_context_from_request(request, current_user),
    )


@router.get("/owner/tenants/{tenant_id}/usage-summary")
def tenant_usage_summary(
    tenant_id: str,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_DASHBOARD_READ)),
) -> dict[str, Any]:
    return TenantManagementUseCase(db).usage_summary(tenant_id)


@router.get("/owner/rbac/matrix")
def owner_rbac_matrix(
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_AUDIT_READ)),
) -> dict[str, Any]:
    return RBACMatrixUseCase(db).matrix(tenant_id=current_user.tenant_id)


@router.get("/owner/rbac/effective-permissions/{user_id}")
def owner_effective_permissions(
    user_id: str,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_AUDIT_READ)),
) -> dict[str, Any]:
    return RBACMatrixUseCase(db).effective_permissions(user_id)


@router.get("/owner/audit-logs/{audit_id}/timeline")
def audit_timeline(
    audit_id: str,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_AUDIT_READ)),
) -> dict[str, Any]:
    return AuditTimelineUseCase(db).execute(audit_id)


@router.post("/owner/wallets/operation", response_model=WalletLedgerRead, status_code=status.HTTP_201_CREATED)
def wallet_operation(
    payload: WalletOperationCommand,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_FINANCE_WRITE)),
) -> WalletLedgerRead:
    command = payload.model_dump()
    command["idempotency_key"] = command["idempotency_key"] or getattr(request.state, "idempotency_key", None)
    return WalletOperationUseCase(db).execute(command, actor_context_from_request(request, current_user))


@router.post("/software-admin/api-keys/{key_id}/rotate")
def rotate_api_key(
    key_id: str,
    payload: RotateAPIKeyCommand,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.API_KEYS_WRITE)),
) -> dict[str, Any]:
    return APIKeyRotationUseCase(db).execute(
        key_id,
        actor=actor_context_from_request(request, current_user),
        overlap_hours=payload.overlap_hours,
    )


@router.post("/connectors/{connector_id}/policy-sync")
def connector_policy_sync(
    connector_id: str,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.CONNECTOR_OPERATE)),
) -> dict[str, Any]:
    return ConnectorPolicySyncUseCase(db).execute(connector_id, actor_context_from_request(request, current_user))


@router.post("/software-admin/gold-tests/regression/run")
def run_gold_regression(
    payload: RegressionRunCommand,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.QUALITY_WRITE)),
) -> dict[str, Any]:
    return GoldTestRegressionUseCase(db).execute(
        software_id=payload.software_id,
        version_id=payload.version_id,
        actor=actor_context_from_request(request, current_user),
    )
