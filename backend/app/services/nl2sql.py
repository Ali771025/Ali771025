from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.security.access_control import AccessControlService
from app.application.security.billing import TokenAccountingService
from app.core.security import redact
from app.models.domain import ReportRequest, SoftwareProduct, SoftwareVersion, Tenant, User
from app.schemas.domain import (
    Confidence,
    DisplaySpec,
    ReportClarification,
    ReportPolicy,
    ReportRejected,
    ReportRequestIn,
    ReportSuccess,
)
from app.services.audit import new_audit_id, write_audit
from app.services.knowledge import checksum

DANGEROUS_SQL_RE = re.compile(r"\b(drop|truncate|delete|update|insert|alter|exec|merge)\b", re.IGNORECASE)
SUBJECT_KEYWORDS: dict[str, dict[str, Any]] = {
    "commission100": {
        "keywords": ["ماده 100", "ماده ۱۰۰", "کمیسیون", "commission100"],
        "required_scope": "commission100.read",
        "table": "dbo.Commission100Cases",
        "title": "گزارش پرونده‌های ماده ۱۰۰",
        "intent": "commission100_cases",
    },
    "permit": {
        "keywords": ["پروانه", "مجوز", "permit"],
        "required_scope": "permits.read",
        "table": "dbo.Permits",
        "title": "گزارش پروانه‌ها",
        "intent": "permits",
    },
    "payment": {
        "keywords": ["پرداخت", "عوارض", "فیش", "payment"],
        "required_scope": "payments.read",
        "table": "dbo.Payments",
        "title": "گزارش پرداخت‌ها",
        "intent": "payments",
    },
}


def _detect_subject(question: str) -> dict[str, Any] | None:
    normalized = question.replace("ي", "ی").replace("ك", "ک").lower()
    for subject in SUBJECT_KEYWORDS.values():
        if any(keyword.lower() in normalized for keyword in subject["keywords"]):
            return subject
    return None


def _needs_clarification(question: str) -> bool:
    normalized = question.replace("ي", "ی").replace("ك", "ک")
    has_last = "آخرین" in normalized or "اخیر" in normalized
    has_target = any(term in normalized for term in ["پرونده", "رأی", "رای", "تغییر وضعیت", "ثبت"])
    return has_last and not has_target


def _extract_limit(question: str, max_rows: int) -> int:
    digit_match = re.search(r"\b(\d{1,4})\b", question)
    if digit_match:
        return max(1, min(int(digit_match.group(1)), max_rows))
    persian_digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    translated = question.translate(persian_digits)
    digit_match = re.search(r"\b(\d{1,4})\b", translated)
    if digit_match:
        return max(1, min(int(digit_match.group(1)), max_rows))
    return min(20, max_rows)


