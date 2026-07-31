from __future__ import annotations

from typing import Any, Protocol

from app.application.common.context import ActorContext


class SoftwareRepositoryPort(Protocol):
    def code_exists(self, code: str) -> bool: ...

    def add_product(self, data: dict[str, Any]) -> Any: ...

    def get_product(self, software_id: str) -> Any | None: ...

    def list_products(self, tenant_id: str | None = None) -> list[Any]: ...

    def add_version(self, data: dict[str, Any], version_hash: str) -> Any: ...

    def get_version(self, version_id: str) -> Any | None: ...

    def list_versions(self, software_id: str) -> list[Any]: ...

    def latest_published_snapshot(self, version_id: str) -> Any | None: ...

    def activate_snapshot(self, version_id: str, snapshot_id: str, version_hash: str) -> None: ...


class KnowledgeRepositoryPort(Protocol):
    def add_document(self, data: dict[str, Any], enrichment: dict[str, Any]) -> Any: ...

    def get_document(self, document_id: str) -> Any | None: ...

    def get_documents_by_ids(self, document_ids: list[str]) -> list[Any]: ...

    def list_documents(
        self,
        *,
        software_id: str | None = None,
        version_id: str | None = None,
        approval_status: str | None = None,
    ) -> list[Any]: ...

    def add_snapshot(self, data: dict[str, Any]) -> Any: ...


class AuditPort(Protocol):
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
    ) -> Any: ...


class UnitOfWorkPort(Protocol):
    software: SoftwareRepositoryPort
    knowledge: KnowledgeRepositoryPort
    audit: AuditPort

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
