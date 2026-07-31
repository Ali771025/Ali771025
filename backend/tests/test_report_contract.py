from __future__ import annotations

import os
import uuid
from pathlib import Path

TEST_DB = Path(__file__).resolve().parents[1] / "test_nl2sql_reporting.db"
TEST_DB.unlink(missing_ok=True)

os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB}")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("SEED_DEMO_DATA", "true")

from fastapi.testclient import TestClient

from app.main import app


def _valid_payload(question: str) -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "software_id": "behsaz",
        "software_version": "12.4.0",
        "user_id": "user-1025",
        "question": question,
        "access_context": {
            "organization": "municipality-01",
            "region": ["1", "2"],
            "roles": ["report-user"],
            "scopes": ["commission100.read"],
        },
        "locale": "fa-IR",
        "timezone": "Asia/Tehran",
    }


def test_generate_report_success_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reports/generate",
            json=_valid_payload("آخرین پرونده‌های ماده ۱۰۰ را نشان بده"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["sql"].startswith("SELECT TOP (@limit)")
    assert payload["policy"]["max_rows"] == 20
    assert payload["confidence"]["level"] == "high"


def test_generate_report_rejects_out_of_scope() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reports/generate",
            json=_valid_payload("لیست حقوق کارکنان را بده"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "OUT_OF_SCOPE"
