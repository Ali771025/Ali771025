from __future__ import annotations

import difflib
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.rbac import Permission, require_permissions
from app.core.security import api_key_prefix, get_password_hash
from app.models.domain import (
    APIKey,
    Feedback,
    GoldTest,
    KnowledgeDocument,
    KnowledgeSnapshot,
    ModelPolicy,
    Recipe,
    ReportRequest,
    Role,
    SchemaRelation,
    SoftwareProduct,
    SoftwareVersion,
    User,
)
from app.schemas.domain import (
    APIKeyCreate,
    APIKeyIssued,
    APIKeyRead,
    DashboardMetric,
    DashboardResponse,
    FeedbackRead,
    GoldTestCreate,
    GoldTestRead,
    GoldTestRunResult,
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    KnowledgeStandardizeRequest,
    KnowledgeStandardizeResult,
    ModelPolicyCreate,
    QualityReviewCreate,
    RecipeCreate,
    RecipeRead,
    RequestDetailRead,
    RequestMonitorRead,
    RoleCreate,
    RoleRead,
    SchemaRelationCreate,
    SchemaRelationRead,
    SnapshotPublishRequest,
    SnapshotRead,
    SoftwareCreate,
    SoftwareRead,
    SoftwareUserCreate,
    UserRead,
    VersionCreate,
    VersionRead,
)
from app.services.audit import write_audit
from app.services.knowledge import checksum, detect_document_type, extract_metadata, validate_knowledge
from app.services.nl2sql import generate_report_contract

router = APIRouter(prefix="/software-admin", tags=["پنل مدیر نرم‌افزار"])
SoftwareAdmin = Depends(require_permissions(Permission.SOFTWARE_READ))


@router.get("/dashboard", response_model=DashboardResponse)
def software_dashboard(
    db: DbSession,
    current_user: CurrentUser = SoftwareAdmin,
    software_id: str | None = None,
    version_id: str | None = None,
) -> DashboardResponse:
    software_query = select(SoftwareProduct)
    if software_id:
        software_query = software_query.where(SoftwareProduct.id == software_id)
    products = db.scalars(software_query).all()
    product_ids = [item.id for item in products]

    version_query = select(SoftwareVersion)
    if product_ids:
        version_query = version_query.where(SoftwareVersion.software_id.in_(product_ids))
    if version_id:
        version_query = version_query.where(SoftwareVersion.id == version_id)
    versions = db.scalars(version_query).all()
    version_ids = [item.id for item in versions]

    docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.version_id.in_(version_ids)) if version_ids else select(KnowledgeDocument).where(False)).all()
    requests = db.scalars(select(ReportRequest).where(ReportRequest.software_id.in_(product_ids)) if product_ids else select(ReportRequest).where(False)).all()
    users = db.scalars(select(User).where(User.tenant_id == current_user.tenant_id) if current_user.tenant_id else select(User)).all()
    snapshots = db.scalars(select(KnowledgeSnapshot).where(KnowledgeSnapshot.version_id.in_(version_ids)) if version_ids else select(KnowledgeSnapshot).where(False)).all()

    success = sum(1 for item in requests if item.status == "success")
    return DashboardResponse(
        filters={"software_id": software_id, "version_id": version_id},
        metrics=[
            DashboardMetric(label="نسخه فعال", value=next((v.version_number for v in versions if v.status == "active"), "ندارد")),
            DashboardMetric(label="آخرین Snapshot", value=next((s.name for s in sorted(snapshots, key=lambda x: x.created_at, reverse=True)), "ندارد")),
            DashboardMetric(label="فایل‌های تأییدشده", value=sum(1 for doc in docs if doc.approval_status == "approved")),
            DashboardMetric(label="تعارض‌ها و خطاها", value=sum(len(doc.errors or []) for doc in docs)),
            DashboardMetric(label="کاربران", value=len(users)),
            DashboardMetric(label="مصرف و درخواست", value=len(requests)),
            DashboardMetric(label="نرخ موفقیت", value=round(success / len(requests) * 100, 2) if requests else 0),
            DashboardMetric(label="نیازمند بازبینی", value=sum(1 for item in requests if item.status in {"needs_review", "needs_clarification"})),
        ],
        charts={"request_status": {}, "knowledge_quality": []},
        alerts=[{"severity": "info", "message": "وضعیت Connector و مدل از مسیرهای مربوطه قابل مشاهده است."}],
    )


