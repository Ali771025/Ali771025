from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_nl2sql_reporting.db")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("SEED_DEMO_DATA", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


client = TestClient(app)


def test_generate_report_success_contract() -> None:
    response = client.post(
        "/api/v1/reports/generate",
        json={
            "request_id": str(uuid.uuid4()),
            "software_id": "behsaz",
            "software_version": "12.4.0",
            "user_id": "user-1025",
            "question": "آخرین پرونده‌های ماده ۱۰۰ را نشان بده",
            "access_context": {
                "organization": "municipality-01",
                "region": ["1", "2"],
                "roles": ["report-user"],
                "scopes": ["commission100.read"],
            },
            "locale": "fa-IR",
            "timezone": "Asia/Tehran",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["sql"].startswith("SELECT TOP (@limit)")
    assert payload["policy"]["max_rows"] == 20
    assert payload["confidence"]["level"] == "high"


def test_generate_report_rejects_out_of_scope() -> None:
    response = client.post(
        "/api/v1/reports/generate",
        json={
            "request_id": str(uuid.uuid4()),
            "software_id": "behsaz",
            "software_version": "12.4.0",
            "user_id": "user-1025",
            "question": "لیست حقوق کارکنان را بده",
            "access_context": {"organization": "municipality-01", "region": ["1"], "roles": ["report-user"], "scopes": ["commission100.read"]},
            "locale": "fa-IR",
            "timezone": "Asia/Tehran",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["reason_code"] == "OUT_OF_SCOPE"
