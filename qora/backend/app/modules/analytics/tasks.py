"""Small background-job adapters; a queue can call the same functions at scale."""
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.modules.analytics.service import AnalyticsService
from app.modules.service.service import ServiceRegistry
from app.shared.logging import log


def aggregate_service_day(service_id: int) -> None:
    """Refresh one creator's daily metrics after a session/outcome event."""
    with SessionLocal() as db:
        try:
            service = ServiceRegistry.get(db, service_id)
            AnalyticsService.aggregate_day(
                db,
                bucket_date=datetime.now(timezone.utc).date(),
                creator_id=service.creator_id,
            )
        except Exception as exc:
            db.rollback()
            # Background aggregation must never turn a completed user request into a failure.
            log("analytics").exception("daily aggregation failed for service %s: %s", service_id, exc)
