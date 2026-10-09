"""Phase 4: daily event aggregation, demand insights and regression evaluation."""
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.analytics.models import CreatorMetric
from app.modules.analytics.service import AnalyticsService
from app.modules.identity.service import IdentityService
from app.modules.outcome.models import OutcomeRecord
from app.modules.runtime.service import RuntimeService
from app.modules.service.service import ServiceRegistry
from evaluation.harness import run_evaluation


def test_daily_pipeline_and_real_demand_insight(client, sarah):
    now = datetime.now(timezone.utc)
    today = now.date()
    day_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    with SessionLocal() as db:
        creator = IdentityService.get_by_email(db, "sarah@qora.ai")
        from app.modules.profile.service import ProfileService

        profile = ProfileService.get_creator_or_404(db, creator.id)
        service = ServiceRegistry.list_by_creator(db, profile.id)[0]
        version = ServiceRegistry.current_version(db, service)
        emma = IdentityService.get_by_email(db, "emma@qora.ai")
        omar = IdentityService.get_by_email(db, "omar@qora.ai")

        # One earlier visit plus two current-day sessions verifies return-user attribution.
        previous = RuntimeService.start_session(db, emma.id, service.id, version.id, None)
        previous.status = "completed"
        previous.started_at = day_start - timedelta(hours=2)
        previous.finished_at = day_start - timedelta(hours=1)

        sessions = []
        for offset, user in enumerate((emma, omar), start=1):
            session = RuntimeService.start_session(db, user.id, service.id, version.id, None)
            session.status = "completed"
            session.started_at = day_start + timedelta(hours=offset)
            session.finished_at = session.started_at + timedelta(minutes=5)
            sessions.append(session)
            db.add(OutcomeRecord(
                session_id=session.id,
                service_id=service.id,
                user_id=user.id,
                status="SUCCESS",
                score=0.9,
                signals={"service": 1, "completion": 1, "structured": 1},
                user_confirmed=True,
                evaluated_at=session.finished_at,
            ))
            RuntimeService.record_event(db, session.id, "unmet_request", {
                "note": "Please add a shorter checklist with practical examples and more prompt detail",
                "person_key": f"person-{user.id}",
                "source": "explicit_outcome_feedback",
                "active": True,
            })
        db.commit()

        result = AnalyticsService.aggregate_day(db, today, profile.id)
        assert result["services_aggregated"] >= 1
        bucket = db.scalar(select(CreatorMetric).where(
            CreatorMetric.service_id == service.id,
            CreatorMetric.bucket_date == today,
        ))
        assert bucket is not None
        assert bucket.users_count >= 2
        assert bucket.sessions_count >= 2
        assert bucket.successful_sessions >= 2
        assert bucket.returned_users >= 1
        assert bucket.useful_votes >= 2
        assert bucket.unmet_request_count == 2

    inbox = client.get("/api/v1/creator/analytics/insights", headers=sarah)
    assert inbox.status_code == 200
    reports = inbox.json()["items"]
    insight = next(row for row in reports if row["kind"] == "demand_cluster")
    assert "2 users asked for" in insight["summary"]
    assert insight["evidence"]["session_count"] == 2
    assert "prompt" not in insight["summary"].lower()

    overview = client.get("/api/v1/creator/analytics/overview", headers=sarah).json()
    assert overview["daily"]
    assert any(row["service_id"] == insight["service_id"] for row in overview["per_service"])

    dismissed = client.post(
        f"/api/v1/creator/analytics/insights/{insight['id']}/dismiss", headers=sarah
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"


def test_evaluation_harness_regressions():
    report = run_evaluation()
    assert report["intent"]["cases"] >= 10
    assert report["intent"]["passed"] == report["intent"]["cases"], report["intent"]["results"]
    assert report["outcome"]["passed"] == report["outcome"]["cases"], report["outcome"]["results"]
