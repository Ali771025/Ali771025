from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class Page(ORMModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class StatusMessage(BaseModel):
    status: str = "ok"
    message: str | None = None


# -------------------------- public/auth --------------------------
class LoginRequest(BaseModel):
    username_or_email: str
    password: str
    tenant_code: str | None = None
    captcha: str | None = None
    remember_me: bool = False


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthUser(BaseModel):
    id: str
    username: str
    email: EmailStr | None = None
    full_name: str | None = None
    tenant_id: str | None = None
    roles: list[str]
    permissions: list[str]
    mfa_required: bool = False
    mfa_enabled: bool = False
    locale: str = "fa-IR"
    timezone: str = "Asia/Tehran"


class LoginResponse(BaseModel):
    tokens: TokenPair | None = None
    user: AuthUser
    requires_mfa: bool = False
    challenge_id: str | None = None


class MFAVerifyRequest(BaseModel):
    challenge_id: str | None = None
    otp_code: str | None = None
    authenticator_code: str | None = None
    recovery_code: str | None = None


class MFAResult(BaseModel):
    verified: bool
    suspicious_login: bool = False
    device_registered: bool = False
    tokens: TokenPair | None = None
    message: str | None = None


class ForgotPasswordRequest(BaseModel):
    username_or_email: str


class ResetPasswordRequest(BaseModel):
    username_or_email: str
    otp_or_token: str
    new_password: str = Field(min_length=10)
    confirm_new_password: str = Field(min_length=10)

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        if info.data.get("new_password") != value:
            raise ValueError("passwords_do_not_match")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)
    confirm_new_password: str = Field(min_length=10)

    @field_validator("confirm_new_password")
    @classmethod
    def change_passwords_match(cls, value: str, info):
        if info.data.get("new_password") != value:
            raise ValueError("passwords_do_not_match")
        return value


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    email: EmailStr | None = None
    locale: str | None = None
    timezone: str | None = None
    mfa_enabled: bool | None = None


class ProfileResponse(AuthUser):
    mobile: str | None = None
    last_login_at: datetime | None = None
    sessions: list[dict[str, Any]] = []


# -------------------------- owner/system management --------------------------
class TenantCreate(BaseModel):
    code: str
    name: str
    contact_info: dict[str, Any] = {}
    responsible_manager_id: str | None = None
    allowed_software_ids: list[str] = []
    cloud_model_policy: Literal["allowed", "restricted", "forbidden"] = "restricted"
    log_retention_days: int = Field(default=365, ge=1)
    timezone: str = "Asia/Tehran"
    consumption_limit: float | None = None
    status: Literal["active", "inactive", "suspended"] = "active"
    security_policy: dict[str, Any] = {}


class TenantRead(ORMModel, TenantCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class ManagerCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    username: str
    email: EmailStr | None = None
    mobile: str | None = None
    tenant_id: str | None = None
    managed_software_ids: list[str] = []
    roles: list[str] = ["software_admin"]
    scopes: list[str] = []
    consumption_limit: float | None = None
    expires_at: datetime | None = None
    status: Literal["active", "inactive", "suspended"] = "active"
    mfa_required: bool = True
    description: str | None = None
    temporary_password: str = Field(default="ChangeMe!12345", min_length=10)


class UserRead(ORMModel):
    id: str
    tenant_id: str | None
    external_user_id: str | None = None
    username: str
    email: EmailStr | None = None
    mobile: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str]
    scopes: list[str]
    allowed_subjects: list[str] = []
    organization: str | None = None
    region: list[str] = []
    daily_quota: int | None = None
    monthly_quota: int | None = None
    expires_at: datetime | None = None
    status: str
    mfa_required: bool
    mfa_enabled: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    tenant_id: str | None = None
    name: str
    description: str | None = None
    scope: dict[str, Any] = {}
    permissions: list[str] = []


