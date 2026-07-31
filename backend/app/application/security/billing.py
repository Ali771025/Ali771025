from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import ReportRequest, Tariff, Tenant, User, WalletLedger


@dataclass(frozen=True, slots=True)
class BillingDecision:
    allowed: bool
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    balance_before: float
    balance_after: float
    ledger_id: str | None = None
    reason_code: str | None = None
    message: str | None = None
    tariff_id: str | None = None


class TokenAccountingService:
    """Token estimation, tariff calculation and immutable wallet ledger debit."""

    def estimate_tokens(self, *, question: str, retrieved_documents: int = 4, sql_complexity: int = 1) -> tuple[int, int]:
        # فارسی tokenization is approximate; this intentionally overestimates for quota safety.
        prompt_tokens = max(120, math.ceil(len(question) / 2.6) + retrieved_documents * 140 + sql_complexity * 80)
        completion_tokens = max(80, min(700, math.ceil(prompt_tokens * 0.34)))
        return prompt_tokens, completion_tokens

    def active_tariff(self, db: Session, *, tenant: Tenant | None = None, software_id: str | None = None) -> Tariff | None:
        now = datetime.now(UTC)
        tariffs = list(db.scalars(select(Tariff).where(Tariff.status == "active").order_by(Tariff.created_at.desc())))
        for tariff in tariffs:
            if tariff.starts_at and tariff.starts_at > now:
                continue
            if tariff.ends_at and tariff.ends_at < now:
                continue
            applies_to = tariff.applies_to or {}
            tenant_ids = set(applies_to.get("tenant_ids") or [])
            software_ids = set(applies_to.get("software_ids") or [])
            if tenant_ids and tenant and tenant.id not in tenant_ids:
                continue
            if software_ids and software_id and software_id not in software_ids:
                continue
            return tariff
        return None

    def estimate_cost(self, *, tariff: Tariff | None, prompt_tokens: int, completion_tokens: int, cache_hit: bool = False) -> float:
        if cache_hit and tariff:
            return float(tariff.cached_request_price or 0)
        input_cost = float(tariff.input_token_cost) if tariff else 0.00002
        output_cost = float(tariff.output_token_cost) if tariff else 0.00004
        minimum = float(tariff.minimum_cost) if tariff else 0.001
        cost = prompt_tokens * input_cost + completion_tokens * output_cost
        return round(max(cost, minimum), 6)

    def current_balance(self, db: Session, *, tenant: Tenant | None = None, user: User | None = None) -> float:
        ledger = db.scalar(
            select(WalletLedger)
            .where(
                WalletLedger.tenant_id == (tenant.id if tenant else None),
                WalletLedger.user_id == (user.id if user else None),
                WalletLedger.manager_id.is_(None),
            )
            .order_by(WalletLedger.created_at.desc())
        )
        return float(ledger.balance_after) if ledger else 0.0


    def quota_violation(
        self,
        db: Session,
        *,
        tenant: Tenant | None,
        user: User | None,
        estimated_cost: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[str, str] | None:
        now = datetime.now(UTC)
        day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        user_identities = []
        if user:
            user_identities = [identity for identity in [user.id, user.username, user.external_user_id] if identity]

        def base_query(start: datetime):
            query = select(ReportRequest).where(ReportRequest.created_at >= start)
            if tenant:
                query = query.where(ReportRequest.tenant_id == tenant.id)
            if user_identities:
                query = query.where(ReportRequest.user_id.in_(user_identities))
            return query

        daily_count = len(list(db.scalars(base_query(day_start))))
        monthly_count = len(list(db.scalars(base_query(month_start))))
        daily_cost = float(
            db.scalar(
                select(func.coalesce(func.sum(ReportRequest.cost_amount), 0)).where(
                    ReportRequest.created_at >= day_start,
                    ReportRequest.tenant_id == (tenant.id if tenant else None),
                )
            )
            or 0
        )
        monthly_cost = float(
            db.scalar(
                select(func.coalesce(func.sum(ReportRequest.cost_amount), 0)).where(
                    ReportRequest.created_at >= month_start,
                    ReportRequest.tenant_id == (tenant.id if tenant else None),
                )
            )
            or 0
        )

        if user and user.daily_quota is not None and daily_count >= user.daily_quota:
            return "USER_DAILY_QUOTA_EXCEEDED", "سقف روزانه درخواست کاربر تکمیل شده است."
        if user and user.monthly_quota is not None and monthly_count >= user.monthly_quota:
            return "USER_MONTHLY_QUOTA_EXCEEDED", "سقف ماهانه درخواست کاربر تکمیل شده است."

        policy = tenant.security_policy if tenant else {}
        daily_request_limit = policy.get("daily_request_limit")
        monthly_request_limit = policy.get("monthly_request_limit")
        daily_cost_limit = policy.get("daily_cost_limit")
        monthly_cost_limit = policy.get("monthly_cost_limit")
        daily_token_limit = policy.get("daily_token_limit")
        token_estimate = prompt_tokens + completion_tokens

        if daily_request_limit is not None and daily_count >= int(daily_request_limit):
            return "TENANT_DAILY_REQUEST_LIMIT_EXCEEDED", "سقف روزانه درخواست سازمان تکمیل شده است."
        if monthly_request_limit is not None and monthly_count >= int(monthly_request_limit):
            return "TENANT_MONTHLY_REQUEST_LIMIT_EXCEEDED", "سقف ماهانه درخواست سازمان تکمیل شده است."
        if daily_cost_limit is not None and daily_cost + estimated_cost > float(daily_cost_limit):
            return "TENANT_DAILY_COST_LIMIT_EXCEEDED", "سقف هزینه روزانه سازمان تکمیل شده است."
        if monthly_cost_limit is not None and monthly_cost + estimated_cost > float(monthly_cost_limit):
            return "TENANT_MONTHLY_COST_LIMIT_EXCEEDED", "سقف هزینه ماهانه سازمان تکمیل شده است."
        if daily_token_limit is not None:
            daily_tokens = int(
                db.scalar(
                    select(func.coalesce(func.sum(ReportRequest.prompt_tokens + ReportRequest.completion_tokens), 0)).where(
                        ReportRequest.created_at >= day_start,
                        ReportRequest.tenant_id == (tenant.id if tenant else None),
                    )
                )
                or 0
            )
            if daily_tokens + token_estimate > int(daily_token_limit):
                return "TENANT_DAILY_TOKEN_LIMIT_EXCEEDED", "سقف Token روزانه سازمان تکمیل شده است."
        return None

    def authorize_and_debit(
        self,
        db: Session,
        *,
        tenant: Tenant | None,
        user: User | None,
        software_id: str | None,
        question: str,
        idempotency_key: str | None,
        cache_hit: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> BillingDecision:
        prompt_tokens, completion_tokens = self.estimate_tokens(question=question)
        tariff = self.active_tariff(db, tenant=tenant, software_id=software_id)
        estimated_cost = self.estimate_cost(
            tariff=tariff,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hit=cache_hit,
        )
        if idempotency_key:
            existing = db.scalar(select(WalletLedger).where(WalletLedger.financial_reference == idempotency_key))
            if existing:
                return BillingDecision(
                    allowed=True,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    estimated_cost=float(existing.amount),
                    balance_before=float(existing.balance_before),
                    balance_after=float(existing.balance_after),
                    ledger_id=existing.id,
                    tariff_id=tariff.id if tariff else None,
                )

        quota_violation = self.quota_violation(
            db,
            tenant=tenant,
            user=user,
            estimated_cost=estimated_cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if quota_violation:
            reason_code, message = quota_violation
            return BillingDecision(
                allowed=False,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost=estimated_cost,
                balance_before=self.current_balance(db, tenant=tenant, user=user),
                balance_after=self.current_balance(db, tenant=tenant, user=user),
                reason_code=reason_code,
                message=message,
                tariff_id=tariff.id if tariff else None,
            )

        balance_before = self.current_balance(db, tenant=tenant, user=user)
        balance_after = round(balance_before - estimated_cost, 6)
        if balance_after < 0:
            return BillingDecision(
                allowed=False,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost=estimated_cost,
                balance_before=balance_before,
                balance_after=balance_before,
                reason_code="INSUFFICIENT_CREDIT",
                message="اعتبار کافی برای تولید گزارش وجود ندارد.",
                tariff_id=tariff.id if tariff else None,
            )

        ledger = WalletLedger(
            tenant_id=tenant.id if tenant else None,
            user_id=user.id if user else None,
            operation_type="deduct",
            amount=estimated_cost,
            balance_before=balance_before,
            balance_after=balance_after,
            financial_reference=idempotency_key or f"report-{uuid.uuid4()}",
            description="NL2SQL report token usage debit",
            consumed_amount=estimated_cost,
            reserved_amount=0,
        )
        if metadata:
            ledger.description = f"{ledger.description} | {metadata}"
        db.add(ledger)
        db.flush()
        return BillingDecision(
            allowed=True,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=estimated_cost,
            balance_before=balance_before,
            balance_after=balance_after,
            ledger_id=ledger.id,
            tariff_id=tariff.id if tariff else None,
        )