@router.post("/software", response_model=SoftwareRead, status_code=status.HTTP_201_CREATED)
def create_software(
    payload: SoftwareCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.SOFTWARE_WRITE)),
) -> SoftwareRead:
    if db.scalar(select(SoftwareProduct).where(SoftwareProduct.code == payload.code)):
        raise HTTPException(status_code=409, detail="software code already exists")
    product = SoftwareProduct(**payload.model_dump())
    db.add(product)
    db.flush()
    write_audit(db, action="software.create", target_type="software", target_id=product.id, actor_id=current_user.id, tenant_id=payload.tenant_id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(product)
    return product


@router.get("/software", response_model=list[SoftwareRead])
def list_software(db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[SoftwareRead]:
    query = select(SoftwareProduct).order_by(SoftwareProduct.name)
    if current_user.tenant_id:
        query = query.where((SoftwareProduct.tenant_id == current_user.tenant_id) | (SoftwareProduct.tenant_id.is_(None)))
    return list(db.scalars(query))


@router.patch("/software/{software_id}", response_model=SoftwareRead)
def update_software(
    software_id: str,
    payload: SoftwareCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.SOFTWARE_WRITE)),
) -> SoftwareRead:
    product = db.get(SoftwareProduct, software_id)
    if not product:
        raise HTTPException(status_code=404, detail="software not found")
    before = {"code": product.code, "name": product.name, "status": product.status}
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    write_audit(db, action="software.update", target_type="software", target_id=product.id, actor_id=current_user.id, before_value=before, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(product)
    return product


@router.post("/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED)
def create_version(
    payload: VersionCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.SOFTWARE_WRITE)),
) -> VersionRead:
    version = SoftwareVersion(**payload.model_dump(), version_hash=checksum(f"{payload.software_id}:{payload.version_number}"))
    db.add(version)
    db.flush()
    write_audit(db, action="software.version_create", target_type="software_version", target_id=version.id, actor_id=current_user.id, software_id=payload.software_id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(version)
    return version


@router.get("/software/{software_id}/versions", response_model=list[VersionRead])
def list_versions(software_id: str, db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[VersionRead]:
    return list(db.scalars(select(SoftwareVersion).where(SoftwareVersion.software_id == software_id).order_by(SoftwareVersion.created_at.desc())))


@router.post("/knowledge", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
def upload_knowledge(
    payload: KnowledgeDocumentCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.KNOWLEDGE_WRITE)),
) -> KnowledgeDocumentRead:
    detected = detect_document_type(payload.content, payload.document_type)
    metadata = extract_metadata(payload.content)
    quality_score, errors, warnings = validate_knowledge(payload.content, payload.document_type)
    document = KnowledgeDocument(
        **payload.model_dump(),
        checksum=checksum(payload.content),
        detected_type=detected,
        extracted_metadata=metadata,
        quality_score=quality_score,
        errors=errors,
        warnings=warnings,
        approval_status="review" if errors or warnings else "approved",
    )
    db.add(document)
    db.flush()
    write_audit(db, action="knowledge.upload", target_type="knowledge_document", target_id=document.id, actor_id=current_user.id, software_id=payload.software_id, version_id=payload.version_id, after_value={"title": payload.title, "checksum": document.checksum, "metadata": metadata}, request=request)
    db.commit()
    db.refresh(document)
    return document


@router.get("/knowledge", response_model=list[KnowledgeDocumentRead])
def list_knowledge(
    db: DbSession,
    current_user: CurrentUser = SoftwareAdmin,
    software_id: str | None = None,
    version_id: str | None = None,
    approval_status: str | None = None,
) -> list[KnowledgeDocumentRead]:
    query = select(KnowledgeDocument)
    if software_id:
        query = query.where(KnowledgeDocument.software_id == software_id)
    if version_id:
        query = query.where(KnowledgeDocument.version_id == version_id)
    if approval_status:
        query = query.where(KnowledgeDocument.approval_status == approval_status)
    return list(db.scalars(query.order_by(KnowledgeDocument.created_at.desc())))


@router.get("/knowledge/{document_id}", response_model=KnowledgeDocumentRead)
def get_knowledge(document_id: str, db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> KnowledgeDocumentRead:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.patch("/knowledge/{document_id}", response_model=KnowledgeDocumentRead)
def edit_knowledge(
    document_id: str,
    payload: KnowledgeDocumentCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.KNOWLEDGE_WRITE)),
) -> KnowledgeDocumentRead:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    previous_content = document.content
    before = {"checksum": document.checksum, "document_version": document.document_version}
    for key, value in payload.model_dump().items():
        setattr(document, key, value)
    document.document_version += 1
    document.checksum = checksum(payload.content)
    document.detected_type = detect_document_type(payload.content, payload.document_type)
    document.extracted_metadata = extract_metadata(payload.content)
    document.quality_score, document.errors, document.warnings = validate_knowledge(payload.content, payload.document_type)
    document.approval_status = "review"
    diff = "\n".join(difflib.unified_diff(previous_content.splitlines(), payload.content.splitlines(), fromfile="previous", tofile="current", lineterm=""))
    write_audit(db, action="knowledge.edit", target_type="knowledge_document", target_id=document.id, actor_id=current_user.id, before_value=before, after_value={"checksum": document.checksum, "diff": diff[:4000]}, request=request)
    db.commit()
    db.refresh(document)
    return document


