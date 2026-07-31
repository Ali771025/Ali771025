from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.domain import AIModel, SoftwareProduct, SoftwareVersion, Tenant, User
from app.services.knowledge import checksum


def seed_minimum_data(db: Session) -> None:
    """Seed local development with the Behsaz pilot domain and owner account."""

    tenant = db.scalar(select(Tenant).where(Tenant.code == "municipality-01"))
    if not tenant:
        tenant = Tenant(
            code="municipality-01",
            name="شهرداری نمونه پایلوت",
            contact_info={"email": "admin@example.local", "phone": "+982100000"},
            cloud_model_policy="restricted",
            security_policy={"mfa_required_for_admins": True, "redaction": True},
        )
        db.add(tenant)
        db.flush()

    owner = db.scalar(select(User).where(User.username == "owner"))
    if not owner:
        owner = User(
            tenant_id=tenant.id,
            username="owner",
            email="owner@example.local",
            first_name="مالک",
            last_name="سامانه",
            hashed_password=get_password_hash("OwnerChangeMe!12345"),
            roles=["system_owner"],
            scopes=["*"],
            organization="municipality-01",
            region=["1", "2"],
            mfa_required=False,
            mfa_enabled=False,
        )
        db.add(owner)
        db.flush()
        tenant.responsible_manager_id = owner.id

    admin = db.scalar(select(User).where(User.username == "software-admin"))
    if not admin:
        admin = User(
            tenant_id=tenant.id,
            username="software-admin",
            email="software-admin@example.local",
            first_name="مدیر",
            last_name="نرم‌افزار",
            hashed_password=get_password_hash("AdminChangeMe!12345"),
            roles=["software_admin"],
            scopes=["commission100.read", "permits.read", "payments.read"],
            organization="municipality-01",
            region=["1", "2"],
            mfa_required=True,
        )
        db.add(admin)
        db.flush()

    report_user = db.scalar(select(User).where(User.username == "report-user"))
    if not report_user:
        report_user = User(
            tenant_id=tenant.id,
            external_user_id="user-1025",
            username="report-user",
            email="report-user@example.local",
            first_name="کاربر",
            last_name="گزارش",
            hashed_password=get_password_hash("UserChangeMe!12345"),
            roles=["report_user"],
            scopes=["commission100.read"],
            organization="municipality-01",
            region=["1", "2"],
        )
        db.add(report_user)
        db.flush()

    model = db.scalar(select(AIModel).where(AIModel.provider == "local", AIModel.name == "nl2sql-local"))
    if not model:
        model = AIModel(
            provider="local",
            name="nl2sql-local",
            version="0.1",
            hosting_type="local",
            endpoint="http://local-model:8080/v1/chat/completions",
            context_length=8192,
            timeout_seconds=20,
            priority=10,
            allowed_tenants=[tenant.id],
            allowed_sensitivity_levels=["public", "internal", "confidential"],
            health_status={"status": "unknown", "last_test": None},
        )
        db.add(model)
        db.flush()

    software = db.scalar(select(SoftwareProduct).where(SoftwareProduct.code == "behsaz"))
    if not software:
        software = SoftwareProduct(
            tenant_id=tenant.id,
            code="behsaz",
            name="بهساز",
            owner_company="مشتری پایلوت",
            responsible_manager_id=admin.id,
            description="نرم‌افزار On-Premise پایلوت برای گزارش‌ساز هوشمند و NL2SQL",
            product_type="standalone",
            database_dialect="T-SQL",
            default_schema="dbo",
            default_model_id=model.id,
            security_policy={"cloud_allowed": False, "raw_data_export": False},
            access_policy={"max_rows": 20, "timeout_seconds": 10, "allowed_scopes": ["commission100.read"]},
        )
        db.add(software)
        db.flush()

    version = db.scalar(
        select(SoftwareVersion).where(
            SoftwareVersion.software_id == software.id,
            SoftwareVersion.version_number == "12.4.0",
        )
    )
    if not version:
        version = SoftwareVersion(
            software_id=software.id,
            version_number="12.4.0",
            title="نسخه پایلوت بهساز",
            build_number="pilot-001",
            database_dialect="T-SQL",
            schema_version="12.4",
            status="active",
            version_hash=checksum("behsaz:12.4.0:pilot"),
            regression_result={"status": "not_run", "required_gold_tests": 20},
        )
        db.add(version)

    db.commit()
