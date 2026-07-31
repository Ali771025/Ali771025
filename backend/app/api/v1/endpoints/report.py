from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.domain import Feedback, ReportRequest
from app.schemas.domain import (
    FeedbackRead,
    ReportExecutionResultIn,
    ReportRequestIn,
    ReportResponse,
    StatusMessage,
    UserFeedbackCreate,
)
from app.services.audit import write_audit
from app.services.nl2sql import generate_report_contract

router = APIRouter(prefix="/reports", tags=["رابط کاربر On-Premise و قرارداد NL2SQL"])


@router.post("/generate", response_model=ReportResponse)
def generate_report(payload: ReportRequestIn, db: DbSession) -> ReportResponse:
    """
    Main NL2SQL API contract.

    It returns parameterized SQL and display metadata only. Raw local query results must never be
    sent back to the central service.
    """

    return generate_report_contract(db, payload)


@router.post("/execution-result", response_model=StatusMessage)
def report_execution_result(payload: ReportExecutionResultIn, request: Request, db: DbSession) -> StatusMessage:
    report = db.scalar(select(ReportRequest).where(ReportRequest.audit_id == payload.audit_id))
    if report:
        report.validator_result = {
            **(report.validator_result or {}),
            "local_execution": {
                "execution_time_ms": payload.execution_time_ms,
                "row_count": payload.row_count,
                "display_type": payload.display_type,
                "raw_data_received": False,
            },
        }
        write_audit(
            db,
            audit_id=payload.audit_id,
            action="report.local_execution_metadata",
            target_type="report_request",
            target_id=report.id,
            actor_id=report.user_id,
            software_id=report.software_id,
            version_id=report.version_id,
            after_value=payload.model_dump(mode="json"),
            request=request,
        )
        db.commit()
    return StatusMessage(status="completed", message="متادیتای اجرای محلی بدون داده خام ثبت شد.")


@router.post("/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def user_feedback(payload: UserFeedbackCreate, request: Request, db: DbSession) -> FeedbackRead:
    feedback = Feedback(
        audit_id=payload.audit_id,
        user_verdict=payload.verdict,
        rating=payload.rating,
        description=payload.description,
        problem_type=payload.problem_type,
        manager_review_requested=payload.manager_review_requested,
        review_status="queued" if payload.manager_review_requested else "received",
    )
    db.add(feedback)
    db.flush()
    write_audit(
        db,
        audit_id=payload.audit_id,
        action="feedback.user_submit",
        target_type="feedback",
        target_id=feedback.id,
        after_value=payload.model_dump(mode="json"),
        request=request,
    )
    db.commit()
    db.refresh(feedback)
    return feedback