@router.get("/knowledge/{document_id}/diff", response_model=dict[str, Any])
def knowledge_diff(document_id: str, compared_to_id: str, db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> dict[str, Any]:
    current = db.get(KnowledgeDocument, document_id)
    previous = db.get(KnowledgeDocument, compared_to_id)
    if not current or not previous:
        raise HTTPException(status_code=404, detail="document not found")
    diff = list(difflib.unified_diff(previous.content.splitlines(), current.content.splitlines(), fromfile=previous.title, tofile=current.title, lineterm=""))
    return {"document_id": document_id, "compared_to_id": compared_to_id, "diff": diff}


@router.post("/knowledge/standardize", response_model=KnowledgeStandardizeResult)
def standardize_knowledge(
    payload: KnowledgeStandardizeRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.KNOWLEDGE_WRITE)),
) -> KnowledgeStandardizeResult:
    documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(payload.document_ids))))
    blockers: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    seen_checksums: dict[str, str] = {}
    for document in documents:
        document.detected_type = detect_document_type(document.content, document.document_type)
        document.extracted_metadata = extract_metadata(document.content)
        document.quality_score, document.errors, document.warnings = validate_knowledge(document.content, document.document_type)
        if document.errors:
            blockers.extend({"document_id": document.id, **error} for error in document.errors)
            document.approval_status = "rejected"
        elif document.checksum in seen_checksums:
            conflicts.append({"document_id": document.id, "conflicts_with": seen_checksums[document.checksum], "code": "DUPLICATE_CHECKSUM"})
            document.approval_status = "conflict"
        else:
            seen_checksums[document.checksum] = document.id
            document.approval_status = "review" if document.warnings else "approved"
            if document.warnings:
                suggestions.append({"document_id": document.id, "message": "برای تأیید نهایی هشدارها را بازبینی کنید."})
    final_status = "conflict" if conflicts else "rejected" if blockers else "review" if suggestions else "approved"
    write_audit(db, action="knowledge.standardize", target_type="knowledge_batch", actor_id=current_user.id, software_id=payload.software_id, version_id=payload.version_id, after_value={"status": final_status, "blockers": blockers, "conflicts": conflicts}, request=request)
    db.commit()
    return KnowledgeStandardizeResult(status=final_status, documents=documents, blockers=blockers, conflicts=conflicts, suggestions=suggestions)


