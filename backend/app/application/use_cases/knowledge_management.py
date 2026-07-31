from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.application.common.context import ActorContext
from app.application.common.exceptions import BusinessRuleViolation, NotFoundError
from app.application.ports.unit_of_work import UnitOfWorkPort
from app.services.knowledge import (
    checksum,
    detect_document_type,
    extract_metadata,
    validate_knowledge,
)


@dataclass(slots=True)
class UploadKnowledgeDocumentUseCase:
    uow: UnitOfWorkPort

    def execute(self, data: dict[str, Any], actor: ActorContext) -> Any:
        content = data["content"]
        detected = detect_document_type(content, data["document_type"])
        metadata = extract_metadata(content)
        quality_score, errors, warnings = validate_knowledge(content, data["document_type"])
        document = self.uow.knowledge.add_document(
            data,
            enrichment={
                "checksum": checksum(content),
                "detected_type": detected,
                "extracted_metadata": metadata,
                "quality_score": quality_score,
                "errors": errors,
                "warnings": warnings,
                "approval_status": "review" if errors or warnings else "approved",
            },
        )
        self.uow.audit.record(
            actor=actor,
            action="knowledge.upload",
            target_type="knowledge_document",
            target_id=document.id,
            software_id=data["software_id"],
            version_id=data["version_id"],
            after_value={"title": data["title"], "checksum": document.checksum, "metadata": metadata},
        )
        self.uow.commit()
        return document


@dataclass(slots=True)
class StandardizeKnowledgeUseCase:
    uow: UnitOfWorkPort

    def execute(self, data: dict[str, Any], actor: ActorContext) -> dict[str, Any]:
        documents = self.uow.knowledge.get_documents_by_ids(data["document_ids"])
        if len(documents) != len(data["document_ids"]):
            raise NotFoundError(
                code="KNOWLEDGE_DOCUMENT_NOT_FOUND",
                message="یک یا چند سند دانش یافت نشد.",
                details={"requested": data["document_ids"], "found": [document.id for document in documents]},
            )

        blockers: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        suggestions: list[dict[str, Any]] = []
        seen_checksums: dict[str, str] = {}

        for document in documents:
            document.detected_type = detect_document_type(document.content, document.document_type)
            document.extracted_metadata = extract_metadata(document.content)
            document.quality_score, document.errors, document.warnings = validate_knowledge(
                document.content, document.document_type
            )
            if document.errors:
                blockers.extend({"document_id": document.id, **error} for error in document.errors)
                document.approval_status = "rejected"
            elif document.checksum in seen_checksums:
                conflicts.append(
                    {
                        "document_id": document.id,
                        "conflicts_with": seen_checksums[document.checksum],
                        "code": "DUPLICATE_CHECKSUM",
                    }
                )
                document.approval_status = "conflict"
            else:
                seen_checksums[document.checksum] = document.id
                document.approval_status = "review" if document.warnings else "approved"
                if document.warnings:
                    suggestions.append(
                        {"document_id": document.id, "message": "برای تأیید نهایی هشدارها را بازبینی کنید."}
                    )

        final_status = "conflict" if conflicts else "rejected" if blockers else "review" if suggestions else "approved"
        self.uow.audit.record(
            actor=actor,
            action="knowledge.standardize",
            target_type="knowledge_batch",
            software_id=data["software_id"],
            version_id=data["version_id"],
            after_value={"status": final_status, "blockers": blockers, "conflicts": conflicts},
        )
        self.uow.commit()
        return {
            "status": final_status,
            "documents": documents,
            "blockers": blockers,
            "conflicts": conflicts,
            "suggestions": suggestions,
        }


@dataclass(slots=True)
class PublishSnapshotUseCase:
    uow: UnitOfWorkPort

    def execute(self, data: dict[str, Any], actor: ActorContext) -> Any:
        documents = self.uow.knowledge.get_documents_by_ids(data["document_ids"])
        if len(documents) != len(data["document_ids"]):
            raise NotFoundError(
                code="KNOWLEDGE_DOCUMENT_NOT_FOUND",
                message="یک یا چند سند برای انتشار Snapshot یافت نشد.",
            )

        blockers = [document.id for document in documents if document.errors or document.approval_status in {"rejected", "conflict"}]
        if blockers:
            raise BusinessRuleViolation(
                code="SNAPSHOT_BLOCKED",
                message="انتشار Snapshot فقط در صورت نبود Blocker امکان‌پذیر است.",
                details={"documents": blockers},
            )
        if not data.get("mandatory_test_result", {}).get("passed", False):
            raise BusinessRuleViolation(
                code="REGRESSION_TEST_FAILED",
                message="تست‌های اجباری Regression موفق نبوده‌اند.",
            )

        final_hash = checksum("|".join(sorted(document.checksum for document in documents)))
        previous_snapshot = self.uow.software.latest_published_snapshot(data["version_id"])
        snapshot = self.uow.knowledge.add_snapshot(
            {
                "software_id": data["software_id"],
                "version_id": data["version_id"],
                "name": data["name"],
                "release_note": data.get("release_note"),
                "approvers": data.get("approvers") or [],
                "scheduled_at": data.get("scheduled_at"),
                "document_ids": data["document_ids"],
                "final_hash": final_hash,
                "conflict_report": {"blockers": [], "conflicts": []},
                "regression_report": data.get("mandatory_test_result") or {"passed": True},
                "publish_status": "published",
                "previous_snapshot_id": previous_snapshot.id if previous_snapshot else None,
                "published_at": datetime.now(UTC),
            }
        )
        self.uow.software.activate_snapshot(data["version_id"], snapshot.id, final_hash)
        self.uow.audit.record(
            actor=actor,
            action="knowledge.snapshot_publish",
            target_type="knowledge_snapshot",
            target_id=snapshot.id,
            software_id=data["software_id"],
            version_id=data["version_id"],
            after_value={"final_hash": final_hash, "document_ids": data["document_ids"]},
        )
        self.uow.commit()
        return snapshot
