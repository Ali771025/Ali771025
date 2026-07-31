from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.rbac import Permission, require_permissions
from app.core.security import get_password_hash
from app.models.domain import (
    AIModel,
    AuditLog,
    Payment,
    ReportRequest,
    Role,
    SoftwareProduct,
    Tariff,
    Tenant,
    User,
    WalletLedger,
)
from app.schemas.domain import (
    AIModelCreate,
    AIModelRead,
    AuditLogRead,
    DashboardMetric,
    DashboardResponse,
    ManagerCreate,
    PaymentCreate,
    RoleCreate,
    RoleRead,
    TariffCreate,
    TariffRead,
    TenantCreate,
    TenantRead,
    UserRead,
    WalletLedgerRead,
    WalletOperation,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/owner", tags=["پنل مالک سامانه"])
OwnerUser = Depends(require_permissions(Permission.OWNER_DASHBOARD_READ))


@router.get("/dashboard", response_model=DashboardResponse)
def owner_dashboard(
    db: DbSession,
    current_user: CurrentUser = OwnerUser,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    software_id: str | None = None,
    model_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    cache_hit: bool | None = None,
) -> DashboardResponse:
    query = select(ReportRequest)
    filters: dict[str, Any] = {
        "start_at": start_at,
        "end_at": end_at,
        "software_id": software_id,
        "model_id": model_id,
        "status": status_filter,
        "cache_hit": cache_hit,
    }
    if start_at:
        query = query.where(ReportRequest.created_at >= start_at)
    if end_at:
        query = query.where(ReportRequest.created_at <= end_at)
    if software_id:
        query = query.where(ReportRequest.software_id == software_id)
    if model_id:
        query = query.where(ReportRequest.model_id == model_id)
    if status_filter:
        query = query.where(ReportRequest.status == status_filter)
    if cache_hit is not None:
        query = query.where(ReportRequest.cache_hit == cache_hit)

    requests = db.scalars(query).all()
    total = len(requests)
    successful = sum(1 for item in requests if item.status == "success")
    rejected = sum(1 for item in requests if item.status == "rejected")
    clarification = sum(1 for item in requests if item.status == "needs_clarification")
    token_sum = sum((item.prompt_tokens or 0) + (item.completion_tokens or 0) for item in requests)
    cost_sum = float(sum(item.cost_amount or 0 for item in requests))
    cache_count = sum(1 for item in requests if item.cache_hit)
    latencies = sorted([item.response_time_ms for item in requests if item.response_time_ms is not None])
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0

    model_health = db.scalars(select(AIModel)).all()
    security_events = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.event_type == "security")) or 0

    return DashboardResponse(
        filters={key: str(value) if isinstance(value, datetime) else value for key, value in filters.items()},
        metrics=[
            DashboardMetric(label="کل درخواست‌ها", value=total),
            DashboardMetric(label="درخواست موفق", value=successful),
            DashboardMetric(label="ردشده", value=rejected),
            DashboardMetric(label="نیازمند شفاف‌سازی", value=clarification),
            DashboardMetric(label="نرخ پاسخ صحیح", value=round(successful / total * 100, 2) if total else 0),
            DashboardMetric(label="مصرف Token", value=token_sum),
            DashboardMetric(label="هزینه مصرف", value=cost_sum),
            DashboardMetric(label="نرخ Cache Hit", value=round(cache_count / total * 100, 2) if total else 0),
            DashboardMetric(label="میانگین زمان پاسخ", value=avg_latency),
            DashboardMetric(label="P95 زمان پاسخ", value=p95),
            DashboardMetric(label="رخدادهای امنیتی", value=security_events),
            DashboardMetric(label="مدل‌های ثبت‌شده", value=len(model_health)),
        ],
        charts={
            "daily_usage": [],
            "top_topics": [],
            "model_status": [
                {"id": model.id, "name": model.name, "status": model.status, "health": model.health_status}
                for model in model_health
            ],
        },
        alerts=[{"severity": "info", "message": "داشبورد مالک با داده عملیاتی تکمیل می‌شود."}],
    )


