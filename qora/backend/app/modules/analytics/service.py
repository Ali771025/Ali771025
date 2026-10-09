"""Event pipeline, daily creator metrics, and evidence-backed creator insights [PRD Phase 4].

All cross-module reads go through service interfaces; raw private profile data is never queried.
"""
import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.analytics.models import CreatorMetric, InsightReport
from app.modules.qualification.simulation import SimulationEngine
from app.modules.service.service import ServiceRegistry
from app.shared.errors import FORBIDDEN, NOT_FOUND, AppError

TECH_TERMS = re.compile(r"\b(rag|embeddings?|prompts?)\b", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "for", "from", "help", "i", "in",
    "is", "it", "me", "my", "of", "on", "or", "please", "the", "this", "to", "we", "with", "you", "your",
}


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _safe_request(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\+?\d[\d\s().-]{7,}\d", " ", text)
    text = TECH_TERMS.sub(" ", text)
    return " ".join(text.split())[:180]


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[\w'-]+", _safe_request(text), flags=re.UNICODE)
        if len(token) > 2 and token not in STOPWORDS
    }


class AnalyticsService:
    @staticmethod
    def _owned(db: Session, creator_id: int, service_id: int):
        for service in ServiceRegistry.list_by_creator(db, creator_id):
            if service.id == service_id:
                return service
        ServiceRegistry.get(db, service_id)
        raise AppError(FORBIDDEN, "Not your service", 403)

    @staticmethod
    def service_metrics(db: Session, creator_id: int, service_id: int) -> dict:
        from app.modules.outcome.service import OutcomeService
        from app.modules.runtime.service import RuntimeService

        AnalyticsService._owned(db, creator_id, service_id)
        sessions = RuntimeService.sessions_for_service(db, service_id)
        outcomes = OutcomeService.list_for_service(db, service_id)
        users = {row["user_id"] for row in sessions}
        sessions_by_user: dict[int, int] = defaultdict(int)
        for row in sessions:
            if row.get("status") == "completed":
                sessions_by_user[row["user_id"]] += 1
        returned = sum(count >= 2 for count in sessions_by_user.values())
        successful = [row for row in outcomes if row["status"] == "SUCCESS"]
        useful = [row for row in outcomes if row["user_confirmed"]]
        unmet = [
            event for event in RuntimeService.session_events_for_service(db, service_id, kind="unmet_request")
            if (event.get("payload") or {}).get("active", True)
        ]
        return {
            "service_id": service_id,
            "users_count": len(users),
            "sessions": len(sessions),
            "successful_sessions": len(successful),
            "returned_users": returned,
            "useful_votes": len(useful),
            "unmet_request_count": len({event["session_id"] for event in unmet}),
            "success_rate": round(len(successful) / max(len(outcomes), 1), 3),
        }

    @staticmethod
    def aggregate_day(db: Session, bucket_date: date | None = None, creator_id: int | None = None) -> dict:
        """Idempotently recompute one daily bucket from session/outcome/event sources."""
        from app.modules.outcome.service import OutcomeService
        from app.modules.runtime.service import RuntimeService

        day = bucket_date or datetime.now(timezone.utc).date()
        if creator_id is None:
            services = ServiceRegistry.list_all_for_analytics(db)
        else:
            services = ServiceRegistry.list_by_creator(db, creator_id)
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        updated = 0
        for service in services:
            all_sessions = RuntimeService.sessions_for_service(db, service.id)
            day_sessions = [
                row for row in all_sessions
                if row.get("started_at") and start <= _naive_utc(row["started_at"]) < end
            ]
            day_users = {row["user_id"] for row in day_sessions}
            prior_users = {
                row["user_id"] for row in all_sessions
                if row.get("started_at") and _naive_utc(row["started_at"]) < start
            }
            outcomes = OutcomeService.list_for_service(db, service.id)
            day_outcomes = [
                row for row in outcomes
                if row.get("evaluated_at") and start <= _naive_utc(row["evaluated_at"]) < end
            ]
            events = RuntimeService.session_events_for_service(
                db, service.id, kind="unmet_request", since=start
            )
            day_events = [
                event for event in events
                if event.get("at") and _naive_utc(event["at"]) < end
                and (event.get("payload") or {}).get("active", True)
            ]
            metric = db.scalar(select(CreatorMetric).where(
                CreatorMetric.service_id == service.id,
                CreatorMetric.bucket_date == day,
            ))
            if metric is None:
                metric = CreatorMetric(service_id=service.id, creator_id=service.creator_id, bucket_date=day)
                db.add(metric)
            metric.creator_id = service.creator_id
            metric.users_count = len(day_users)
            metric.sessions_count = len(day_sessions)
            metric.successful_sessions = sum(row["status"] == "SUCCESS" for row in day_outcomes)
            metric.returned_users = len(day_users & prior_users)
            metric.useful_votes = sum(bool(row["user_confirmed"]) for row in day_outcomes)
            metric.unmet_request_count = len({event["session_id"] for event in day_events})
            updated += 1
        db.commit()

        creator_ids = {service.creator_id for service in services} if creator_id is None else {creator_id}
        insight_count = sum(AnalyticsService.generate_demand_insights(db, cid) for cid in creator_ids)
        return {"bucket_date": day.isoformat(), "services_aggregated": updated, "new_or_updated_insights": insight_count}

    @staticmethod
    def daily_metrics(db: Session, creator_id: int, days: int = 30) -> list[dict]:
        start = datetime.now(timezone.utc).date() - timedelta(days=max(1, min(days, 90)) - 1)
        rows = db.scalars(
            select(CreatorMetric)
            .where(CreatorMetric.creator_id == creator_id, CreatorMetric.bucket_date >= start)
            .order_by(CreatorMetric.bucket_date)
        ).all()
        grouped: dict[str, dict] = {}
        for row in rows:
            key = row.bucket_date.isoformat()
            totals = grouped.setdefault(key, {
                "date": key,
                "users": 0,
                "sessions": 0,
                "successful_sessions": 0,
                "returned_users": 0,
                "useful_votes": 0,
                "unmet_request_count": 0,
            })
            for field, target in (
                ("users_count", "users"),
                ("sessions_count", "sessions"),
                ("successful_sessions", "successful_sessions"),
                ("returned_users", "returned_users"),
                ("useful_votes", "useful_votes"),
                ("unmet_request_count", "unmet_request_count"),
            ):
                totals[target] += getattr(row, field)
        return list(grouped.values())

    @staticmethod
    def overview(db: Session, creator_id: int) -> dict:
        from app.modules.outcome.service import OutcomeService
        from app.modules.runtime.service import RuntimeService

        services = ServiceRegistry.list_by_creator(db, creator_id)
        service_rows = []
        totals = {
            "services": len(services),
            "users": 0,
            "sessions": 0,
            "successful_sessions": 0,
            "returned_users": 0,
            "useful_votes": 0,
            "unmet_request_count": 0,
        }
        for service in services:
            metrics = AnalyticsService.service_metrics(db, creator_id, service.id)
            for key in ("users_count", "sessions", "successful_sessions", "returned_users", "useful_votes", "unmet_request_count"):
                totals_key = "users" if key == "users_count" else key
                totals[totals_key] += metrics[key]
            service_rows.append({"service_id": service.id, "name": service.name, **metrics})

        # The current UTC day is cheap to recompute and makes the dashboard reflect new sessions.
        AnalyticsService.aggregate_day(db, creator_id=creator_id)
        insights = AnalyticsService.insight_inbox(db, creator_id, generate=False)
        return {
            "totals": totals,
            "per_service": service_rows,
            "daily": AnalyticsService.daily_metrics(db, creator_id),
            "insights": insights,
        }

    @staticmethod
    def generate_demand_insights(db: Session, creator_id: int, days: int = 30) -> int:
        """Cluster explicit, anonymized unmet-request signals and persist evidence-backed reports."""
        from app.modules.runtime.service import RuntimeService

        services = ServiceRegistry.list_by_creator(db, creator_id)
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, min(days, 90)))
        changed = 0
        for service in services:
            events = RuntimeService.session_events_for_service(
                db, service.id, kind="unmet_request", since=since
            )
            records = []
            for event in events:
                payload = event.get("payload") or {}
                if not payload.get("active", True):
                    continue
                note = _safe_request(payload.get("note", ""))
                tokens = _tokens(note)
                if len(tokens) < 2:
                    continue
                records.append({
                    "note": note,
                    "tokens": tokens,
                    "session_id": event["session_id"],
                    "person_key": payload.get("person_key") or f"session:{event['session_id']}",
                })
            clusters: list[dict] = []
            for record in records:
                best = None
                best_overlap = 0.0
                for cluster in clusters:
                    union = record["tokens"] | cluster["tokens"]
                    overlap = len(record["tokens"] & cluster["tokens"]) / max(len(union), 1)
                    if overlap > best_overlap:
                        best, best_overlap = cluster, overlap
                if best is not None and best_overlap >= 0.34:
                    best["records"].append(record)
                    best["tokens"].update(record["tokens"])
                else:
                    clusters.append({"tokens": set(record["tokens"]), "records": [record]})

            for cluster in clusters:
                person_keys = {row["person_key"] for row in cluster["records"]}
                session_ids = sorted({row["session_id"] for row in cluster["records"]})
                if len(person_keys) < 2:
                    continue
                phrase = max((row["note"] for row in cluster["records"]), key=len)[:120]
                summary = f"{len(person_keys)} users asked for: {phrase}"
                suggestion = f"Consider adding clearer guidance or a concrete example for ‘{phrase}’."
                stable_terms = " ".join(sorted(cluster["tokens"]))[:240]
                signature = hashlib.sha256(f"{service.id}:demand_cluster:{stable_terms}".encode()).hexdigest()
                report = db.scalar(select(InsightReport).where(InsightReport.signature == signature))
                evidence = {
                    "user_count": len(person_keys),
                    "session_count": len(session_ids),
                    "session_ids": session_ids[:25],
                    "period_days": days,
                }
                if report is None:
                    report = InsightReport(
                        service_id=service.id,
                        creator_id=creator_id,
                        kind="demand_cluster",
                        signature=signature,
                        summary=summary,
                        suggested_update=suggestion,
                        evidence=evidence,
                        status="new",
                    )
                    db.add(report)
                else:
                    report.summary = summary
                    report.suggested_update = suggestion
                    report.evidence = evidence
                changed += 1
        db.commit()
        return changed

    @staticmethod
    def insight_inbox(db: Session, creator_id: int, generate: bool = True) -> list[dict]:
        if generate:
            AnalyticsService.generate_demand_insights(db, creator_id)
        services = ServiceRegistry.list_by_creator(db, creator_id)
        ids = [service.id for service in services]
        if not ids:
            return []
        rows = db.scalars(
            select(InsightReport)
            .where(InsightReport.creator_id == creator_id)
            .order_by(InsightReport.created_at.desc())
        ).all()
        service_name = {service.id: service.name for service in services}
        results = []
        for row in rows:
            value = row.as_dict()
            value["service_name"] = service_name.get(row.service_id, "Service")
            results.append(value)
        return results

    @staticmethod
    def mark_insight(db: Session, creator_id: int, insight_id: int, status: str) -> dict:
        if status not in ("dismissed", "acted_on"):
            raise AppError(FORBIDDEN, "Insight status must be dismissed or acted_on", 400)
        report = db.get(InsightReport, insight_id)
        if not report or report.creator_id != creator_id:
            raise AppError(NOT_FOUND, "Insight not found", 404)
        report.status = status
        db.commit()
        return report.as_dict()

    @staticmethod
    def insights(db: Session, creator_id: int, service_id: int) -> list[dict]:
        from app.modules.outcome.service import OutcomeService

        AnalyticsService._owned(db, creator_id, service_id)
        reports = [
            item for item in AnalyticsService.insight_inbox(db, creator_id)
            if item["service_id"] == service_id
        ]
        sim = SimulationEngine.latest_for_service(db, service_id)
        if sim and (sim.summary or {}).get("avg_score", 1) < 0.85:
            weak = [kind for kind, score in ((sim.summary or {}).get("per_kind") or {}).items() if score < 0.8]
            if weak:
                reports.append({
                    "kind": "knowledge_gap",
                    "summary": f"Testing shows weak handling of: {', '.join(weak)} — strengthen the service guidance.",
                    "suggested_update": "Review the service boundaries and add a practical example.",
                    "evidence": {"weak_kinds": weak},
                    "status": "new",
                    "service_id": service_id,
                })
        outcomes = OutcomeService.list_for_service(db, service_id)
        partial = [row for row in outcomes if row["status"] == "PARTIAL"]
        if partial:
            reports.append({
                "kind": "improvement",
                "summary": f"{len(partial)} sessions ended with a partial result — users may need a clearer deliverable.",
                "suggested_update": "Make the expected end result more concrete.",
                "evidence": {"partial_sessions": len(partial)},
                "status": "new",
                "service_id": service_id,
            })
        return reports
