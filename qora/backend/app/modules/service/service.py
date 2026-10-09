"""Service registry — CRUD, versioning, lifecycle, discovery ranking (API_CONTRACT §6)."""
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.service.models import (
    ALLOWED_TRANSITIONS,
    AiService,
    FollowedService,
    LifecycleTransition,
    ServiceCapabilityMap,
    ServiceIntentMap,
    ServiceVersion,
)
from app.shared.errors import CONFLICT, FORBIDDEN, NOT_FOUND, AppError


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "service"


def _freshness(published_at) -> float:
    if not published_at:
        return 0.5
    age = (datetime.now(timezone.utc) - published_at.replace(tzinfo=timezone.utc)).days
    return 1.0 if age < 30 else 0.7 if age < 90 else 0.4


class ServiceRegistry:
    # ---------- create ----------
    @staticmethod
    def create(db: Session, creator_profile_id: int, data: dict) -> AiService:
        slug = slugify(data["name"])
        if db.scalar(select(AiService).where(AiService.slug == slug)):
            slug = f"{slug}-{creator_profile_id}"
        svc = AiService(
            creator_id=creator_profile_id,
            slug=slug,
            name=data["name"],
            summary=data.get("summary", ""),
            description=data.get("description", ""),
            purpose=data.get("purpose", ""),
            audience=data.get("audience", ""),
            category=data.get("category", "general"),
            risk_level=data.get("risk_level", "LOW"),
        )
        db.add(svc)
        db.flush()
        ServiceRegistry._link_graph(db, svc.id, data.get("intent_slugs", []), data.get("capability_slugs", []))
        db.commit()
        db.refresh(svc)
        return svc

    @staticmethod
    def _link_graph(db: Session, service_id: int, intent_slugs: list[str], cap_slugs: list[str]):
        from app.modules.intent.service import IntentService  # interface import

        ids = IntentService.ids_for_slugs(db, intent_slugs, cap_slugs)
        for slug in intent_slugs:
            if slug in ids:
                db.add(ServiceIntentMap(service_id=service_id, intent_id=ids[slug], relevance=0.85))
        for slug in cap_slugs:
            if slug in ids:
                db.add(ServiceCapabilityMap(service_id=service_id, capability_id=ids[slug]))

    # ---------- versions ----------
    @staticmethod
    def add_version(db: Session, service: AiService, data: dict) -> ServiceVersion:
        n = len(db.scalars(select(ServiceVersion).where(ServiceVersion.service_id == service.id)).all()) + 1
        v = ServiceVersion(service_id=service.id, version_no=n, **data)
        db.add(v)
        db.flush()
        service.current_version_id = v.id
        if service.lifecycle_status == "published":
            ServiceRegistry._transition(db, service, "updated", "new version created")
        db.commit()
        db.refresh(v)
        return v

    @staticmethod
    def get_version(db: Session, version_id: int) -> ServiceVersion | None:
        return db.get(ServiceVersion, version_id)

    @staticmethod
    def current_version(db: Session, service: AiService) -> ServiceVersion | None:
        return db.get(ServiceVersion, service.current_version_id) if service.current_version_id else None

    # ---------- lifecycle ----------
    ACTION_MAP = {
        "submit_test": "ready_for_test",
        "request_qualification": "qualification_pending",
        "publish": "published",
        "pause": "unlisted",
        "unlist": "unlisted",
        "improve": "improve",
        "rollback": "draft",
    }

    @staticmethod
    def lifecycle(db: Session, service: AiService, actor_id: int, action: str, reason: str = "") -> AiService:
        target = ServiceRegistry.ACTION_MAP[action]
        if action == "publish" and service.lifecycle_status == "ready":
            pass
        ServiceRegistry._transition(db, service, target, reason, actor_id)
        db.commit()
        db.refresh(service)
        return service

    @staticmethod
    def _transition(db: Session, service: AiService, to_status: str, reason: str, actor_id: int | None = None):
        from_status = service.lifecycle_status
        if to_status not in ALLOWED_TRANSITIONS.get(from_status, []):
            raise AppError(
                CONFLICT,
                f"Cannot move service from '{from_status}' to '{to_status}'",
                409,
                [{"allowed": ALLOWED_TRANSITIONS.get(from_status, [])}],
            )
        service.lifecycle_status = to_status
        if to_status == "published":
            service.visibility = "public"
            service.published_at = service.published_at or datetime.now(timezone.utc)
        if to_status == "unlisted":
            service.visibility = "unlisted"
        db.add(LifecycleTransition(
            service_id=service.id, from_status=from_status, to_status=to_status,
            actor_id=actor_id or 0, reason=reason,
        ))

    # ---------- queries ----------
    @staticmethod
    def get(db: Session, service_id: int) -> AiService:
        s = db.get(AiService, service_id)
        if not s:
            raise AppError(NOT_FOUND, "Service not found", 404)
        return s

    @staticmethod
    def owned(db: Session, service_id: int, creator_profile_id: int) -> AiService:
        s = ServiceRegistry.get(db, service_id)
        if s.creator_id != creator_profile_id:
            raise AppError(FORBIDDEN, "Not your service", 403)
        return s

    @staticmethod
    def versions_of(db: Session, service_id: int) -> list[ServiceVersion]:
        return list(db.scalars(select(ServiceVersion).where(ServiceVersion.service_id == service_id).order_by(ServiceVersion.version_no.desc())).all())

    # ---------- follow [PRD: add to personal toolkit] ----------
    @staticmethod
    def follow(db: Session, user_id: int, service_id: int, follow: bool = True):
        row = db.get(FollowedService, (user_id, service_id))
        if follow and not row:
            db.add(FollowedService(user_id=user_id, service_id=service_id))
        elif not follow and row:
            db.delete(row)
        db.commit()

    @staticmethod
    def followed_ids(db: Session, user_id: int) -> set[int]:
        return {r.service_id for r in db.scalars(select(FollowedService).where(FollowedService.user_id == user_id)).all()}

    # ---------- discovery / matching with PRD ranking signals ----------
    @staticmethod
    def discover(db: Session, user_id: int | None, query_intent_slug: str | None = None, q: str | None = None, limit: int = 20) -> list[dict]:
        from app.modules.outcome.service import OutcomeService  # interface import
        from app.modules.profile.service import ProfileService

        rows = db.scalars(select(AiService).where(AiService.lifecycle_status == "published")).all()
        if q:
            low = q.lower()
            rows = [s for s in rows if low in (s.name + s.summary + s.description + s.category).lower()]

        intent_ids: dict[int, str] = {}
        if query_intent_slug:
            from app.modules.intent.service import IntentService

            ids = IntentService.ids_for_slugs(db, [query_intent_slug], [])
            if query_intent_slug in ids:
                intent_ids[ids[query_intent_slug]] = query_intent_slug

        outcome_stats = OutcomeService.get_service_outcome_stats(db)
        followed = ServiceRegistry.followed_ids(db, user_id) if user_id else set()

        w = settings
        scored = []
        for s in rows:
            # intent relevance
            rel = 0.3
            if intent_ids:
                maps = db.scalars(select(ServiceIntentMap).where(ServiceIntentMap.service_id == s.id)).all()
                rel = max([m.relevance for m in maps if m.intent_id in intent_ids] or [0.15])
            st = outcome_stats.get(s.id, {})
            success_rate = float(st.get("success_rate", 0.5))
            satisfaction = float(st.get("confirmed_rate", 0.5))
            creator = ProfileService.get_creator_by_id(db, s.creator_id)
            trust = float(creator.trust_score) if creator else 0.5
            personal_fit = 1.0 if s.id in followed else 0.5
            fresh = _freshness(s.published_at)
            exploration = 0.5
            score = (
                w.RANK_W_INTENT * rel
                + w.RANK_W_OUTCOME * success_rate
                + w.RANK_W_PERSONAL_FIT * personal_fit
                + w.RANK_W_TRUST * trust
                + w.RANK_W_FRESHNESS * fresh
                + w.RANK_W_EXPLORATION * exploration
                + w.RANK_W_SATISFACTION * satisfaction
            )
            scored.append({
                "service": s,
                "creator": {
                    "display_name": creator.display_name if creator else "unknown",
                    "verification_status": creator.verification_status if creator else "none",
                },
                "outcome": {"success_rate": success_rate, "sessions": st.get("sessions", 0)},
                "trust": {"overall": trust, "freshness": "fresh" if fresh >= 0.7 else "stale"},
                "rank": {
                    "score": round(score, 4),
                    "signals": {
                        "intent_relevance": round(rel, 3),
                        "outcome_quality": round(success_rate, 3),
                        "personal_fit": round(personal_fit, 3),
                        "trust": round(trust, 3),
                        "freshness": round(fresh, 3),
                        "satisfaction": round(satisfaction, 3),
                        "exploration": exploration,
                    },
                },
                "followed": s.id in followed,
            })
        scored.sort(key=lambda x: -x["rank"]["score"])
        return scored[:limit]

    @staticmethod
    def match_for_intent(db: Session, user_id: int, intent_slug: str, limit: int = 3) -> list[dict]:
        results = ServiceRegistry.discover(db, user_id, query_intent_slug=intent_slug, limit=limit)
        return [r for r in results if r["rank"]["score"] >= 0.25 or r["rank"]["signals"]["intent_relevance"] > 0.5]
