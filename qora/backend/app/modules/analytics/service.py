"""Creator Analytics v1 — session signals → metrics → insight reports.

'17 users asked for a shorter checklist' — insights come from real session signals [PRD feature].
Full event pipeline lands in Phase 4; v1 computes from outcome/session records.
All cross-module data access goes through service interfaces (boundary rule).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.qualification.simulation import SimulationEngine
from app.modules.service.service import ServiceRegistry
from app.shared.errors import FORBIDDEN, NOT_FOUND, AppError


class AnalyticsService:
    @staticmethod
    def _owned(db: Session, creator_id: int, service_id: int):
        for s in ServiceRegistry.list_by_creator(db, creator_id):
            if s.id == service_id:
                return s
        ServiceRegistry.get(db, service_id)  # raises 404 if the service does not exist
        raise AppError(FORBIDDEN, "Not your service", 403)

    @staticmethod
    def service_metrics(db: Session, creator_id: int, service_id: int) -> dict:
        from app.modules.outcome.service import OutcomeService
        from app.modules.runtime.service import RuntimeService

        AnalyticsService._owned(db, creator_id, service_id)
        sessions = RuntimeService.sessions_for_service(db, service_id)
        outcomes = OutcomeService.list_for_service(db, service_id)

        users = {s["user_id"] for s in sessions}
        returned = len([u for u in users if sum(1 for s in sessions if s["user_id"] == u) > 1])
        successful = [o for o in outcomes if o["status"] in ("SUCCESS", "PARTIAL")]
        useful = [o for o in outcomes if o["user_confirmed"]]
        return {
            "service_id": service_id,
            "users_count": len(users),
            "sessions": len(sessions),
            "successful_sessions": len(successful),
            "returned_users": returned,
            "useful_votes": len(useful),
            "success_rate": round(len(successful) / max(len(outcomes), 1), 3),
        }

    @staticmethod
    def insights(db: Session, creator_id: int, service_id: int) -> list[dict]:
        from app.modules.outcome.service import OutcomeService

        AnalyticsService._owned(db, creator_id, service_id)
        reports: list[dict] = []

        sim = SimulationEngine.latest_for_service(db, service_id)
        if sim and (sim.summary or {}).get("avg_score", 1) < 0.85:
            weak = [k for k, v in ((sim.summary or {}).get("per_kind") or {}).items() if v < 0.8]
            if weak:
                reports.append({
                    "kind": "knowledge_gap",
                    "summary": f"Simulation shows weak handling of: {', '.join(weak)} — strengthen boundaries or behavior.",
                    "evidence": {"weak_kinds": weak},
                    "status": "new",
                })

        outcomes = OutcomeService.list_for_service(db, service_id)
        partial = [o for o in outcomes if o["status"] == "PARTIAL"]
        if partial:
            reports.append({
                "kind": "improvement",
                "summary": f"{len(partial)} sessions ended as PARTIAL — users may need a clearer deliverable definition.",
                "evidence": {"partial_sessions": len(partial)},
                "status": "new",
            })
        return reports

    @staticmethod
    def overview(db: Session, creator_id: int) -> dict:
        services = ServiceRegistry.list_by_creator(db, creator_id)
        totals = {"services": len(services), "users": 0, "successful_sessions": 0, "useful_votes": 0}
        per_service = []
        for s in services:
            m = AnalyticsService.service_metrics(db, creator_id, s.id)
            totals["users"] += m["users_count"]
            totals["successful_sessions"] += m["successful_sessions"]
            totals["useful_votes"] += m["useful_votes"]
            per_service.append({"service_id": s.id, "name": s.name, **m})
        return {"totals": totals, "per_service": per_service}
