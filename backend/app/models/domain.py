from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    responsible_manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    allowed_software_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cloud_model_policy: Mapped[str] = mapped_column(String(40), default="restricted", nullable=False)
    log_retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tehran", nullable=False)
    consumption_limit: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    security_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    external_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_subjects: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    organization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    daily_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    mfa_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="fa-IR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tehran", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base, TimestampMixin):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    device: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SoftwareProduct(Base, TimestampMixin):
    __tablename__ = "software_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible_manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_type: Mapped[str] = mapped_column(String(30), default="standalone", nullable=False)
    parent_software_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_products.id"), nullable=True)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    database_dialect: Mapped[str] = mapped_column(String(60), default="T-SQL", nullable=False)
    default_schema: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=True)
    security_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    access_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="fa-IR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tehran", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class SoftwareVersion(Base, TimestampMixin):
    __tablename__ = "software_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_number: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    build_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    base_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_versions.id"), nullable=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    database_dialect: Mapped[str] = mapped_column(String(60), default="T-SQL", nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    can_reference_previous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    version_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    regression_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("software_id", "version_number", name="uq_versions_software_number"),)


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_versions.id"), index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sensitivity_level: Mapped[str] = mapped_column(String(30), default="internal", nullable=False)
    replaced_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_documents.id"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    extracted_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (Index("ix_knowledge_documents_status", "approval_status"),)


class KnowledgeSnapshot(Base, TimestampMixin):
    __tablename__ = "knowledge_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_versions.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    release_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approvers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    final_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    conflict_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    regression_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    publish_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    previous_snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_snapshots.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SchemaRelation(Base, TimestampMixin):
    __tablename__ = "schema_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_versions.id"), index=True, nullable=False)
    source_table: Mapped[str] = mapped_column(String(255), nullable=False)
    source_column: Mapped[str] = mapped_column(String(255), nullable=False)
    target_table: Mapped[str] = mapped_column(String(255), nullable=False)
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    join_type: Mapped[str] = mapped_column(String(30), default="INNER", nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_risk: Mapped[str] = mapped_column(String(30), default="low", nullable=False)
    forbidden_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    verification_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    software_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_products.id"), nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_versions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ip_allowlist: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rate_limit: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    consumption_limit: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    environment: Mapped[str] = mapped_column(String(30), default="development", nullable=False)
    mtls_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIModel(Base, TimestampMixin):
    __tablename__ = "ai_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hosting_type: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_token_cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0, nullable=False)
    output_token_cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    max_retry: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    allowed_tenants: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_sensitivity_levels: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fallback_model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=True)
    failover_conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    health_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ModelPolicy(Base, TimestampMixin):
    __tablename__ = "model_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    primary_model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=False)
    fallback_model_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cloud_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_sensitivity_level: Mapped[str] = mapped_column(String(30), default="internal", nullable=False)
    max_cost: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    failover_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sensitive_query_model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=True)


class Tariff(Base, TimestampMixin):
    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="hybrid", nullable=False)
    input_token_cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0, nullable=False)
    output_token_cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0, nullable=False)
    model_coefficients: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cached_request_price: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    minimum_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    daily_cap: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    monthly_cap: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applies_to: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tax_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class WalletLedger(Base, TimestampMixin):
    __tablename__ = "wallet_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    balance_before: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    financial_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reserved_amount: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    consumed_amount: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    wallet_ledger_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("wallet_ledger.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    gateway: Mapped[str] = mapped_column(String(120), nullable=False)
    target_wallet: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    callback_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reconciliation_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReportRequest(Base, TimestampMixin):
    __tablename__ = "report_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    software_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_versions.id"), nullable=True, index=True)
    external_software_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    api_key_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("api_keys.id"), nullable=True)
    question_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    access_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="fa-IR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tehran", nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    entities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    display_spec: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validator_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=True)
    failover_trace: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_amount: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), default="low", nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audit_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rejection_reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    audit_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    software_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(80), nullable=True)
    api_key_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), default="business", nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="info", nullable=False)
    before_value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    after_value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[str] = mapped_column(String(40), default="success", nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    chain: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    audit_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    user_verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    manager_review_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    automatic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gold_test_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    convert_to_recipe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_knowledge_fix: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recipe(Base, TimestampMixin):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    canonical_question: Mapped[str] = mapped_column(Text, nullable=False)
    persian_rewrites: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    intent: Mapped[str] = mapped_column(String(120), nullable=False)
    entities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_versions.id"), index=True, nullable=False)
    access_scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    parameterized_sql: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    display_spec: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=86_400, nullable=False)
    approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    cache_fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    token_savings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_savings: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class GoldTest(Base, TimestampMixin):
    __tablename__ = "gold_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    rewrites: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_versions.id"), index=True, nullable=False)
    test_user_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expected_intent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_tables: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_joins: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    expected_filter_sort_grain: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gold_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    forbidden_operations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_snapshots.id"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_models.id"), nullable=True)
    last_run_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Connector(Base, TimestampMixin):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    software_id: Mapped[str] = mapped_column(String(36), ForeignKey("software_products.id"), index=True, nullable=False)
    version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("software_versions.id"), nullable=True)
    central_api_url: Mapped[str] = mapped_column(String(500), nullable=False)
    tls_certificate_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    database_dialect: Mapped[str] = mapped_column(String(60), default="T-SQL", nullable=False)
    encrypted_connection_string: Mapped[str] = mapped_column(Text, nullable=False)
    readonly_account: Mapped[str] = mapped_column(String(255), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    allowed_views: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    registration_status: Mapped[str] = mapped_column(String(30), default="registered", nullable=False)
    central_connection_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    database_connection_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    connector_version: Mapped[str] = mapped_column(String(80), default="0.1.0", nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_policy_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_status: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    communication_errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    database_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