class RoleRead(ORMModel, RoleCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class AIModelCreate(BaseModel):
    provider: str
    name: str
    version: str | None = None
    hosting_type: Literal["local", "cloud"] = "local"
    endpoint: str | None = None
    credential_ref: str | None = None
    input_token_cost: float = 0
    output_token_cost: float = 0
    context_length: int = 8192
    timeout_seconds: int = 30
    priority: int = 100
    max_retry: int = 1
    status: Literal["active", "inactive", "degraded"] = "active"
    allowed_tenants: list[str] = []
    allowed_sensitivity_levels: list[str] = ["public", "internal"]
    fallback_model_id: str | None = None
    failover_conditions: dict[str, Any] = {}


class AIModelRead(ORMModel, AIModelCreate):
    id: str
    health_status: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TariffCreate(BaseModel):
    name: str
    unit: Literal["request", "token", "model", "time", "hybrid"] = "hybrid"
    input_token_cost: float = 0
    output_token_cost: float = 0
    model_coefficients: dict[str, float] = {}
    cached_request_price: float = 0
    minimum_cost: float = 0
    daily_cap: float | None = None
    monthly_cap: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    applies_to: dict[str, Any] = {}
    tax_percent: float = 0
    discount_percent: float = 0
    status: Literal["active", "inactive"] = "active"


class TariffRead(ORMModel, TariffCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class WalletOperation(BaseModel):
    tenant_id: str | None = None
    user_id: str | None = None
    manager_id: str | None = None
    operation_type: Literal["charge", "deduct", "adjust", "refund"]
    amount: float
    expires_at: datetime | None = None
    financial_reference: str | None = None
    description: str | None = None


class WalletLedgerRead(ORMModel, WalletOperation):
    id: str
    balance_before: float
    balance_after: float
    reserved_amount: float
    consumed_amount: float
    created_at: datetime


class PaymentCreate(BaseModel):
    amount: float
    gateway: str
    target_wallet: dict[str, Any]
    tracking_number: str | None = None
    status: Literal["pending", "successful", "failed", "refunded"] = "pending"
    callback_payload: dict[str, Any] = {}
    correction_reason: str | None = None


# -------------------------- software admin --------------------------
class SoftwareCreate(BaseModel):
    tenant_id: str | None = None
    code: str
    name: str
    owner_company: str | None = None
    responsible_manager_id: str | None = None
    description: str | None = None
    product_type: Literal["standalone", "dependent"] = "standalone"
    parent_software_id: str | None = None
    dependencies: list[str] = []
    database_dialect: str = "T-SQL"
    default_schema: str | None = None
    default_model_id: str | None = None
    security_policy: dict[str, Any] = {}
    access_policy: dict[str, Any] = {"max_rows": 100, "timeout_seconds": 10}
    locale: str = "fa-IR"
    timezone: str = "Asia/Tehran"
    status: Literal["active", "inactive"] = "active"


class SoftwareRead(ORMModel, SoftwareCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class VersionCreate(BaseModel):
    software_id: str
    version_number: str
    title: str | None = None
    build_number: str | None = None
    base_version_id: str | None = None
    release_date: datetime | None = None
    change_log: str | None = None
    database_dialect: str = "T-SQL"
    schema_version: str | None = None
    can_reference_previous: bool = True
    status: Literal["draft", "review", "approved", "active", "obsolete"] = "draft"


class VersionRead(ORMModel, VersionCreate):
    id: str
    version_hash: str | None = None
    active_snapshot_id: str | None = None
    regression_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    software_id: str
    version_id: str
    document_type: Literal[
        "ddl",
        "schema",
        "join_path",
        "glossary",
        "business_rule",
        "approved_query",
        "question_sql_pair",
        "edge_case",
        "forbidden_pattern",
        "gold_test",
        "markdown",
    ]
    title: str
    content: str
    file_name: str | None = None
    tags: list[str] = []
    domain: str | None = None
    source: str | None = None
    sensitivity_level: Literal["public", "internal", "confidential", "restricted"] = "internal"
    replaced_document_id: str | None = None
    change_note: str | None = None


class KnowledgeDocumentRead(ORMModel, KnowledgeDocumentCreate):
    id: str
    checksum: str
    detected_type: str | None = None
    extracted_metadata: dict[str, Any]
    quality_score: float | None = None
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    approval_status: str
    document_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeStandardizeRequest(BaseModel):
    document_ids: list[str]
    software_id: str
    version_id: str
    standardization_type: Literal["metadata", "quality", "relationships", "full"] = "full"
    selected_local_model_id: str | None = None
    use_llm: bool = False
    validator_rules: dict[str, Any] = {}


class KnowledgeStandardizeResult(BaseModel):
    status: Literal["draft", "review", "approved", "rejected", "conflict"]
    documents: list[KnowledgeDocumentRead]
    blockers: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []


class SnapshotPublishRequest(BaseModel):
    software_id: str
    version_id: str
    document_ids: list[str]
    name: str
    release_note: str | None = None
    approvers: list[str] = []
    scheduled_at: datetime | None = None
    mandatory_test_result: dict[str, Any] = Field(default_factory=lambda: {"passed": True})


class SnapshotRead(ORMModel):
    id: str
    software_id: str
    version_id: str
    name: str
    release_note: str | None = None
    approvers: list[str]
    scheduled_at: datetime | None = None
    document_ids: list[str]
    final_hash: str
    conflict_report: dict[str, Any]
    regression_report: dict[str, Any]
    publish_status: str
    previous_snapshot_id: str | None = None
    published_at: datetime | None = None
    created_at: datetime


class SchemaRelationCreate(BaseModel):
    software_id: str
    version_id: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relation_type: Literal["1:1", "1:N", "N:M"]
    join_type: Literal["INNER", "LEFT", "RIGHT", "FULL"] = "INNER"
    nullable: bool = False
    duplicate_risk: Literal["low", "medium", "high"] = "low"
    forbidden_paths: list[str] = []
    verification_source: str | None = None
    approval_status: Literal["draft", "review", "approved", "rejected", "conflict"] = "draft"


class SchemaRelationRead(ORMModel, SchemaRelationCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class SoftwareUserCreate(BaseModel):
    external_user_id: str
    first_name: str | None = None
    last_name: str | None = None
    username: str
    email: EmailStr | None = None
    tenant_id: str | None = None
    organization: str | None = None
    region: list[str] = []
    roles: list[str] = ["report_user"]
    scopes: list[str] = []
    allowed_subjects: list[str] = []
    daily_quota: int | None = None
    monthly_quota: int | None = None
    expires_at: datetime | None = None
    status: Literal["active", "inactive", "suspended"] = "active"
    requires_dedicated_api_key: bool = False
    temporary_password: str = Field(default="ChangeMe!12345", min_length=10)


class APIKeyCreate(BaseModel):
    name: str
    owner_user_id: str | None = None
    software_id: str | None = None
    version_id: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None
    ip_allowlist: list[str] = []
    rate_limit: dict[str, Any] = {"requests_per_minute": 60}
    consumption_limit: dict[str, Any] = {}
    environment: Literal["development", "stage", "production"] = "development"
    mtls_enabled: bool = False
    description: str | None = None


class APIKeyIssued(ORMModel):
    id: str
    prefix: str
    secret: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    note: str = "Secret فقط همین یک‌بار نمایش داده می‌شود."


class APIKeyRead(ORMModel):
    id: str
    name: str
    prefix: str
    owner_user_id: str | None = None
    software_id: str | None = None
    version_id: str | None = None
    scopes: list[str]
    ip_allowlist: list[str]
    rate_limit: dict[str, Any]
    consumption_limit: dict[str, Any]
    environment: str
    mtls_enabled: bool
    status: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_reason: str | None = None
    created_at: datetime


# -------------------------- NL2SQL API contract --------------------------
class AccessContext(BaseModel):
    organization: str | None = None
    region: list[str] = []
    roles: list[str] = []
    scopes: list[str] = []
    allowed_subjects: list[str] = []


class ReportRequestIn(BaseModel):
    request_id: UUID
    software_id: str
    software_version: str
    user_id: str
    question: str = Field(min_length=3, max_length=4000)
    access_context: AccessContext
    locale: str = "fa-IR"
    timezone: str = "Asia/Tehran"


class Confidence(BaseModel):
    score: float = Field(ge=0, le=1)
    level: Literal["low", "medium", "high"]


class ReportPolicy(BaseModel):
    max_rows: int
    timeout_seconds: int
    knowledge_hash: str
    expires_at: datetime | str


class DisplaySpec(BaseModel):
    type: Literal["table", "text", "auto"] = "table"
    title: str
    columns: list[dict[str, Any]] = []
    formats: dict[str, Any] = {}


class ReportSuccess(BaseModel):
    status: Literal["success"] = "success"
    sql: str
    parameters: dict[str, Any]
    display: DisplaySpec
    confidence: Confidence
    audit_id: str
    policy: ReportPolicy


class ReportClarification(BaseModel):
    status: Literal["needs_clarification"] = "needs_clarification"
    audit_id: str
    question: str
    options: list[str]


class ReportRejected(BaseModel):
    status: Literal["rejected"] = "rejected"
    sql: None = None
    audit_id: str
    reason_code: str
    message: str


ReportResponse = ReportSuccess | ReportClarification | ReportRejected


class ReportExecutionResultIn(BaseModel):
    audit_id: str
    execution_time_ms: int
    row_count: int
    display_type: Literal["table", "text"] = "table"
    # Raw data must stay on-premise and is intentionally not part of this contract.


class UserFeedbackCreate(BaseModel):
    audit_id: str
    verdict: Literal["correct", "incorrect", "partially_correct"]
    rating: int = Field(ge=1, le=5)
    description: str | None = None
    problem_type: str | None = None
    manager_review_requested: bool = False


class FeedbackRead(ORMModel):
    id: str
    audit_id: str
    user_verdict: str
    rating: int
    description: str | None = None
    problem_type: str | None = None
    manager_review_requested: bool
    review_status: str
    final_score: float | None = None
    created_at: datetime


class RequestMonitorRead(ORMModel):
    id: str
    audit_id: str
    correlation_id: str | None = None
    user_id: str
    question_redacted: str
    status: str
    generated_sql: str | None = None
    response_time_ms: int | None = None
    prompt_tokens: int
    completion_tokens: int
    cost_amount: float
    confidence_score: float | None = None
    confidence_level: str | None = None
    validator_result: dict[str, Any]
    model_id: str | None = None
    cache_hit: bool
    risk_level: str
    created_at: datetime


class RequestDetailRead(RequestMonitorRead):
    software_id: str
    version_id: str | None = None
    external_software_id: str | None = None
    software_version: str | None = None
    access_context: dict[str, Any]
    intent: str | None = None
    entities: dict[str, Any]
    parameters: dict[str, Any]
    display_spec: dict[str, Any]
    failover_trace: list[dict[str, Any]]
    policy: dict[str, Any]
    rejection_reason_code: str | None = None
    clarification_question: str | None = None
    clarification_options: list[str]


class QualityReviewCreate(BaseModel):
    audit_id: str
    user_verdict: Literal["correct", "incorrect", "partially_correct"]
    rating: int = Field(ge=1, le=5)
    description: str | None = None
    automatic_score: float | None = None
    gold_test_result: dict[str, Any] = {}
    manager_comment: str | None = None
    error_reason: str | None = None
    corrected_sql: str | None = None
    convert_to_recipe: bool = False
    requires_knowledge_fix: bool = False


class RecipeCreate(BaseModel):
    canonical_question: str
    persian_rewrites: list[str] = []
    intent: str
    entities: dict[str, Any] = {}
    software_id: str
    version_id: str
    access_scope: dict[str, Any] = {}
    parameterized_sql: str
    parameter_schema: dict[str, Any] = {}
    display_spec: dict[str, Any] = {}
    ttl_seconds: int = 86400
    approver_id: str | None = None


class RecipeRead(ORMModel, RecipeCreate):
    id: str
    cache_fingerprint: str
    use_count: int
    success_rate: float
    token_savings: int
    cost_savings: float
    expires_at: datetime | None = None
    status: str
    created_at: datetime


class GoldTestCreate(BaseModel):
    question: str
    rewrites: list[str] = []
    software_id: str
    version_id: str
    test_user_context: dict[str, Any] = {}
    expected_intent: str | None = None
    expected_tables: list[str] = []
    expected_joins: list[dict[str, Any]] = []
    expected_filter_sort_grain: dict[str, Any] = {}
    gold_sql: str | None = None
    forbidden_operations: list[str] = []
    max_rows: int = 100
    snapshot_id: str | None = None
    model_id: str | None = None


class GoldTestRead(ORMModel, GoldTestCreate):
    id: str
    last_run_result: dict[str, Any]
    created_at: datetime


class GoldTestRunResult(BaseModel):
    generated_sql: str
    semantic_comparison: dict[str, Any]
    status: Literal["pass", "fail"]
    diff: dict[str, Any]
    security_error: str | None = None
    response_time_ms: int
    prompt_tokens: int
    completion_tokens: int
    regression_report: dict[str, Any]


class ModelPolicyCreate(BaseModel):
    software_id: str
    primary_model_id: str
    fallback_model_ids: list[str] = []
    cloud_allowed: bool = False
    allowed_sensitivity_level: Literal["public", "internal", "confidential", "restricted"] = "internal"
    max_cost: float | None = None
    timeout_seconds: int = 30
    retry_count: int = 1
    failover_rules: dict[str, Any] = {}
    sensitive_query_model_id: str | None = None


# -------------------------- connector --------------------------
class ConnectorRegister(BaseModel):
    connector_id: str
    software_id: str
    version_id: str | None = None
    central_api_url: str
    tls_certificate_ref: str | None = None
    credential_ref: str | None = None
    database_dialect: str = "T-SQL"
    encrypted_connection_string: str
    readonly_account: str
    timeout_seconds: int = 10
    max_rows: int = 100
    allowed_views: list[str] = []
    policy_version: str


class ConnectorRead(ORMModel):
    id: str
    software_id: str
    version_id: str | None = None
    central_api_url: str
    database_dialect: str
    readonly_account: str
    timeout_seconds: int
    max_rows: int
    allowed_views: list[str]
    policy_version: str
    registration_status: str
    central_connection_status: dict[str, Any]
    database_connection_status: dict[str, Any]
    connector_version: str
    policy_hash: str
    last_heartbeat_at: datetime | None = None
    last_policy_sync_at: datetime | None = None
    certificate_status: dict[str, Any]
    communication_errors: list[dict[str, Any]]
    database_latency_ms: int | None = None
    updated_at: datetime


class ConnectorExecutionRequest(BaseModel):
    sql: str
    parameters: dict[str, Any] = {}
    ttl: int | None = None
    signature: str
    policy_hash: str
    audit_id: str


class ConnectorExecutionResponse(BaseModel):
    validation_result: Literal["accepted", "rejected"]
    accepted: bool
    rejection_reason: str | None = None
    execution_time_ms: int | None = None
    row_count: int | None = None
    controlled_error: str | None = None
    execution_metadata: dict[str, Any] = {}


# -------------------------- notifications/system dashboards --------------------------
class BackgroundJobRead(ORMModel):
    id: str
    kind: str
    related_type: str | None = None
    related_id: str | None = None
    status: Literal["queued", "processing", "completed", "failed"]
    progress_percent: int
    result: dict[str, Any]
    error_detail: dict[str, Any]
    link: str | None = None
    created_at: datetime
    updated_at: datetime


class DashboardMetric(BaseModel):
    label: str
    value: int | float | str
    delta_percent: float | None = None


class DashboardResponse(BaseModel):
    filters: dict[str, Any]
    metrics: list[DashboardMetric]
    charts: dict[str, Any]
    alerts: list[dict[str, Any]] = []


class AuditLogRead(ORMModel):
    id: str
    audit_id: str
    correlation_id: str | None = None
    actor_id: str | None = None
    actor_type: str
    action: str
    target_type: str
    target_id: str | None = None
    tenant_id: str | None = None
    software_id: str | None = None
    version_id: str | None = None
    ip: str | None = None
    api_key_prefix: str | None = None
    event_type: str
    severity: str
    before_value: dict[str, Any]
    after_value: dict[str, Any]
    result: str
    rejection_reason: str | None = None
    request_id: str | None = None
    chain: list[str]
    created_at: datetime