@router.post("/snapshots/publish", response_model=SnapshotRead, status_code=status.HTTP_201_CREATED)
def publish_snapshot(
    payload: SnapshotPublishRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.SNAPSHOT_PUBLISH)),
) -> SnapshotRead:
    documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(payload.document_ids))))
    if len(documents) != len(payload.document_ids):
        raise HTTPException(status_code=404, detail="some documents were not found")
    blockers = [doc.id for doc in documents if doc.errors or doc.approval_status in {"rejected", "conflict"}]
    if blockers:
        raise HTTPException(status_code=409, detail={"code": "SNAPSHOT_BLOCKED", "documents": blockers})
    if not payload.mandatory_test_result.get("passed", False):
        raise HTTPException(status_code=409, detail={"code": "REGRESSION_TEST_FAILED"})
    final_hash = checksum("|".join(sorted(doc.checksum for doc in documents)))
    previous_snapshot = db.scalar(select(KnowledgeSnapshot).where(KnowledgeSnapshot.version_id == payload.version_id, KnowledgeSnapshot.publish_status == "published").order_by(KnowledgeSnapshot.created_at.desc()))
    snapshot = KnowledgeSnapshot(
        software_id=payload.software_id,
        version_id=payload.version_id,
        name=payload.name,
        release_note=payload.release_note,
        approvers=payload.approvers,
        scheduled_at=payload.scheduled_at,
        document_ids=payload.document_ids,
        final_hash=final_hash,
        conflict_report={"blockers": [], "conflicts": []},
        regression_report=payload.mandatory_test_result,
        publish_status="published",
        previous_snapshot_id=previous_snapshot.id if previous_snapshot else None,
        published_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    version = db.get(SoftwareVersion, payload.version_id)
    if version:
        version.active_snapshot_id = snapshot.id
        version.version_hash = final_hash
        version.status = "active"
    db.flush()
    write_audit(db, action="knowledge.snapshot_publish", target_type="knowledge_snapshot", target_id=snapshot.id, actor_id=current_user.id, software_id=payload.software_id, version_id=payload.version_id, after_value={"final_hash": final_hash, "document_ids": payload.document_ids}, request=request)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.post("/snapshots/{snapshot_id}/rollback", response_model=SnapshotRead)
def rollback_snapshot(snapshot_id: str, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.SNAPSHOT_PUBLISH))) -> SnapshotRead:
    snapshot = db.get(KnowledgeSnapshot, snapshot_id)
    if not snapshot or not snapshot.previous_snapshot_id:
        raise HTTPException(status_code=404, detail="rollback target not available")
    previous = db.get(KnowledgeSnapshot, snapshot.previous_snapshot_id)
    version = db.get(SoftwareVersion, snapshot.version_id)
    if version and previous:
        version.active_snapshot_id = previous.id
        version.version_hash = previous.final_hash
    write_audit(db, action="knowledge.snapshot_rollback", target_type="knowledge_snapshot", target_id=snapshot.id, actor_id=current_user.id, after_value={"active_snapshot_id": previous.id if previous else None}, request=request)
    db.commit()
    return previous


@router.post("/schema-relations", response_model=SchemaRelationRead, status_code=status.HTTP_201_CREATED)
def create_schema_relation(
    payload: SchemaRelationCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.KNOWLEDGE_WRITE)),
) -> SchemaRelationRead:
    relation = SchemaRelation(**payload.model_dump())
    db.add(relation)
    db.flush()
    write_audit(db, action="schema_relation.create", target_type="schema_relation", target_id=relation.id, actor_id=current_user.id, software_id=payload.software_id, version_id=payload.version_id, after_value=payload.model_dump(), request=request)
    db.commit()
    db.refresh(relation)
    return relation


