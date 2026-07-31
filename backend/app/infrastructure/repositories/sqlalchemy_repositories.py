from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.common.context import ActorContext
from app.core.security import redact
from app.models.domain import (
    AuditLog,
    KnowledgeDocument,
    KnowledgeSnapshot,
    SoftwareProduct,
    SoftwareVersion,
)
from app.services.audit import new_audit_id


class SQLAlchemySoftwareRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def code_exists(self, code: str) -> bool:
        return self.session.scalar(select(SoftwareProduct.id).where(SoftwareProduct.code == code)) is not None

    def add_product(self, data: dict[str, Any]) -> SoftwareProduct:
        product = SoftwareProduct(**data)
        self.session.add(product)
        self.session.flush()
        return product

    def get_product(self, software_id: str) -> SoftwareProduct | None:
        return self.session.get(SoftwareProduct, software_id)

    def list_products(self, tenant_id: str | None = None) -> list[SoftwareProduct]:
        query = select(SoftwareProduct).order_by(SoftwareProduct.name)
        if tenant_id:
            query = query.where((SoftwareProduct.tenant_id == tenant_id) | (SoftwareProduct.tenant_id.is_(None)))
        return list(self.session.scalars(query))

    def add_version(self, data: dict[str, Any], version_hash: str) -> SoftwareVersion:
        version = SoftwareVersion(**data, version_hash=version_hash)
        self.session.add(version)
        self.session.flush()
        return version

    def get_version(self, version_id: str) -> SoftwareVersion | None:
        return self.session.get(SoftwareVersion, version_id)

    def list_versions(self, software_id: str) -> list[SoftwareVersion]:
        return list(
            self.session.scalars(
                select(SoftwareVersion)
                .where(SoftwareVersion.software_id == software_id)
                .order_by(SoftwareVersion.created_at.desc())
            )
        )

    def latest_published_snapshot(self, version_id: str) -> KnowledgeSnapshot | None:
        return self.session.scalar(
            select(KnowledgeSnapshot)
            .where(KnowledgeSnapshot.version_id == version_id, KnowledgeSnapshot.publish_status == "published")
            .order_by(KnowledgeSnapshot.created_at.desc())
        )

    def activate_snapshot(self, version_id: str, snapshot_id: str, version_hash: str) -> None:
        version = self.session.get(SoftwareVersion, version_id)
        if version:
            version.active_snapshot_id = snapshot_id
            version.version_hash = version_hash
            version.status = "active"


class SQLAlchemyKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_document(self, data: dict[str, Any], enrichment: dict[str, Any]) -> KnowledgeDocument:
        document = KnowledgeDocument(**data, **enrichment)
        self.session.add(document)
        self.session.flush()
        return document

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self.session.get(KnowledgeDocument, document_id)

    def get_documents_by_ids(self, document_ids: list[str]) -> list[KnowledgeDocument]:
        if not document_ids:
            return []
        return list(self.session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))))

    def list_documents(
        self,
        *,
        software_id: str | None = None,
        version_id: str | None = None,
        approval_status: str | None = None,
    ) -> list[KnowledgeDocument]:
        query = select(KnowledgeDocument)
        if software_id:
            query = query.where(KnowledgeDocument.software_id == software_id)
        if version_id:
            query = query.where(KnowledgeDocument.version_id == version_id)
        if approval_status:
            query = query.where(KnowledgeDocument.approval_status == approval_status)
        return list(self.session.scalars(query.order_by(KnowledgeDocument.created_at.desc())))

    def add_snapshot(self, data: dict[str, Any]) -> KnowledgeSnapshot:
        snapshot = KnowledgeSnapshot(**data)
        self.session.add(snapshot)
        self.session.flush()
        return snapshot


class SQLAlchemyAuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor: ActorContext,
        action: str,
        target_type: str,
        target_id: str | None = None,
        tenant_id: str | None = None,
        software_id: str | None = None,
        version_id: str | None = None,
        before_value: dict[str, Any] | None = None,
        after_value: dict[str, Any] | None = None,
        result: str = "success",
        rejection_reason: str | None = None,
        event_type: str = "business",
        severity: str = "info",
        request_id: str | None = None,
        api_key_prefix: str | None = None,
    ) -> AuditLog:
        audit = AuditLog(
            audit_id=new_audit_id(),
            correlation_id=actor.correlation_id,
            actor_id=actor.actor_id,
            actor_type="user",
            action=action,
            target_type=target_type,
            target_id=target_id,
            tenant_id=tenant_id or actor.tenant_id,
            software_id=software_id,
            version_id=version_id,
            ip=actor.ip,
            api_key_prefix=api_key_prefix,
            event_type=event_type,
            severity=severity,
            before_value=redact(before_value or {}),
            after_value=redact(after_value or {}),
            result=result,
            rejection_reason=rejection_reason,
            request_id=request_id,
            user_agent=actor.user_agent,
            chain=[],
        )
        self.session.add(audit)
        self.session.flush()
        return audit
