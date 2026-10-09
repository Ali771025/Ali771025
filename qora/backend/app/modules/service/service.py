"""Service registry — CRUD, versioning, lifecycle, discovery ranking (API_CONTRACT §6)."""
import math
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.service.models import (
    ALLOWED_TRANSITIONS,
    AiService,
    FollowedService,
    LifecycleTransition,
    RankingConfiguration,
    ServiceCapabilityMap,
    ServiceIntentMap,
    ServiceVersion,
)
from app.modules.service.risk import RiskService
from app.shared.errors import CONFLICT, FORBIDDEN, NOT_FOUND, AppError


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "service"


class ServiceRegistry:
    # ---------- create ----------
    @staticmethod
    def create(db: Session, creator_profile_id: int, data: dict) -> AiService:
        slug = slugify(data["name"])
        if db.scalar(select(AiService).where(AiService.slug == slug)):
            slug = f"{slug}-{creator_profile_id}"
        risk_text = " ".join(
            str(data.get(k, ""))
            for k in ("name", "summary", "description", "purpose", "audience", "category")
        )
        risk_level = RiskService.classify(risk_text, data.get("risk_level", "LOW"))
        svc = AiService(
            creator_id=creator_profile_id,
            slug=slug,
            name=data["name"],
            summary=data.get("summary", ""),
            description=data.get("description", ""),
            purpose=data.get("purpose", ""),
            audience=data.get("audience", ""),
            category=data.get("category", "general"),
            risk_level=risk_level,
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

    @staticmethod
    def list_by_creator(db: Session, creator_profile_id: int) -> list[AiService]:
        """Interface for analytics (boundary rule)."""
        return list(db.scalars(select(AiService).where(AiService.creator_id == creator_profile_id)).all())

    @staticmethod
    def list_all_for_analytics(db: Session) -> list[AiService]:
        """Service-layer interface for scheduled analytics aggregation."""
        return list(db.scalars(select(AiService).order_by(AiService.id)).all())

    @staticmethod
    def services_using_knowledge_version(db: Session, knowledge_version_id: int) -> list[dict]:
        """Return owner/service ids for bound material without leaking module models."""
        matches = []
        for service in ServiceRegistry.list_all_for_analytics(db):
            version = ServiceRegistry.current_version(db, service)
            if version and (version.knowledge_config or {}).get("knowledge_version_id") == knowledge_version_id:
                matches.append({"service_id": service.id, "creator_id": service.creator_id})
        return matches

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

    # ---------- lifecycle + risk review ----------
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
        try:
            target = ServiceRegistry.ACTION_MAP[action]
        except KeyError as exc:
            raise AppError(CONFLICT, "Unsupported lifecycle action", 400) from exc
        ServiceRegistry._transition(db, service, target, reason, actor_id)
        if action in ("publish", "pause", "unlist"):
            from app.shared.audit import record

            record(db, actor_id, f"service.{action}", service.id, {"reason": reason[:300]})
        db.commit()
        db.refresh(service)
        return service

    @staticmethod
    def _transition(db: Session, service: AiService, to_status: str, reason: str, actor_id: int | None = None):
        from_status = service.lifecycle_status
        if to_status == "published":
            from app.modules.profile.service import ProfileService

            creator = ProfileService.get_creator_by_id(db, service.creator_id)
            version = ServiceRegistry.current_version(db, service)
            blockers = RiskService.publication_blockers(service, creator, version)
            if blockers:
                raise AppError(
                    FORBIDDEN,
                    "Risk-based publication requirements are not met",
                    403,
                    [{"blockers": blockers}],
                )
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
        db.add(
            LifecycleTransition(
                service_id=service.id,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id or 0,
                reason=reason,
            )
        )

    @staticmethod
    def set_verification_status(db: Session, service_id: int, actor_id: int, status: str) -> AiService:
        if status not in ("pending", "verified", "rejected"):
            raise AppError(CONFLICT, "Verification status must be pending, verified, or rejected", 400)
        service = ServiceRegistry.get(db, service_id)
        previous_status = service.verification_status
        if previous_status == status:
            return service
        service.verification_status = status
        if status == "rejected" and service.lifecycle_status == "published":
            ServiceRegistry._transition(db, service, "restricted", "service verification rejected", actor_id)
        from app.shared.audit import record

        record(db, actor_id, "service.verification", service.id, {"status": status})
        from app.modules.profile.service import ProfileService
        from app.modules.reputation.service import ReputationService

        creator = ProfileService.get_creator_by_id(db, service.creator_id)
        key_suffix = datetime.now(timezone.utc).isoformat()
        for subject_type, subject_id in (("service", service.id), ("creator", service.creator_id)):
            ReputationService.apply_event(
                db, subject_type, subject_id, "verification",
                idempotency_key=f"verification:{service.id}:{status}:{key_suffix}:{subject_type}:{subject_id}",
                meta={"status": status, "service_id": service.id},
                fallback_score=float(creator.trust_score) if creator else 0.5,
            )
        db.commit()
        db.refresh(service)
        return service

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
        return list(
            db.scalars(
                select(ServiceVersion)
                .where(ServiceVersion.service_id == service_id)
                .order_by(ServiceVersion.version_no.desc())
            ).all()
        )

    # ---------- ranking weights (Phase 3, admin editable) ----------
    RANK_WEIGHT_FIELDS = {
        "intent_relevance": "RANK_W_INTENT",
        "outcome_quality": "RANK_W_OUTCOME",
        "personal_fit": "RANK_W_PERSONAL_FIT",
        "trust": "RANK_W_TRUST",
        "freshness": "RANK_W_FRESHNESS",
        "exploration": "RANK_W_EXPLORATION",
        "satisfaction": "RANK_W_SATISFACTION",
        "repeat_use": "RANK_W_REPEAT_USE",
    }

    @staticmethod
    def rank_weights(db: Session) -> dict[str, float]:
        from app.core.config import settings

        row = db.get(RankingConfiguration, "default")
        if row and row.weights:
            values = {key: max(0.0, float(row.weights.get(key, 0.0))) for key in ServiceRegistry.RANK_WEIGHT_FIELDS}
        else:
            values = {
                key: float(getattr(settings, setting))
                for key, setting in ServiceRegistry.RANK_WEIGHT_FIELDS.items()
            }
        total = sum(values.values())
        return {key: value / total for key, value in values.items()} if total else {
            key: 1.0 / len(ServiceRegistry.RANK_WEIGHT_FIELDS) for key in ServiceRegistry.RANK_WEIGHT_FIELDS
        }

    @staticmethod
    def update_rank_weights(db: Session, actor_id: int, weights: dict) -> dict[str, float]:
        expected = set(ServiceRegistry.RANK_WEIGHT_FIELDS)
        if set(weights) != expected:
            raise AppError(
                CONFLICT,
                "Exactly the eight supported ranking signals must be configured",
                400,
                [{"expected": sorted(expected)}],
            )
        try:
            values = {key: float(value) for key, value in weights.items()}
        except (TypeError, ValueError) as exc:
            raise AppError(CONFLICT, "All ranking weights must be numbers", 400) from exc
        if any(value < 0 or value > 1 for value in values.values()) or sum(values.values()) <= 0:
            raise AppError(CONFLICT, "Ranking weights must be between 0 and 1 with a positive total", 400)
        total = sum(values.values())
        normalized = {key: round(value / total, 6) for key, value in values.items()}
        first = next(iter(normalized))
        normalized[first] = round(normalized[first] + 1 - sum(normalized.values()), 6)
        row = db.get(RankingConfiguration, "default")
        if row is None:
            row = RankingConfiguration(key="default", weights=normalized, updated_by=actor_id)
            db.add(row)
        else:
            row.weights = normalized
            row.updated_by = actor_id
        from app.shared.audit import record

        record(db, actor_id, "ranking.weights.updated", "default", normalized)
        db.commit()
        return normalized

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
        return {
            r.service_id
            for r in db.scalars(select(FollowedService).where(FollowedService.user_id == user_id)).all()
        }

    # ---------- discovery / matching with all eight PRD ranking signals ----------
    @staticmethod
    def discover(
        db: Session,
        user_id: int | None,
        query_intent_slug: str | None = None,
        q: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        from app.modules.knowledge.service import KnowledgeService
        from app.modules.outcome.service import OutcomeService
        from app.modules.profile.service import ProfileService
        from app.modules.reputation.service import ReputationService
        from app.modules.runtime.service import RuntimeService

        rows = db.scalars(
            select(AiService).where(AiService.lifecycle_status == "published", AiService.visibility == "public")
        ).all()
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
        weights = ServiceRegistry.rank_weights(db)
        scored = []
        for service in rows:
            creator = ProfileService.get_creator_by_id(db, service.creator_id)
            version = ServiceRegistry.current_version(db, service)
            if not RiskService.eligible_for_discovery(service, creator, version):
                continue

            relevance = 0.3
            if intent_ids:
                maps = db.scalars(
                    select(ServiceIntentMap).where(ServiceIntentMap.service_id == service.id)
                ).all()
                relevance = max([m.relevance for m in maps if m.intent_id in intent_ids] or [0.15])

            stats = outcome_stats.get(service.id, {})
            outcome_quality = float(stats.get("success_rate", 0.5))
            satisfaction = float(stats.get("confirmed_rate", 0.5))
            fallback_creator_trust = float(creator.trust_score) if creator else 0.5
            creator_trust = ReputationService.trust_for(
                db, "creator", service.creator_id, fallback=fallback_creator_trust
            )
            service_trust = ReputationService.trust_for(db, "service", service.id, fallback=0.5)
            freshness_info = KnowledgeService.freshness_for_version(
                db,
                (version.knowledge_config or {}).get("knowledge_version_id") if version else None,
            )
            freshness = float(freshness_info["score"])
            if freshness_info.get("stale"):
                ReputationService.apply_stale_knowledge(
                    db,
                    creator_id=service.creator_id,
                    service_id=service.id,
                    source_fingerprint=freshness_info["fingerprint"],
                    stale_sources=freshness_info["stale_sources"],
                )
                service_trust = ReputationService.trust_for(db, "service", service.id, fallback=0.5)
                creator_trust = ReputationService.trust_for(
                    db, "creator", service.creator_id, fallback=fallback_creator_trust
                )
            trust = round(0.30 * creator_trust["overall"] + 0.70 * service_trust["overall"], 4)
            personal_fit = 1.0 if service.id in followed else 0.5

            sessions = RuntimeService.sessions_for_service(db, service.id)
            completed_by_user: dict[int, int] = {}
            for item in sessions:
                if item.get("status") == "completed":
                    uid = item["user_id"]
                    completed_by_user[uid] = completed_by_user.get(uid, 0) + 1
            repeat_use = sum(count >= 2 for count in completed_by_user.values()) / max(len(completed_by_user), 1)
            # Usage-count novelty proxy until a dedicated impression/exposure event is wired.
            exploration = round(1.0 / math.sqrt(len(sessions) + 1), 3)
            signals = {
                "intent_relevance": round(relevance, 3),
                "outcome_quality": round(outcome_quality, 3),
                "personal_fit": round(personal_fit, 3),
                "trust": round(trust, 3),
                "freshness": round(freshness, 3),
                "satisfaction": round(satisfaction, 3),
                "repeat_use": round(repeat_use, 3),
                "exploration": exploration,
            }
            score = sum(weights[name] * value for name, value in signals.items())
            freshness_label = "stale" if freshness_info.get("stale") else "fresh"
            scored.append(
                {
                    "service": service,
                    "creator": {
                        "display_name": creator.display_name if creator else "unknown",
                        "verification_status": creator.verification_status if creator else "none",
                    },
                    "outcome": {
                        "success_rate": outcome_quality,
                        "sessions": stats.get("sessions", 0),
                    },
                    "trust": {
                        "overall": trust,
                        "creator_overall": round(creator_trust["overall"], 4),
                        "service_overall": round(service_trust["overall"], 4),
                        "components": service_trust["components"],
                        "freshness": freshness_label,
                        "freshness_score": round(freshness, 3),
                    },
                    "rank": {"score": round(score, 4), "signals": signals},
                    "followed": service.id in followed,
                }
            )
        scored.sort(key=lambda item: -item["rank"]["score"])
        return scored[:limit]

    @staticmethod
    def by_capability(db: Session, capability_slug: str, limit: int = 3) -> list[dict]:
        from app.modules.intent.service import IntentService

        ids = IntentService.ids_for_slugs(db, [], [capability_slug])
        capability_id = ids.get(capability_slug)
        if capability_id is None:
            return []
        matching_ids = set(
            db.scalars(
                select(ServiceCapabilityMap.service_id).where(
                    ServiceCapabilityMap.capability_id == capability_id
                )
            ).all()
        )
        if not matching_ids:
            return []
        candidates = ServiceRegistry.discover(db, None, limit=50)
        return [item for item in candidates if item["service"].id in matching_ids][:limit]

    @staticmethod
    def match_for_intent(db: Session, user_id: int, intent_slug: str, limit: int = 3) -> list[dict]:
        results = ServiceRegistry.discover(db, user_id, query_intent_slug=intent_slug, limit=limit)
        return [
            r for r in results
            if r["rank"]["score"] >= 0.25 or r["rank"]["signals"]["intent_relevance"] > 0.5
        ]