@router.get("/schema-relations", response_model=list[SchemaRelationRead])
def list_schema_relations(software_id: str, version_id: str, db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[SchemaRelationRead]:
    return list(db.scalars(select(SchemaRelation).where(SchemaRelation.software_id == software_id, SchemaRelation.version_id == version_id).order_by(SchemaRelation.source_table)))


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_software_user(
    payload: SoftwareUserCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.USERS_WRITE)),
) -> UserRead:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(
        tenant_id=payload.tenant_id or current_user.tenant_id,
        external_user_id=payload.external_user_id,
        username=payload.username,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        hashed_password=get_password_hash(payload.temporary_password),
        roles=payload.roles,
        scopes=payload.scopes,
        allowed_subjects=payload.allowed_subjects,
        organization=payload.organization,
        region=payload.region,
        daily_quota=payload.daily_quota,
        monthly_quota=payload.monthly_quota,
        expires_at=payload.expires_at,
        status=payload.status,
    )
    db.add(user)
    db.flush()
    write_audit(db, action="software_user.create", target_type="user", target_id=user.id, actor_id=current_user.id, tenant_id=user.tenant_id, after_value=payload.model_dump(exclude={"temporary_password"}, mode="json"), request=request)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
def list_software_users(db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[UserRead]:
    query = select(User).order_by(User.created_at.desc())
    if current_user.tenant_id:
        query = query.where(User.tenant_id == current_user.tenant_id)
    return list(db.scalars(query))


@router.post("/user-roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_user_role(payload: RoleCreate, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.USERS_WRITE))) -> RoleRead:
    role = Role(**payload.model_dump())
    db.add(role)
    db.flush()
    write_audit(db, action="software_user.role_create", target_type="role", target_id=role.id, actor_id=current_user.id, after_value=payload.model_dump(), request=request)
    db.commit()
    db.refresh(role)
    return role


@router.post("/api-keys", response_model=APIKeyIssued, status_code=status.HTTP_201_CREATED)
def issue_api_key(
    payload: APIKeyCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.API_KEYS_WRITE)),
) -> APIKeyIssued:
    secret = f"nl2sql_{secrets.token_urlsafe(32)}"
    prefix = api_key_prefix(secret)
    key = APIKey(
        tenant_id=current_user.tenant_id,
        owner_user_id=payload.owner_user_id,
        software_id=payload.software_id,
        version_id=payload.version_id,
        name=payload.name,
        prefix=prefix,
        secret_hash=get_password_hash(secret),
        scopes=payload.scopes,
        ip_allowlist=payload.ip_allowlist,
        rate_limit=payload.rate_limit,
        consumption_limit=payload.consumption_limit,
        environment=payload.environment,
        mtls_enabled=payload.mtls_enabled,
        description=payload.description,
        expires_at=payload.expires_at,
    )
    db.add(key)
    db.flush()
    write_audit(db, action="api_key.issue", target_type="api_key", target_id=key.id, actor_id=current_user.id, api_key_prefix=prefix, after_value=payload.model_dump(mode="json"), request=request, event_type="security")
    db.commit()
    db.refresh(key)
    return APIKeyIssued(id=key.id, prefix=key.prefix, secret=secret, status=key.status, expires_at=key.expires_at, created_at=key.created_at)


@router.get("/api-keys", response_model=list[APIKeyRead])
def list_api_keys(db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[APIKeyRead]:
    query = select(APIKey).order_by(APIKey.created_at.desc())
    if current_user.tenant_id:
        query = query.where(APIKey.tenant_id == current_user.tenant_id)
    return list(db.scalars(query))


@router.post("/api-keys/{key_id}/revoke", response_model=APIKeyRead)
def revoke_api_key(key_id: str, reason: str, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.API_KEYS_WRITE))) -> APIKeyRead:
    key = db.get(APIKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="api key not found")
    key.status = "revoked"
    key.revoked_reason = reason
    write_audit(db, action="api_key.revoke", target_type="api_key", target_id=key.id, actor_id=current_user.id, api_key_prefix=key.prefix, after_value={"reason": reason}, request=request, event_type="security")
    db.commit()
    db.refresh(key)
    return key


@router.get("/consumption", response_model=dict[str, Any])
def consumption(db: DbSession, current_user: CurrentUser = SoftwareAdmin, user_id: str | None = None, api_key_id: str | None = None) -> dict[str, Any]:
    query = select(ReportRequest)
    if user_id:
        query = query.where(ReportRequest.user_id == user_id)
    if api_key_id:
        query = query.where(ReportRequest.api_key_id == api_key_id)
    requests = db.scalars(query).all()
    return {
        "current_usage": len(requests),
        "remaining_quota": None,
        "cost": float(sum(item.cost_amount or 0 for item in requests)),
        "rejected_by_quota": sum(1 for item in requests if item.rejection_reason_code == "QUOTA_EXCEEDED"),
        "chart": [],
    }


