from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/meta", tags=["کاتالوگ محصول و معماری"])

PAGE_COUNTS = {
    "public": 4,
    "owner": 15,
    "software_admin": 19,
    "on_premise": 4,
    "connector": 3,
    "total": 45,
}

API_DOMAINS = [
    {"domain": "auth", "apis": ["Login", "Refresh", "Logout", "MFA", "Sessions"]},
    {"domain": "tenant", "apis": ["CRUD", "Suspend", "Policies", "Usage"]},
    {"domain": "software", "apis": ["CRUD", "Dependencies", "Settings"]},
    {"domain": "versions", "apis": ["Create", "Clone", "Compare", "Approve", "Activate"]},
    {"domain": "knowledge", "apis": ["Upload", "Parse", "Validate", "Version", "Diff"]},
    {"domain": "standardization", "apis": ["Create Job", "Progress", "Result", "Retry"]},
    {"domain": "snapshot", "apis": ["Build", "Test", "Publish", "Rollback"]},
    {"domain": "schema_graph", "apis": ["Nodes", "Edges", "Validate Path"]},
    {"domain": "users", "apis": ["CRUD", "Mapping", "Roles", "Quota"]},
    {"domain": "api_keys", "apis": ["Issue", "Rotate", "Revoke", "Usage"]},
    {"domain": "nl2sql", "apis": ["Generate", "Clarify", "Reject", "Feedback"]},
    {"domain": "requests", "apis": ["List", "Detail", "Timeline", "Review"]},
    {"domain": "quality", "apis": ["Evaluate", "Correct", "Create Recipe"]},
    {"domain": "gold_tests", "apis": ["CRUD", "Run", "Regression Report"]},
    {"domain": "models", "apis": ["CRUD", "Health", "Test", "Routing Policy"]},
    {"domain": "finance", "apis": ["Tariff", "Wallet", "Ledger", "Payment"]},
    {"domain": "audit", "apis": ["Search", "Detail", "Export"]},
    {"domain": "connector", "apis": ["Register", "Heartbeat", "Policy Sync", "Validate Execute"]},
]


@router.get("/product-map")
def product_map() -> dict:
    return {
        "name": "Smart Report Builder & NL2SQL",
        "page_counts": PAGE_COUNTS,
        "environments": [
            {"key": "owner", "title": "پنل مالک سامانه", "purpose": "مدیریت کل سامانه، سازمان‌ها، مدیران، مدل‌ها، مالی و زیرساخت"},
            {"key": "software_admin", "title": "پنل مدیر نرم‌افزار", "purpose": "مدیریت نسخه، دانش، کاربران، دسترسی، تست و انتشار"},
            {"key": "on_premise", "title": "رابط داخل نرم‌افزار On-Premise", "purpose": "ثبت درخواست فارسی، اجرای گزارش و ارسال بازخورد"},
            {"key": "connector", "title": "کنسول Connector", "purpose": "اتصال امن، اعتبارسنجی و اجرای محلی SQL"},
        ],
        "security_principle": "Raw customer query results must never leave the customer network.",
    }


@router.get("/api-catalog")
def api_catalog() -> dict:
    return {
        "cross_cutting_headers": ["X-Request-ID", "X-Correlation-ID", "Idempotency-Key for mutations"],
        "domains": API_DOMAINS,
        "sensitive_data_never_returned": [
            "API Key کامل",
            "Access Token",
            "Refresh Token",
            "Password",
            "Connection String",
            "Model Secret",
            "Raw Customer Report Data",
            "Model Chain-of-Thought",
        ],
    }