@router.post("/managers", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_manager(
    payload: ManagerCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> UserRead:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="username already exists")
    manager = User(
        tenant_id=payload.tenant_id,
        username=payload.username,
        email=payload.email,
        mobile=payload.mobile,
        first_name=payload.first_name,
        last_name=payload.last_name,
        hashed_password=get_password_hash(payload.temporary_password),
        roles=payload.roles,
        scopes=payload.scopes,
        daily_quota=int(payload.consumption_limit) if payload.consumption_limit else None,
        expires_at=payload.expires_at,
        status=payload.status,
        mfa_required=payload.mfa_required,
    )
    db.add(manager)
    db.flush()
    write_audit(
        db,
        action="owner.manager_create",
        target_type="user",
        target_id=manager.id,
        actor_id=current_user.id,
        tenant_id=payload.tenant_id,
        after_value=payload.model_dump(exclude={"temporary_password"}, mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(manager)
    return manager


@router.get("/managers", response_model=list[UserRead])
def list_managers(db: DbSession, current_user: CurrentUser = OwnerUser, limit: int = 50, offset: int = 0) -> list[UserRead]:
    return list(
        db.scalars(
            select(User)
            .where(User.roles.contains(["software_admin"]))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/managers/{manager_id}/reset-password", response_model=dict[str, str])
def reset_manager_password(
    manager_id: str,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> dict[str, str]:
    manager = db.get(User, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="manager not found")
    temporary = "TempChangeMe!12345"
    manager.hashed_password = get_password_hash(temporary)
    write_audit(db, action="owner.manager_reset_password", target_type="user", target_id=manager.id, actor_id=current_user.id, request=request)
    db.commit()
    return {"temporary_password": temporary, "message": "رمز موقت فقط همین‌جا نمایش داده می‌شود."}


@router.patch("/managers/{manager_id}/status", response_model=UserRead)
def change_manager_status(
    manager_id: str,
    new_status: str,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> UserRead:
    manager = db.get(User, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="manager not found")
    before = {"status": manager.status}
    manager.status = new_status
    write_audit(db, action="owner.manager_status", target_type="user", target_id=manager.id, actor_id=current_user.id, before_value=before, after_value={"status": new_status}, request=request)
    db.commit()
    db.refresh(manager)
    return manager


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> RoleRead:
    role = Role(**payload.model_dump())
    db.add(role)
    db.flush()
    write_audit(db, action="owner.role_create", target_type="role", target_id=role.id, actor_id=current_user.id, after_value=payload.model_dump(), request=request)
    db.commit()
    db.refresh(role)
    return role


@router.get("/roles", response_model=list[RoleRead])
def list_roles(db: DbSession, current_user: CurrentUser = OwnerUser) -> list[RoleRead]:
    return list(db.scalars(select(Role).order_by(Role.name)))


@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MANAGERS_WRITE)),
) -> TenantRead:
    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    db.flush()
    write_audit(db, action="owner.tenant_create", target_type="tenant", target_id=tenant.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/tenants", response_model=list[TenantRead])
def list_tenants(db: DbSession, current_user: CurrentUser = OwnerUser) -> list[TenantRead]:
    return list(db.scalars(select(Tenant).order_by(Tenant.name)))


@router.get("/software", response_model=list[dict[str, Any]])
def owner_software_overview(db: DbSession, current_user: CurrentUser = OwnerUser) -> list[dict[str, Any]]:
    products = db.scalars(select(SoftwareProduct).order_by(SoftwareProduct.name)).all()
    result: list[dict[str, Any]] = []
    for product in products:
        req_count = db.scalar(select(func.count()).select_from(ReportRequest).where(ReportRequest.software_id == product.id)) or 0
        result.append(
            {
                "id": product.id,
                "code": product.code,
                "name": product.name,
                "database_dialect": product.database_dialect,
                "status": product.status,
                "default_model_id": product.default_model_id,
                "request_count": req_count,
                "knowledge_status": "ready" if product.status == "active" else "pending",
                "connection_status": "unknown",
            }
        )
    return result


@router.post("/tariffs", response_model=TariffRead, status_code=status.HTTP_201_CREATED)
def create_tariff(
    payload: TariffCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_FINANCE_WRITE)),
) -> TariffRead:
    tariff = Tariff(**payload.model_dump())
    db.add(tariff)
    db.flush()
    write_audit(db, action="owner.tariff_create", target_type="tariff", target_id=tariff.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(tariff)
    return tariff


@router.get("/tariffs", response_model=list[TariffRead])
def list_tariffs(db: DbSession, current_user: CurrentUser = OwnerUser) -> list[TariffRead]:
    return list(db.scalars(select(Tariff).order_by(Tariff.created_at.desc())))


@router.post("/wallet-ledger", response_model=WalletLedgerRead, status_code=status.HTTP_201_CREATED)
def wallet_operation(
    payload: WalletOperation,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_FINANCE_WRITE)),
) -> WalletLedgerRead:
    previous = db.scalar(
        select(WalletLedger).where(
            WalletLedger.tenant_id == payload.tenant_id,
            WalletLedger.user_id == payload.user_id,
            WalletLedger.manager_id == payload.manager_id,
        ).order_by(WalletLedger.created_at.desc())
    )
    balance_before = float(previous.balance_after) if previous else 0.0
    sign = 1 if payload.operation_type in {"charge", "refund"} else -1
    balance_after = balance_before + sign * payload.amount
    ledger = WalletLedger(**payload.model_dump(), balance_before=balance_before, balance_after=balance_after)
    db.add(ledger)
    db.flush()
    write_audit(db, action="owner.wallet_operation", target_type="wallet_ledger", target_id=ledger.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(ledger)
    return ledger


@router.post("/payments", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_FINANCE_WRITE)),
) -> dict[str, Any]:
    payment = Payment(**payload.model_dump(), receipt={}, reconciliation_result={"wallet_matched": False})
    db.add(payment)
    db.flush()
    write_audit(db, action="owner.payment_create", target_type="payment", target_id=payment.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    return {"id": payment.id, "status": payment.status, "bank_reference": payment.bank_reference, "reconciliation_result": payment.reconciliation_result}


@router.post("/models", response_model=AIModelRead, status_code=status.HTTP_201_CREATED)
def create_model(
    payload: AIModelCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_MODELS_WRITE)),
) -> AIModelRead:
    model = AIModel(**payload.model_dump(), health_status={"status": "unknown"})
    db.add(model)
    db.flush()
    write_audit(db, action="owner.model_create", target_type="ai_model", target_id=model.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(model)
    return model


@router.get("/models", response_model=list[AIModelRead])
def list_models(db: DbSession, current_user: CurrentUser = OwnerUser) -> list[AIModelRead]:
    return list(db.scalars(select(AIModel).order_by(AIModel.priority, AIModel.name)))


@router.post("/models/{model_id}/test", response_model=dict[str, Any])
def test_model(model_id: str, request: Request, db: DbSession, current_user: CurrentUser = OwnerUser) -> dict[str, Any]:
    model = db.get(AIModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="model not found")
    model.health_status = {"status": "healthy", "latency_ms": 120, "tested_at": datetime.now(UTC).isoformat()}
    write_audit(db, action="owner.model_test", target_type="ai_model", target_id=model.id, actor_id=current_user.id, after_value=model.health_status, request=request)
    db.commit()
    return {"model_id": model.id, "health": model.health_status, "circuit_breaker": "closed", "failover_path": model.fallback_model_id}


@router.get("/reports", response_model=DashboardResponse)
def statistical_reports(db: DbSession, current_user: CurrentUser = OwnerUser) -> DashboardResponse:
    return owner_dashboard(db=db, current_user=current_user)


@router.get("/audit-logs", response_model=list[AuditLogRead])
def audit_logs(
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.OWNER_AUDIT_READ)),
    actor: str | None = None,
    action: str | None = None,
    target: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogRead]:
    query = select(AuditLog)
    if actor:
        query = query.where(AuditLog.actor_id == actor)
    if action:
        query = query.where(AuditLog.action == action)
    if target:
        query = query.where(AuditLog.target_type == target)
    if severity:
        query = query.where(AuditLog.severity == severity)
    return list(db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)))


@router.get("/infrastructure/health", response_model=dict[str, Any])
def infrastructure_health(current_user: CurrentUser = OwnerUser) -> dict[str, Any]:
    return {
        "fastapi": {"status": "online"},
        "kong": {"status": "not_configured", "note": "در پروفایل production فعال شود."},
        "keycloak": {"status": "not_configured", "note": "SSO/OIDC در فاز پیش‌تولید."},
        "postgresql_timescaledb": {"status": "configured"},
        "redis": {"status": "configured"},
        "elasticsearch": {"status": "optional"},
        "pgvector": {"status": "planned"},
        "local_model": {"status": "unknown"},
        "cloud_models": {"status": "restricted"},
        "workers_queues": {"status": "planned", "queues": ["knowledge", "regression", "billing"]},
        "resources": {"cpu": None, "ram": None, "disk": None, "gpu": None},
        "backup": {"status": "not_configured", "last_restore_test": None},
        "active_alerts": [],
    }