@router.get("/requests", response_model=list[RequestMonitorRead])
def monitor_requests(
    db: DbSession,
    current_user: CurrentUser = Depends(require_permissions(Permission.REQUESTS_READ)),
    request_id: str | None = None,
    audit_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
    software_id: str | None = None,
    status_filter: str | None = None,
    model_id: str | None = None,
    intent: str | None = None,
    cache_hit: bool | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RequestMonitorRead]:
    query = select(ReportRequest)
    if request_id:
        query = query.where(ReportRequest.id == request_id)
    if audit_id:
        query = query.where(ReportRequest.audit_id == audit_id)
    if correlation_id:
        query = query.where(ReportRequest.correlation_id == correlation_id)
    if user_id:
        query = query.where(ReportRequest.user_id == user_id)
    if software_id:
        query = query.where(ReportRequest.software_id == software_id)
    if status_filter:
        query = query.where(ReportRequest.status == status_filter)
    if model_id:
        query = query.where(ReportRequest.model_id == model_id)
    if intent:
        query = query.where(ReportRequest.intent == intent)
    if cache_hit is not None:
        query = query.where(ReportRequest.cache_hit == cache_hit)
    if risk_level:
        query = query.where(ReportRequest.risk_level == risk_level)
    return list(db.scalars(query.order_by(ReportRequest.created_at.desc()).limit(limit).offset(offset)))


@router.get("/requests/{request_id}", response_model=RequestDetailRead)
def request_detail(request_id: str, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.REQUESTS_READ))) -> RequestDetailRead:
    item = db.get(ReportRequest, request_id)
    if not item:
        raise HTTPException(status_code=404, detail="request not found")
    return item


@router.post("/quality/reviews", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def quality_review(payload: QualityReviewCreate, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.QUALITY_WRITE))) -> FeedbackRead:
    final_score = payload.automatic_score if payload.automatic_score is not None else payload.rating / 5
    feedback = Feedback(
        audit_id=payload.audit_id,
        user_verdict=payload.user_verdict,
        rating=payload.rating,
        description=payload.description,
        automatic_score=payload.automatic_score,
        gold_test_result=payload.gold_test_result,
        manager_comment=payload.manager_comment,
        error_reason=payload.error_reason,
        corrected_sql=payload.corrected_sql,
        convert_to_recipe=payload.convert_to_recipe,
        requires_knowledge_fix=payload.requires_knowledge_fix,
        final_score=final_score,
        review_status="completed",
        error_category=payload.error_reason,
        corrective_action="recipe" if payload.convert_to_recipe else "knowledge_fix" if payload.requires_knowledge_fix else "none",
    )
    db.add(feedback)
    db.flush()
    write_audit(db, action="quality.review", target_type="feedback", target_id=feedback.id, actor_id=current_user.id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.post("/recipes", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.QUALITY_WRITE))) -> RecipeRead:
    fingerprint = checksum(f"{payload.software_id}:{payload.version_id}:{payload.canonical_question}:{payload.access_scope}")
    recipe = Recipe(**payload.model_dump(), cache_fingerprint=fingerprint)
    db.add(recipe)
    db.flush()
    write_audit(db, action="recipe.create", target_type="recipe", target_id=recipe.id, actor_id=current_user.id, after_value={"fingerprint": fingerprint}, request=request)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.get("/recipes", response_model=list[RecipeRead])
def list_recipes(db: DbSession, current_user: CurrentUser = SoftwareAdmin, software_id: str | None = None, version_id: str | None = None) -> list[RecipeRead]:
    query = select(Recipe)
    if software_id:
        query = query.where(Recipe.software_id == software_id)
    if version_id:
        query = query.where(Recipe.version_id == version_id)
    return list(db.scalars(query.order_by(Recipe.created_at.desc())))


