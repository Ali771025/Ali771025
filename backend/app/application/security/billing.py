from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Tariff, Tenant, User, WalletLedger


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
