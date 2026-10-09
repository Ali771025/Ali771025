"""Rebuild today's metric buckets for all services (suitable for a daily scheduler)."""
from app.core.db import SessionLocal
from app.modules.analytics.service import AnalyticsService


if __name__ == "__main__":
    with SessionLocal() as db:
        print(AnalyticsService.aggregate_day(db))