def _build_sql(subject: dict[str, Any], limit: int, access_context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    regions = access_context.get("region") or []
    where = ["1 = 1"]
    parameters: dict[str, Any] = {"limit": limit}
    if regions:
        where.append("RegionCode IN @regions")
        parameters["regions"] = regions
    sql = (
        "SELECT TOP (@limit) CaseNo, RegionCode, CreatedAt, Status "
        f"FROM {subject['table']} WHERE {' AND '.join(where)} ORDER BY CreatedAt DESC"
    )
    return sql, parameters


def generate_report_contract(
    db: Session,
    payload: ReportRequestIn,
    *,
    idempotency_key: str | None = None,
) -> ReportSuccess | ReportClarification | ReportRejected:
    started = time.perf_counter()
    audit_id = new_audit_id()
    request_uuid = str(payload.request_id)
    access_context = payload.access_context.model_dump()
    question_redacted = redact(payload.question)

    software = db.scalar(select(SoftwareProduct).where(SoftwareProduct.code == payload.software_id))
    tenant = None
    user = db.scalar(
        select(User).where(
            (User.external_user_id == payload.user_id)
            | (User.username == payload.user_id)
            | (User.id == payload.user_id)
        )
    )
    if software and software.tenant_id:
        tenant = db.get(Tenant, software.tenant_id)
    if not tenant and access_context.get("organization"):
        tenant = db.scalar(select(Tenant).where(Tenant.code == access_context.get("organization")))

    version = None
    if software:
        version = db.scalar(
            select(SoftwareVersion).where(
                SoftwareVersion.software_id == software.id,
                SoftwareVersion.version_number == payload.software_version,
            )
        )

    policy = ReportPolicy(
        max_rows=int((software.access_policy or {}).get("max_rows", 20)) if software else 20,
        timeout_seconds=int((software.access_policy or {}).get("timeout_seconds", 10)) if software else 10,
        knowledge_hash=(version.version_hash if version and version.version_hash else checksum(f"{payload.software_id}:{payload.software_version}")),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
    )

    def persist(status: str, **kwargs: Any) -> None:
        report = ReportRequest(
            id=request_uuid,
            tenant_id=software.tenant_id if software else None,
            software_id=software.id if software else None,
            version_id=version.id if version else None,
            external_software_id=payload.software_id,
            software_version=payload.software_version,
            user_id=payload.user_id,
            question_redacted=str(question_redacted),
            access_context=access_context,
            locale=payload.locale,
            timezone=payload.timezone,
            status=status,
            audit_id=audit_id,
            response_time_ms=int((time.perf_counter() - started) * 1000),
            policy=policy.model_dump(mode="json"),
            **kwargs,
        )
        db.merge(report)
        write_audit(
            db,
            audit_id=audit_id,
            action="report.generate",
            target_type="report_request",
            target_id=request_uuid,
            tenant_id=software.tenant_id if software else None,
            software_id=software.id if software else None,
            version_id=version.id if version else None,
            actor_id=payload.user_id,
            after_value={"status": status, "request": payload.model_dump(mode="json"), **kwargs},
            result="success" if status in {"success", "needs_clarification"} else "rejected",
            rejection_reason=kwargs.get("rejection_reason_code"),
            request_id=request_uuid,
        )
        db.commit()

    if not software:
        persist(status="rejected", rejection_reason_code="UNKNOWN_SOFTWARE")
        return ReportRejected(
            audit_id=audit_id,
            reason_code="UNKNOWN_SOFTWARE",
            message="نرم‌افزار یا Tenant ارسالی در سامانه ثبت نشده است.",
        )

    if DANGEROUS_SQL_RE.search(payload.question):
        persist(status="rejected", rejection_reason_code="UNSAFE_REQUEST", risk_level="high")
        return ReportRejected(
            audit_id=audit_id,
            reason_code="UNSAFE_REQUEST",
            message="درخواست شامل عملیات غیرمجاز یا پرریسک است.",
        )

    subject = _detect_subject(payload.question)
    if subject is None:
        persist(status="rejected", rejection_reason_code="OUT_OF_SCOPE")
        return ReportRejected(
            audit_id=audit_id,
            reason_code="OUT_OF_SCOPE",
            message="این درخواست خارج از سطح دسترسی یا حوزه نرم‌افزار است.",
        )

    required_scope = subject["required_scope"]
    requested_limit = _extract_limit(payload.question, policy.max_rows)
    access_decision = AccessControlService().evaluate_report_access(
        tenant=tenant,
        software=software,
        user=user,
        external_user_id=payload.user_id,
        access_context=access_context,
        required_scope=required_scope,
        requested_limit=requested_limit,
    )
    if not access_decision.allowed:
        persist(
            status="rejected",
            rejection_reason_code=access_decision.reason_code or "ACCESS_DENIED",
            risk_level="medium",
            intent=subject["intent"],
            validator_result={
                "access_decision": access_decision.reason_code,
                "effective_permissions": sorted(access_decision.effective_permissions),
                "effective_scopes": sorted(access_decision.effective_scopes),
            },
        )
        return ReportRejected(
            audit_id=audit_id,
            reason_code=access_decision.reason_code or "ACCESS_DENIED",
            message=access_decision.message or "سطح دسترسی کاربر برای این موضوع کافی نیست.",
        )

    policy.max_rows = access_decision.max_rows
    policy.timeout_seconds = access_decision.timeout_seconds
    policy.policy_hash = access_decision.policy_hash
    policy.access_fingerprint = access_decision.access_fingerprint

    if _needs_clarification(payload.question):
        options = ["آخرین پرونده", "آخرین رأی", "آخرین تغییر وضعیت"]
        question = "منظور شما آخرین پرونده، آخرین رأی یا آخرین تغییر وضعیت است؟"
        persist(
            status="needs_clarification",
            intent=subject["intent"],
            clarification_question=question,
            clarification_options=options,
            confidence_score=0.52,
            confidence_level="low",
        )
        return ReportClarification(audit_id=audit_id, question=question, options=options)

    limit = min(requested_limit, policy.max_rows)
    billing = TokenAccountingService().authorize_and_debit(
        db,
        tenant=tenant,
        user=user,
        software_id=software.id if software else None,
        question=payload.question,
        idempotency_key=idempotency_key or request_uuid,
        cache_hit=False,
        metadata={"request_id": request_uuid, "audit_id": audit_id},
    )
    if not billing.allowed:
        policy.estimated_cost = billing.estimated_cost
        policy.balance_after = billing.balance_after
        policy.prompt_tokens = billing.prompt_tokens
        policy.completion_tokens = billing.completion_tokens
        persist(
            status="rejected",
            rejection_reason_code=billing.reason_code or "INSUFFICIENT_CREDIT",
            risk_level="medium",
            intent=subject["intent"],
            prompt_tokens=billing.prompt_tokens,
            completion_tokens=billing.completion_tokens,
            cost_amount=billing.estimated_cost,
            validator_result={"billing": billing.reason_code, "balance_before": billing.balance_before},
        )
        return ReportRejected(
            audit_id=audit_id,
            reason_code=billing.reason_code or "INSUFFICIENT_CREDIT",
            message=billing.message or "اعتبار کافی وجود ندارد.",
        )

    policy.estimated_cost = billing.estimated_cost
    policy.balance_after = billing.balance_after
    policy.prompt_tokens = billing.prompt_tokens
    policy.completion_tokens = billing.completion_tokens
    sql, parameters = _build_sql(subject, limit, access_context)
    display = DisplaySpec(
        type="table",
        title=subject["title"],
        columns=[
            {"name": "CaseNo", "title": "شماره پرونده"},
            {"name": "RegionCode", "title": "منطقه"},
            {"name": "CreatedAt", "title": "تاریخ ثبت"},
            {"name": "Status", "title": "وضعیت"},
        ],
        formats={"CreatedAt": "jalali-date"},
    )
    confidence = Confidence(score=0.94, level="high")
    persist(
        status="success",
        intent=subject["intent"],
        entities={"subject": subject["intent"], "limit": limit},
        generated_sql=sql,
        parameters=parameters,
        display_spec=display.model_dump(mode="json"),
        confidence_score=confidence.score,
        confidence_level=confidence.level,
        validator_result={
            "safe": True,
            "parameterized": True,
            "max_rows_enforced": True,
            "policy_hash": access_decision.policy_hash,
            "access_fingerprint": access_decision.access_fingerprint,
            "billing_ledger_id": billing.ledger_id,
            "balance_before": billing.balance_before,
            "balance_after": billing.balance_after,
            "tariff_id": billing.tariff_id,
        },
        prompt_tokens=billing.prompt_tokens,
        completion_tokens=billing.completion_tokens,
        cost_amount=billing.estimated_cost,
        cache_hit=False,
    )
    return ReportSuccess(sql=sql, parameters=parameters, display=display, confidence=confidence, audit_id=audit_id, policy=policy)


def validate_connector_sql(sql: str, max_rows: int) -> tuple[bool, str | None]:
    if DANGEROUS_SQL_RE.search(sql):
        return False, "SQL شامل عملیات نوشتن یا تخریب است."
    normalized = sql.lower()
    if "select" not in normalized:
        return False, "فقط SELECT مجاز است."
    if "top" not in normalized and "limit" not in normalized and max_rows:
        return False, "سقف ردیف باید در SQL اعمال شود."
    return True, None
