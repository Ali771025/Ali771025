from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_current_user
from app.models.domain import BackgroundJob
from app.schemas.domain import BackgroundJobRead
from app.services.audit import write_audit

router = APIRouter(prefix="/notifications", tags=["اعلان‌ها و کارهای پس‌زمینه"])


@router.get("/jobs", response_model=list[BackgroundJobRead])
def list_jobs(db: DbSession, current_user: CurrentUser = Depends(get_current_user), status_filter: str | None = None) -> list[BackgroundJobRead]:
    query = select(BackgroundJob)
    if current_user.tenant_id:
        query = query.where(BackgroundJob.tenant_id == current_user.tenant_id)
    if status_filter:
        query = query.where(BackgroundJob.status == status_filter)
    return list(db.scalars(query.order_by(BackgroundJob.created_at.desc()).limit(100)))


@router.post("/jobs/demo", response_model=BackgroundJobRead, status_code=status.HTTP_201_CREATED)
def create_demo_job(kind: str, request: Request, db: DbSession, current_user: CurrentUser = Depends(get_current_user)) -> BackgroundJobRead:
    job = BackgroundJob(
        tenant_id=current_user.tenant_id,
        kind=kind,
        related_type="demo",
        related_id="demo",
        status="queued",
        progress_percent=0,
        link="/software-admin/knowledge",
    )
    db.add(job)
    db.flush()
    write_audit(db, action="job.queue", target_type="background_job", target_id=job.id, actor_id=current_user.id, tenant_id=current_user.tenant_id, after_value={"kind": kind}, request=request)
    db.commit()
    db.refresh(job)
    return job