@router.post("/gold-tests", response_model=GoldTestRead, status_code=status.HTTP_201_CREATED)
def create_gold_test(payload: GoldTestCreate, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.QUALITY_WRITE))) -> GoldTestRead:
    count = db.scalar(select(func.count()).select_from(GoldTest).where(GoldTest.software_id == payload.software_id, GoldTest.version_id == payload.version_id)) or 0
    gold = GoldTest(**payload.model_dump(), last_run_result={"status": "not_run", "pilot_minimum_progress": f"{count + 1}/20"})
    db.add(gold)
    db.flush()
    write_audit(db, action="gold_test.create", target_type="gold_test", target_id=gold.id, actor_id=current_user.id, after_value={"question": payload.question, "progress": count + 1}, request=request)
    db.commit()
    db.refresh(gold)
    return gold


@router.get("/gold-tests", response_model=list[GoldTestRead])
def list_gold_tests(software_id: str, version_id: str, db: DbSession, current_user: CurrentUser = SoftwareAdmin) -> list[GoldTestRead]:
    return list(db.scalars(select(GoldTest).where(GoldTest.software_id == software_id, GoldTest.version_id == version_id).order_by(GoldTest.created_at)))


@router.post("/gold-tests/{gold_test_id}/run", response_model=GoldTestRunResult)
def run_gold_test(gold_test_id: str, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.QUALITY_WRITE))) -> GoldTestRunResult:
    gold = db.get(GoldTest, gold_test_id)
    if not gold:
        raise HTTPException(status_code=404, detail="gold test not found")
    product = db.get(SoftwareProduct, gold.software_id)
    version = db.get(SoftwareVersion, gold.version_id)
    if not product or not version:
        raise HTTPException(status_code=409, detail="software/version missing")
    from app.schemas.domain import AccessContext, ReportRequestIn
    import uuid

    payload = ReportRequestIn(
        request_id=uuid.uuid4(),
        software_id=product.code,
        software_version=version.version_number,
        user_id="gold-test-user",
        question=gold.question,
        access_context=AccessContext(**(gold.test_user_context or {"organization": "test", "region": [], "roles": ["report-user"], "scopes": ["commission100.read", "permits.read", "payments.read"]})),
    )
    response = generate_report_contract(db, payload)
    generated_sql = getattr(response, "sql", "") or ""
    expected_tables = set(gold.expected_tables or [])
    actual_tables = {table for table in expected_tables if table.lower() in generated_sql.lower()}
    passed = response.status == "success" and (not expected_tables or actual_tables == expected_tables)
    result = GoldTestRunResult(
        generated_sql=generated_sql,
        semantic_comparison={"expected_tables": list(expected_tables), "matched_tables": list(actual_tables)},
        status="pass" if passed else "fail",
        diff={"tables": list(expected_tables - actual_tables), "joins": [], "filter_sort_grain": gold.expected_filter_sort_grain},
        security_error=None if response.status != "rejected" else getattr(response, "reason_code", None),
        response_time_ms=100,
        prompt_tokens=540,
        completion_tokens=180,
        regression_report={"audit_id": response.audit_id, "minimum_required": 20},
    )
    gold.last_run_result = result.model_dump(mode="json")
    write_audit(db, action="gold_test.run", target_type="gold_test", target_id=gold.id, actor_id=current_user.id, after_value=result.model_dump(mode="json"), request=request)
    db.commit()
    return result


@router.post("/model-policies", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_model_policy(payload: ModelPolicyCreate, request: Request, db: DbSession, current_user: CurrentUser = Depends(require_permissions(Permission.SOFTWARE_WRITE))) -> dict[str, Any]:
    policy = ModelPolicy(**payload.model_dump())
    db.add(policy)
    db.flush()
    write_audit(db, action="model_policy.create", target_type="model_policy", target_id=policy.id, actor_id=current_user.id, software_id=payload.software_id, after_value=payload.model_dump(mode="json"), request=request)
    db.commit()
    return {
        "id": policy.id,
        "active_route": [payload.primary_model_id, *payload.fallback_model_ids],
        "health_status": "unknown",
        "last_failover": None,
        "cost_quality": {},
        "selection_reason": "policy_priority",
    }
